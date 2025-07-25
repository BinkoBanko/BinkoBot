import os
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class DiscordService:
    def __init__(self):
        self.client_id = os.environ.get('DISCORD_CLIENT_ID')
        self.client_secret = os.environ.get('DISCORD_CLIENT_SECRET')
        self.bot_token = os.environ.get('DISCORD_BOT_TOKEN')
        self.redirect_uri = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:5000/auth/callback')
        self.base_url = 'https://discord.com/api/v10'
        
    def get_oauth_url(self, state: str = None) -> str:
        """Generate Discord OAuth authorization URL"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'identify guilds'
        }
        if state:
            params['state'] = state
            
        return f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    
    def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = requests.post(
                f"{self.base_url}/oauth2/token",
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get Discord user information"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            response = requests.get(
                f"{self.base_url}/users/@me",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    def get_user_guilds(self, access_token: str) -> Optional[List[Dict]]:
        """Get user's Discord guilds"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            response = requests.get(
                f"{self.base_url}/users/@me/guilds",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get user guilds: {e}")
            return None
    
    def get_guild_info(self, guild_id: str) -> Optional[Dict]:
        """Get guild information using bot token"""
        if not self.bot_token:
            logger.error("Bot token not configured")
            return None
            
        headers = {'Authorization': f'Bot {self.bot_token}'}
        
        try:
            response = requests.get(
                f"{self.base_url}/guilds/{guild_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get guild info for {guild_id}: {e}")
            return None
    
    def get_guild_channels(self, guild_id: str) -> Optional[List[Dict]]:
        """Get guild channels using bot token"""
        if not self.bot_token:
            logger.error("Bot token not configured")
            return None
            
        headers = {'Authorization': f'Bot {self.bot_token}'}
        
        try:
            response = requests.get(
                f"{self.base_url}/guilds/{guild_id}/channels",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get guild channels for {guild_id}: {e}")
            return None
    
    def get_guild_members(self, guild_id: str, limit: int = 1000) -> Optional[List[Dict]]:
        """Get guild members using bot token"""
        if not self.bot_token:
            logger.error("Bot token not configured")
            return None
            
        headers = {'Authorization': f'Bot {self.bot_token}'}
        params = {'limit': min(limit, 1000)}
        
        try:
            response = requests.get(
                f"{self.base_url}/guilds/{guild_id}/members",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get guild members for {guild_id}: {e}")
            return None
    
    def get_channel_messages(self, channel_id: str, limit: int = 100) -> Optional[List[Dict]]:
        """Get recent messages from a channel"""
        if not self.bot_token:
            logger.error("Bot token not configured")
            return None
            
        headers = {'Authorization': f'Bot {self.bot_token}'}
        params = {'limit': min(limit, 100)}
        
        try:
            response = requests.get(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get channel messages for {channel_id}: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh Discord access token"""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            response = requests.post(
                f"{self.base_url}/oauth2/token",
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None
