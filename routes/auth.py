from flask import Blueprint, request, redirect, url_for, session, flash, render_template
import secrets
import logging
from models import User
from discord_service import DiscordService
from app import db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)
discord_service = DiscordService()

@auth_bp.route('/login')
def login():
    """Redirect to Discord OAuth"""
    if 'user_id' in session:
        return redirect(url_for('dashboard.overview'))
    
    # Generate a random state for security
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    
    oauth_url = discord_service.get_oauth_url(state)
    return redirect(oauth_url)

@auth_bp.route('/callback')
def callback():
    """Handle Discord OAuth callback"""
    # Verify state parameter
    state = request.args.get('state')
    if not state or state != session.get('oauth_state'):
        flash('Invalid OAuth state. Please try again.', 'error')
        return redirect(url_for('index'))
    
    # Clear the state from session
    session.pop('oauth_state', None)
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        error = request.args.get('error', 'Unknown error')
        flash(f'OAuth error: {error}', 'error')
        return redirect(url_for('index'))
    
    try:
        # Exchange code for token
        token_data = discord_service.exchange_code_for_token(code)
        if not token_data:
            flash('Failed to obtain access token from Discord.', 'error')
            return redirect(url_for('index'))
        
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        
        # Get user information
        user_info = discord_service.get_user_info(access_token)
        if not user_info:
            flash('Failed to get user information from Discord.', 'error')
            return redirect(url_for('index'))
        
        # Find or create user
        user = User.query.filter_by(discord_id=user_info['id']).first()
        
        if user:
            # Update existing user
            user.username = user_info['username']
            user.discriminator = user_info.get('discriminator', '0000')
            user.avatar = user_info.get('avatar')
            user.access_token = access_token
            user.refresh_token = refresh_token
            user.last_login = db.func.now()
        else:
            # Create new user
            user = User(
                discord_id=user_info['id'],
                username=user_info['username'],
                discriminator=user_info.get('discriminator', '0000'),
                avatar=user_info.get('avatar'),
                access_token=access_token,
                refresh_token=refresh_token
            )
            db.session.add(user)
        
        db.session.commit()
        
        # Store user ID in session
        session['user_id'] = user.id
        session['username'] = user.username
        
        flash(f'Welcome, {user.username}!', 'success')
        return redirect(url_for('dashboard.overview'))
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        flash('An error occurred during login. Please try again.', 'error')
        return redirect(url_for('index'))

@auth_bp.route('/logout')
def logout():
    """Log out the user"""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/profile')
def profile():
    """User profile page"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found. Please log in again.', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('profile.html', user=user)
