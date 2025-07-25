from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
import logging
from models import User, Server, UserServer, VibeScore, ServerAnalytics
from discord_service import DiscordService
from vibe_analyzer import VibeAnalyzer
from app import db
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)
discord_service = DiscordService()
vibe_analyzer = VibeAnalyzer()

def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@dashboard_bp.route('/')
@login_required
def overview():
    """Main dashboard overview"""
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Sync user's Discord servers
    sync_user_servers(user)
    
    # Get user's servers with latest vibe scores
    user_servers = db.session.query(Server, VibeScore).join(
        UserServer, UserServer.server_id == Server.id
    ).outerjoin(
        VibeScore, VibeScore.server_id == Server.id
    ).filter(
        UserServer.user_id == user.id
    ).order_by(
        VibeScore.calculated_at.desc().nullslast()
    ).all()
    
    # Group by server and get latest vibe score for each
    servers_with_vibes = {}
    for server, vibe_score in user_servers:
        if server.id not in servers_with_vibes:
            servers_with_vibes[server.id] = {
                'server': server,
                'vibe_score': vibe_score
            }
    
    servers_data = list(servers_with_vibes.values())
    
    # Calculate overall statistics
    total_servers = len(servers_data)
    avg_vibe = 0
    if servers_data:
        vibe_scores = [s['vibe_score'].overall_score for s in servers_data if s['vibe_score']]
        avg_vibe = sum(vibe_scores) / len(vibe_scores) if vibe_scores else 0
    
    return render_template('dashboard.html', 
                         user=user, 
                         servers=servers_data,
                         total_servers=total_servers,
                         avg_vibe=round(avg_vibe, 1))

@dashboard_bp.route('/server/<int:server_id>')
@login_required
def server_detail(server_id):
    """Detailed view of a specific server"""
    user = User.query.get(session['user_id'])
    if not user:
        flash('User session expired. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user has access to this server
    user_server = UserServer.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if not user_server:
        flash('Server not found or access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    
    server = Server.query.get(server_id)
    
    # Get recent vibe scores
    recent_vibes = VibeScore.query.filter_by(
        server_id=server_id
    ).order_by(VibeScore.calculated_at.desc()).limit(30).all()
    
    # Get recent analytics
    recent_analytics = ServerAnalytics.query.filter_by(
        server_id=server_id
    ).order_by(ServerAnalytics.date.desc()).limit(30).all()
    
    # Get latest vibe score
    latest_vibe = recent_vibes[0] if recent_vibes else None
    
    return render_template('server_detail.html',
                         server=server,
                         latest_vibe=latest_vibe,
                         recent_vibes=recent_vibes,
                         recent_analytics=recent_analytics)

@dashboard_bp.route('/refresh-server/<int:server_id>')
@login_required
def refresh_server(server_id):
    """Refresh analytics and vibe score for a server"""
    user = User.query.get(session['user_id'])
    if not user:
        flash('User session expired. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    # Check if user has access to this server
    user_server = UserServer.query.filter_by(
        user_id=user.id,
        server_id=server_id
    ).first()
    
    if not user_server:
        flash('Server not found or access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    
    try:
        # Update analytics
        vibe_analyzer.update_server_analytics(server_id)
        
        # Calculate new vibe score
        vibe_score = vibe_analyzer.analyze_server_vibe(server_id)
        
        if vibe_score:
            flash('Server analytics and vibe score updated successfully!', 'success')
        else:
            flash('Failed to update server analytics. Please try again.', 'warning')
            
    except Exception as e:
        logger.error(f"Error refreshing server {server_id}: {e}")
        flash('An error occurred while refreshing server data.', 'error')
    
    return redirect(url_for('dashboard.server_detail', server_id=server_id))

def sync_user_servers(user):
    """Sync user's Discord servers with database"""
    try:
        # Get user's guilds from Discord
        guilds = discord_service.get_user_guilds(user.access_token)
        if not guilds:
            logger.warning(f"Failed to get guilds for user {user.username}")
            return
        
        for guild in guilds:
            # Check if server exists in database
            server = Server.query.filter_by(discord_id=guild['id']).first()
            
            if not server:
                # Create new server record
                server = Server()
                server.discord_id = guild['id']
                server.name = guild['name']
                server.icon = guild.get('icon')
                server.owner_id = guild.get('owner_id')
                db.session.add(server)
                db.session.flush()  # Get the server ID
            else:
                # Update existing server info
                server.name = guild['name']
                server.icon = guild.get('icon')
                server.owner_id = guild.get('owner_id')
            
            # Check if user-server relationship exists
            user_server = UserServer.query.filter_by(
                user_id=user.id,
                server_id=server.id
            ).first()
            
            if not user_server:
                # Create user-server relationship
                user_server = UserServer()
                user_server.user_id = user.id
                user_server.server_id = server.id
                user_server.permissions = guild.get('permissions', 0)
                db.session.add(user_server)
            else:
                # Update permissions
                user_server.permissions = guild.get('permissions', 0)
        
        db.session.commit()
        logger.info(f"Synced {len(guilds)} servers for user {user.username}")
        
    except Exception as e:
        logger.error(f"Error syncing servers for user {user.username}: {e}")
        db.session.rollback()
