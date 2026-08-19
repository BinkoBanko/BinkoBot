from flask import Blueprint, render_template, session, redirect, url_for, flash, request, jsonify
import logging
from enum import Enum
from web.models import User, Server, UserServer, VibeScore, ServerAnalytics
from web.discord_service import (
    DiscordService,
    DiscordInvalidRefreshTokenError,
    DiscordUnauthorizedError,
)
from web.vibe_analyzer import VibeAnalyzer
from app import db
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)
discord_service = DiscordService()
vibe_analyzer = VibeAnalyzer()


class SyncStatus(Enum):
    """Outcome of synchronizing a user's Discord servers."""

    SUCCESS = 'success'
    LOGIN_REQUIRED = 'login_required'
    UNAVAILABLE = 'unavailable'

    def __bool__(self):
        """Keep the result convenient for callers that only need success."""
        return self is SyncStatus.SUCCESS


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
    
    # Sync user's Discord servers. If Discord rejected the access token and
    # the stored refresh token cannot restore it, do not present an
    # authenticated-but-stale dashboard.
    sync_status = sync_user_servers(user)
    if sync_status is SyncStatus.LOGIN_REQUIRED:
        session.pop('user_id', None)
        session.pop('username', None)
        flash(
            'Your Discord session has expired or is no longer valid. '
            'Please log in again.',
            'error',
        )
        return redirect(url_for('auth.login'))
    if sync_status is SyncStatus.UNAVAILABLE:
        flash(
            'Discord is temporarily unavailable. Showing your saved dashboard '
            'data; please try again shortly.',
            'warning',
        )
    
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

def _try_refresh_user_tokens(user) -> SyncStatus:
    """Exchange the user's stored refresh token for a new access/refresh pair.

    Only returns LOGIN_REQUIRED when Discord explicitly confirms the refresh
    token is revoked or expired (``invalid_grant``). Every other failure —
    missing stored refresh token, non-``invalid_grant`` API errors, malformed
    responses, or database write failures — returns UNAVAILABLE so the caller
    can keep the current session and show saved dashboard data.
    """
    if not user.refresh_token:
        logger.warning(
            "Cannot refresh tokens for user %s: no refresh token stored; "
            "keeping current session",
            user.username,
        )
        return SyncStatus.UNAVAILABLE

    try:
        new_tokens = discord_service.refresh_access_token(user.refresh_token)
    except DiscordInvalidRefreshTokenError:
        # Discord explicitly said ``invalid_grant`` — the token is gone.
        logger.warning(
            "Stored refresh token is invalid (invalid_grant) for user %s; "
            "re-authentication required",
            user.username,
        )
        return SyncStatus.LOGIN_REQUIRED

    if not isinstance(new_tokens, dict):
        logger.warning(
            "Token refresh unavailable for user %s; keeping the current session",
            user.username,
        )
        return SyncStatus.UNAVAILABLE

    new_access = new_tokens.get("access_token")
    new_refresh = new_tokens.get("refresh_token", user.refresh_token)
    if not new_access:
        logger.warning(
            "Token refresh for user %s returned no access_token; treating "
            "as transient failure",
            user.username,
        )
        return SyncStatus.UNAVAILABLE

    previous_access = user.access_token
    previous_refresh = user.refresh_token
    user.access_token = new_access
    user.refresh_token = new_refresh
    try:
        db.session.commit()
    except Exception as e:
        logger.error(
            "Failed to persist refreshed tokens for user %s: %s",
            user.username, e,
        )
        db.session.rollback()
        user.access_token = previous_access
        user.refresh_token = previous_refresh
        return SyncStatus.UNAVAILABLE

    logger.info("Refreshed Discord tokens for user %s", user.username)
    return SyncStatus.SUCCESS


def sync_user_servers(user) -> SyncStatus:
    """Sync user's Discord servers with database.

    Returns LOGIN_REQUIRED when Discord explicitly rejects the access token and
    the stored refresh token is missing or invalid. Returns UNAVAILABLE for
    temporary Discord/database failures so callers can keep showing saved data.
    """
    try:
        # A missing response represents an unavailable API, not proof that
        # the user's credentials are invalid. Only an explicit 401 starts the
        # one-shot refresh flow.
        try:
            guilds = discord_service.get_user_guilds(user.access_token)
        except DiscordUnauthorizedError:
            logger.info(
                "Discord rejected the access token for user %s; attempting "
                "token refresh",
                user.username,
            )
            refresh_status = _try_refresh_user_tokens(user)
            if refresh_status is not SyncStatus.SUCCESS:
                return refresh_status
            try:
                guilds = discord_service.get_user_guilds(user.access_token)
            except DiscordUnauthorizedError:
                # The freshly-issued token was also rejected. This is a
                # transient Discord fault, not confirmation that the user's
                # credentials are invalid — do not log them out.
                logger.warning(
                    "Refreshed token was also rejected for user %s; treating "
                    "as transient Discord unavailability",
                    user.username,
                )
                return SyncStatus.UNAVAILABLE

        if guilds is None:
            logger.warning(
                "Discord guild data is temporarily unavailable for user %s",
                user.username,
            )
            return SyncStatus.UNAVAILABLE
        
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
        return SyncStatus.SUCCESS
        
    except Exception as e:
        logger.error(f"Error syncing servers for user {user.username}: {e}")
        db.session.rollback()
        return SyncStatus.UNAVAILABLE
