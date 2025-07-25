import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from collections import defaultdict, Counter
import re
from models import Server, VibeScore, ServerAnalytics, ChannelActivity
from discord_service import DiscordService
from app import db

logger = logging.getLogger(__name__)

class VibeAnalyzer:
    def __init__(self):
        self.discord_service = DiscordService()
        
        # Positive and negative sentiment indicators
        self.positive_words = {
            'awesome', 'amazing', 'great', 'excellent', 'fantastic', 'wonderful',
            'love', 'like', 'enjoy', 'fun', 'cool', 'nice', 'good', 'best',
            'happy', 'excited', 'glad', 'thanks', 'thank', 'appreciate',
            'congrats', 'congratulations', 'celebrate', 'achievement', 'success'
        }
        
        self.negative_words = {
            'hate', 'awful', 'terrible', 'horrible', 'bad', 'worst',
            'annoying', 'frustrated', 'angry', 'mad', 'upset', 'sad',
            'boring', 'stupid', 'dumb', 'suck', 'sucks', 'fail', 'failed'
        }
        
        self.positive_emojis = {
            '😀', '😃', '😄', '😁', '😆', '😂', '🤣', '😊', '😇', '🙂',
            '😍', '🥰', '😘', '😗', '😙', '😚', '😋', '😛', '😜', '🤪',
            '😎', '🤩', '🥳', '😏', '😌', '👍', '👌', '✅', '✨', '🎉',
            '🔥', '💯', '❤️', '💕', '💖', '💗', '💙', '💚', '💛', '🧡'
        }
    
    def analyze_server_vibe(self, server_id: int) -> Optional[VibeScore]:
        """Analyze and calculate vibe score for a server"""
        try:
            server = Server.query.get(server_id)
            if not server:
                logger.error(f"Server {server_id} not found")
                return None
            
            # Get recent analytics data
            recent_analytics = self._get_recent_analytics(server_id)
            
            # Calculate individual scores
            activity_score = self._calculate_activity_score(server, recent_analytics)
            positivity_score = self._calculate_positivity_score(server)
            engagement_score = self._calculate_engagement_score(server, recent_analytics)
            growth_score = self._calculate_growth_score(server, recent_analytics)
            
            # Calculate overall score (weighted average)
            overall_score = (
                activity_score * 0.3 +
                positivity_score * 0.25 +
                engagement_score * 0.25 +
                growth_score * 0.2
            )
            
            # Create or update vibe score
            vibe_score = VibeScore()
            vibe_score.server_id = server_id
            vibe_score.overall_score = round(overall_score, 2)
            vibe_score.activity_score = round(activity_score, 2)
            vibe_score.positivity_score = round(positivity_score, 2)
            vibe_score.engagement_score = round(engagement_score, 2)
            vibe_score.growth_score = round(growth_score, 2)
            
            db.session.add(vibe_score)
            
            # Update server's last analyzed timestamp
            server.last_analyzed = datetime.now(timezone.utc)
            db.session.commit()
            
            logger.info(f"Calculated vibe score for server {server.name}: {overall_score}")
            return vibe_score
            
        except Exception as e:
            logger.error(f"Error analyzing server vibe: {e}")
            db.session.rollback()
            return None
    
    def _get_recent_analytics(self, server_id: int, days: int = 7) -> List[ServerAnalytics]:
        """Get recent analytics data for a server"""
        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
        return ServerAnalytics.query.filter(
            ServerAnalytics.server_id == server_id,
            ServerAnalytics.date >= cutoff_date
        ).order_by(ServerAnalytics.date.desc()).all()
    
    def _calculate_activity_score(self, server: Server, analytics: List[ServerAnalytics]) -> float:
        """Calculate activity score based on message volume and active users"""
        if not analytics:
            return 0.0
        
        # Average daily metrics
        avg_messages = sum(a.message_count for a in analytics) / len(analytics)
        avg_active_users = sum(a.active_users for a in analytics) / len(analytics)
        
        # Normalize based on server size
        member_count = max(server.member_count, 1)
        message_ratio = min(avg_messages / member_count, 10.0)  # Cap at 10 messages per member
        activity_ratio = min(avg_active_users / member_count, 1.0)  # Cap at 100%
        
        # Score from 0-100
        activity_score = (message_ratio * 5 + activity_ratio * 50) * 2
        return min(activity_score, 100.0)
    
    def _calculate_positivity_score(self, server: Server) -> float:
        """Calculate positivity score based on message sentiment"""
        try:
            # Get recent messages from channels
            channels = self.discord_service.get_guild_channels(server.discord_id)
            if not channels:
                return 50.0  # Default neutral score
            
            positive_count = 0
            negative_count = 0
            total_analyzed = 0
            
            # Analyze messages from text channels
            for channel in channels[:5]:  # Limit to first 5 channels
                if channel.get('type') == 0:  # Text channel
                    messages = self.discord_service.get_channel_messages(
                        channel['id'], limit=50
                    )
                    if messages:
                        for message in messages:
                            sentiment = self._analyze_message_sentiment(message.get('content', ''))
                            if sentiment > 0:
                                positive_count += sentiment
                            elif sentiment < 0:
                                negative_count += abs(sentiment)
                            total_analyzed += 1
            
            if total_analyzed == 0:
                return 50.0
            
            # Calculate positivity ratio
            total_sentiment = positive_count + negative_count
            if total_sentiment == 0:
                return 50.0
            
            positivity_ratio = positive_count / total_sentiment
            return min(positivity_ratio * 100, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating positivity score: {e}")
            return 50.0
    
    def _analyze_message_sentiment(self, content: str) -> int:
        """Analyze sentiment of a message (-3 to +3)"""
        if not content:
            return 0
        
        content_lower = content.lower()
        words = re.findall(r'\b\w+\b', content_lower)
        
        sentiment = 0
        
        # Check for positive words
        for word in words:
            if word in self.positive_words:
                sentiment += 1
        
        # Check for negative words
        for word in words:
            if word in self.negative_words:
                sentiment -= 1
        
        # Check for positive emojis
        for emoji in self.positive_emojis:
            sentiment += content.count(emoji)
        
        return max(-3, min(3, sentiment))
    
    def _calculate_engagement_score(self, server: Server, analytics: List[ServerAnalytics]) -> float:
        """Calculate engagement score based on reactions and voice activity"""
        if not analytics:
            return 0.0
        
        avg_reactions = sum(a.reactions_count for a in analytics) / len(analytics)
        avg_voice_minutes = sum(a.voice_minutes for a in analytics) / len(analytics)
        avg_messages = sum(a.message_count for a in analytics) / len(analytics)
        
        # Calculate engagement ratios
        reaction_ratio = avg_reactions / max(avg_messages, 1) if avg_messages > 0 else 0
        voice_engagement = min(avg_voice_minutes / max(server.member_count, 1), 60)  # Max 60 min per member
        
        # Score from 0-100
        engagement_score = (reaction_ratio * 100 + voice_engagement) / 2
        return min(engagement_score, 100.0)
    
    def _calculate_growth_score(self, server: Server, analytics: List[ServerAnalytics]) -> float:
        """Calculate growth score based on new members and activity trends"""
        if len(analytics) < 2:
            return 50.0  # Default neutral score
        
        # Calculate member growth
        total_new_members = sum(a.new_members for a in analytics)
        avg_new_members = total_new_members / len(analytics)
        
        # Calculate activity trend
        recent_activity = sum(a.message_count for a in analytics[:3]) / 3  # Last 3 days
        older_activity = sum(a.message_count for a in analytics[-3:]) / 3  # Older 3 days
        
        activity_trend = 0
        if older_activity > 0:
            activity_trend = (recent_activity - older_activity) / older_activity
        
        # Normalize growth indicators
        member_growth_score = min(avg_new_members * 10, 50)  # Max 50 for member growth
        activity_trend_score = max(0, min(activity_trend * 100 + 25, 50))  # Max 50 for activity trend
        
        return member_growth_score + activity_trend_score
    
    def update_server_analytics(self, server_id: int) -> bool:
        """Update analytics data for a server"""
        try:
            server = Server.query.get(server_id)
            if not server:
                return False
            
            # Get current date
            today = datetime.now(timezone.utc).date()
            
            # Check if we already have analytics for today
            existing = ServerAnalytics.query.filter(
                ServerAnalytics.server_id == server_id,
                ServerAnalytics.date == today
            ).first()
            
            if existing:
                logger.info(f"Analytics already exist for server {server.name} today")
                return True
            
            # Collect analytics data
            analytics_data = self._collect_server_analytics(server)
            
            # Create new analytics record
            analytics = ServerAnalytics()
            analytics.server_id = server_id
            analytics.date = today
            for key, value in analytics_data.items():
                setattr(analytics, key, value)
            
            db.session.add(analytics)
            db.session.commit()
            
            logger.info(f"Updated analytics for server {server.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating server analytics: {e}")
            db.session.rollback()
            return False
    
    def _collect_server_analytics(self, server: Server) -> Dict:
        """Collect analytics data from Discord API"""
        analytics_data = {
            'message_count': 0,
            'active_users': 0,
            'new_members': 0,
            'reactions_count': 0,
            'voice_minutes': 0
        }
        
        try:
            # Get channels
            channels = self.discord_service.get_guild_channels(server.discord_id)
            if not channels:
                return analytics_data
            
            active_users = set()
            
            # Analyze text channels
            for channel in channels:
                if channel.get('type') == 0:  # Text channel
                    messages = self.discord_service.get_channel_messages(
                        channel['id'], limit=100
                    )
                    if messages:
                        today_messages = []
                        today = datetime.now(timezone.utc).date()
                        
                        for message in messages:
                            # Parse message timestamp
                            msg_time = datetime.fromisoformat(
                                message['timestamp'].replace('Z', '+00:00')
                            )
                            if msg_time.date() == today:
                                today_messages.append(message)
                                active_users.add(message['author']['id'])
                        
                        analytics_data['message_count'] += len(today_messages)
                        
                        # Count reactions
                        for message in today_messages:
                            if 'reactions' in message:
                                for reaction in message['reactions']:
                                    analytics_data['reactions_count'] += reaction.get('count', 0)
            
            analytics_data['active_users'] = len(active_users)
            
            # Note: Voice minutes and new members would require more complex tracking
            # For now, we'll use placeholder values or implement simplified tracking
            
        except Exception as e:
            logger.error(f"Error collecting server analytics: {e}")
        
        return analytics_data
