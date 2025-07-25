from flask import Blueprint, jsonify, session, request
import logging
from models import User, Server, UserServer, VibeScore, ServerAnalytics
from datetime import datetime, timedelta, timezone
from app import db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

def api_login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@api_bp.route('/server/<int:server_id>/vibe-history')
@api_login_required
def server_vibe_history(server_id):
    """Get vibe score history for a server"""
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    # Check access
    user_server = UserServer.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if not user_server:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get number of days from query parameter
    days = request.args.get('days', 30, type=int)
    days = min(days, 90)  # Limit to 90 days max
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    vibe_scores = VibeScore.query.filter(
        VibeScore.server_id == server_id,
        VibeScore.calculated_at >= cutoff_date
    ).order_by(VibeScore.calculated_at.asc()).all()
    
    data = []
    for score in vibe_scores:
        data.append({
            'date': score.calculated_at.strftime('%Y-%m-%d'),
            'overall_score': score.overall_score,
            'activity_score': score.activity_score,
            'positivity_score': score.positivity_score,
            'engagement_score': score.engagement_score,
            'growth_score': score.growth_score
        })
    
    return jsonify(data)

@api_bp.route('/server/<int:server_id>/analytics')
@api_login_required
def server_analytics(server_id):
    """Get analytics data for a server"""
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    # Check access
    user_server = UserServer.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if not user_server:
        return jsonify({'error': 'Access denied'}), 403
    
    # Get number of days from query parameter
    days = request.args.get('days', 30, type=int)
    days = min(days, 90)  # Limit to 90 days max
    
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
    
    analytics = ServerAnalytics.query.filter(
        ServerAnalytics.server_id == server_id,
        ServerAnalytics.date >= cutoff_date
    ).order_by(ServerAnalytics.date.asc()).all()
    
    data = []
    for record in analytics:
        data.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'message_count': record.message_count,
            'active_users': record.active_users,
            'new_members': record.new_members,
            'reactions_count': record.reactions_count,
            'voice_minutes': record.voice_minutes
        })
    
    return jsonify(data)

@api_bp.route('/dashboard/stats')
@api_login_required
def dashboard_stats():
    """Get overall dashboard statistics"""
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    # Get user's servers
    server_ids = [us.server_id for us in user.servers]
    
    if not server_ids:
        return jsonify({
            'total_servers': 0,
            'avg_vibe': 0,
            'total_members': 0,
            'active_servers': 0
        })
    
    # Get latest vibe scores for each server
    latest_vibes = []
    for server_id in server_ids:
        latest_vibe = VibeScore.query.filter_by(
            server_id=server_id
        ).order_by(VibeScore.calculated_at.desc()).first()
        
        if latest_vibe:
            latest_vibes.append(latest_vibe.overall_score)
    
    # Get server information
    servers = Server.query.filter(Server.id.in_(server_ids)).all()
    
    total_members = sum(s.member_count or 0 for s in servers)
    avg_vibe = sum(latest_vibes) / len(latest_vibes) if latest_vibes else 0
    active_servers = len([s for s in servers if s.last_analyzed])
    
    return jsonify({
        'total_servers': len(servers),
        'avg_vibe': round(avg_vibe, 1),
        'total_members': total_members,
        'active_servers': active_servers
    })

@api_bp.route('/server/<int:server_id>/summary')
@api_login_required
def server_summary(server_id):
    """Get server summary data"""
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 401
    
    # Check access
    user_server = UserServer.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if not user_server:
        return jsonify({'error': 'Access denied'}), 403
    
    server = Server.query.get(server_id)
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    # Get latest vibe score
    latest_vibe = VibeScore.query.filter_by(
        server_id=server_id
    ).order_by(VibeScore.calculated_at.desc()).first()
    
    # Get recent analytics (last 7 days)
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=7)
    recent_analytics = ServerAnalytics.query.filter(
        ServerAnalytics.server_id == server_id,
        ServerAnalytics.date >= cutoff_date
    ).all()
    
    # Calculate totals
    total_messages = sum(a.message_count for a in recent_analytics)
    total_active_users = sum(a.active_users for a in recent_analytics)
    avg_active_users = total_active_users / len(recent_analytics) if recent_analytics else 0
    
    return jsonify({
        'server': {
            'id': server.id,
            'name': server.name,
            'member_count': server.member_count,
            'last_analyzed': server.last_analyzed.isoformat() if server.last_analyzed else None
        },
        'vibe_score': {
            'overall_score': latest_vibe.overall_score if latest_vibe else 0,
            'activity_score': latest_vibe.activity_score if latest_vibe else 0,
            'positivity_score': latest_vibe.positivity_score if latest_vibe else 0,
            'engagement_score': latest_vibe.engagement_score if latest_vibe else 0,
            'growth_score': latest_vibe.growth_score if latest_vibe else 0,
            'last_calculated': latest_vibe.calculated_at.isoformat() if latest_vibe else None
        },
        'weekly_stats': {
            'total_messages': total_messages,
            'avg_active_users': round(avg_active_users, 1),
            'days_analyzed': len(recent_analytics)
        }
    })
