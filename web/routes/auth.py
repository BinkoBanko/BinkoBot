from flask import Blueprint, request, redirect, url_for, session, flash, render_template
import os
import secrets
import logging
from urllib.parse import urlparse
from web.models import User
from web.discord_service import DiscordService
from app import db

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)
discord_service = DiscordService()


def _redirect_uri_registration_message():
    """Explain how to repair Discord OAuth after a public-domain change."""
    redirect_uri = getattr(discord_service, 'redirect_uri', None)
    if not redirect_uri:
        redirect_uri = 'the configured callback URI'
    return (
        "In the Discord Developer Portal, register this exact OAuth2 redirect "
        f"URI: {redirect_uri}"
    )


def _normalize_uri(uri):
    """Normalize a URI for comparison: lowercase scheme/host, keep path."""
    if not isinstance(uri, str):
        return None
    try:
        parts = urlparse(uri)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path or ''}"


def _redirect_uri_problem(request_host):
    """
    Verify -- BEFORE redirecting to Discord -- that the redirect URI the app
    is about to send is actually registered for this Discord application.

    Discord validates the redirect URI before showing its authorization
    page, so an unregistered URI dead-ends users on Discord's own error page
    and the app never gets a chance to explain. This applies both to a stale
    explicit DISCORD_REDIRECT_URI *and* to the auto-derived REPLIT_DOMAINS
    fallback after the domain changes.

    Returns None when login may proceed, or a dict describing the problem:
      { 'reason': str, 'effective_uri': str, 'registered': list|None }
    """
    effective_uri = getattr(discord_service, 'redirect_uri', None)
    normalized_effective = _normalize_uri(effective_uri)
    if normalized_effective is None:
        return {
            'reason': 'malformed',
            'effective_uri': effective_uri,
            'registered': None,
        }

    # Primary check: ask Discord which redirect URIs are registered for this
    # application and require an exact (normalized) match.
    registered = discord_service.get_registered_redirect_uris()
    if registered is not None:
        normalized_registered = [
            n for n in (_normalize_uri(u) for u in registered) if n
        ]
        if normalized_effective not in normalized_registered:
            return {
                'reason': 'unregistered',
                'effective_uri': effective_uri,
                'registered': registered,
            }
        return None

    # Verification against Discord unavailable (no bot token / API error).
    # Fall back to a local sanity check: an explicitly configured
    # DISCORD_REDIRECT_URI must exactly match the callback for the domain
    # actually serving this request. The auto-derived fallback matches by
    # construction, so only the explicit value can drift here.
    configured = os.environ.get('DISCORD_REDIRECT_URI')
    if configured and request_host:
        expected = _normalize_uri(f'https://{request_host}/auth/callback')
        if _normalize_uri(configured) != expected:
            return {
                'reason': 'mismatch',
                'effective_uri': configured,
                'registered': None,
            }
    return None


@auth_bp.route('/login')
def login():
    """Redirect to Discord OAuth"""
    if 'user_id' in session:
        return redirect(url_for('dashboard.overview'))

    if not discord_service.oauth_configured:
        logger.error('Discord OAuth credentials are not configured')
        flash(
            'Discord sign-in is not configured yet. '
            f'{_redirect_uri_registration_message()}',
            'error',
        )
        return redirect(url_for('index'))

    # Guard: never send users to Discord with a redirect URI that Discord
    # will reject. Discord validates the URI before showing its authorization
    # page, so an unregistered/stale URI dead-ends users on Discord's own
    # error page. This covers both a stale explicit DISCORD_REDIRECT_URI and
    # the auto-derived callback after the Replit domain changed.
    problem = _redirect_uri_problem(request.host)
    if problem:
        # For an unregistered-but-well-formed URI the value to register is
        # the effective URI itself (it already reflects the current domain).
        # For a stale explicit value or malformed URI, derive it from the
        # domain actually serving this request.
        if problem['reason'] == 'unregistered':
            current_callback = problem['effective_uri']
        else:
            current_callback = f'https://{request.host}/auth/callback'
        registered = problem.get('registered')
        registered_hint = (
            f" Currently registered in Discord: {', '.join(registered)}."
            if registered else ''
        )
        logger.error(
            'Discord redirect URI problem (%s): app would send %s. '
            'Register %s in the Discord Developer Portal (OAuth2 → '
            'Redirects) and/or set DISCORD_REDIRECT_URI to it.%s',
            problem['reason'], problem['effective_uri'],
            current_callback, registered_hint,
        )
        flash(
            'Discord sign-in is misconfigured for this domain. The app '
            f"would use the redirect URI {problem['effective_uri']}, which "
            'Discord will not accept. Register this exact URI in the '
            f'Discord Developer Portal (OAuth2 → Redirects): {current_callback} '
            '— and if the DISCORD_REDIRECT_URI environment variable is set, '
            f'update it to the same value.{registered_hint}',
            'error',
        )
        return redirect(url_for('index'))

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
        flash(
            f'OAuth error: {error}. '
            f'{_redirect_uri_registration_message()}',
            'error',
        )
        return redirect(url_for('index'))
    
    try:
        # Exchange code for token
        token_data = discord_service.exchange_code_for_token(code)
        if not token_data:
            flash(
                'Failed to obtain access token from Discord. '
                f'{_redirect_uri_registration_message()}',
                'error',
            )
            return redirect(url_for('index'))
        
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        
        # Get user information
        if not access_token:
            flash('No access token received from Discord.', 'error')
            return redirect(url_for('index'))
        
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
            user = User()
            user.discord_id = user_info['id']
            user.username = user_info['username']
            user.discriminator = user_info.get('discriminator', '0000')
            user.avatar = user_info.get('avatar')
            user.access_token = access_token
            user.refresh_token = refresh_token
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
