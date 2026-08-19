import os
import time
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class DiscordUnauthorizedError(Exception):
    """Raised when Discord rejects a user access token as unauthorized."""


class DiscordInvalidRefreshTokenError(Exception):
    """Raised when Discord rejects a refresh token as invalid or expired."""


class DiscordService:
    # How long a successful registered-redirect-URIs lookup stays cached.
    REGISTERED_URIS_CACHE_TTL = 300  # seconds

    def __init__(self):
        self.client_id = os.environ.get('DISCORD_CLIENT_ID')
        self.client_secret = os.environ.get('DISCORD_CLIENT_SECRET')
        self.bot_token = os.environ.get('DISCORD_BOT_TOKEN')
        self.redirect_uri = self._get_redirect_uri()
        self.base_url = 'https://discord.com/api/v10'
        self._registered_uris_cache: Optional[List[str]] = None
        self._registered_uris_cache_time = 0.0

    @staticmethod
    def _get_redirect_uri() -> str:
        """Return the configured callback or the current Replit app callback."""
        configured_uri = os.environ.get('DISCORD_REDIRECT_URI')
        if configured_uri:
            return configured_uri

        # Replit exposes the public app domain at runtime. Prefer it over a
        # localhost fallback so OAuth works in the Preview and on deployments
        # without requiring a second code change.
        domains = os.environ.get('REPLIT_DOMAINS') or os.environ.get('REPLIT_DEV_DOMAIN')
        if domains:
            domain = domains.split(',')[0].strip().rstrip('/')
            if domain:
                return f'https://{domain}/auth/callback'

        return 'http://localhost:5000/auth/callback'

    @property
    def oauth_configured(self) -> bool:
        """Whether the credentials required to start Discord OAuth are set."""
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def get_registered_redirect_uris(self) -> Optional[List[str]]:
        """Fetch the OAuth2 redirect URIs registered for this application in
        the Discord Developer Portal (GET /applications/@me, bot token auth).

        Returns the list of registered URIs, or None when verification is
        impossible (no bot token, or the API call failed). Successful lookups
        are cached for REGISTERED_URIS_CACHE_TTL seconds; failures are never
        cached so a transient error does not stick.
        """
        now = time.monotonic()
        if (
            self._registered_uris_cache is not None
            and now - self._registered_uris_cache_time < self.REGISTERED_URIS_CACHE_TTL
        ):
            return self._registered_uris_cache

        if not self.bot_token:
            return None

        try:
            response = requests.get(
                f"{self.base_url}/applications/@me",
                headers={'Authorization': f'Bot {self.bot_token}'},
                timeout=10,
            )
            response.raise_for_status()
            uris = response.json().get('redirect_uris')
        except (requests.RequestException, ValueError) as e:
            logger.error(f"Failed to fetch registered redirect URIs: {e}")
            return None

        if not isinstance(uris, list):
            return None

        self._registered_uris_cache = uris
        self._registered_uris_cache_time = now
        return uris

    def get_oauth_url(self, state: Optional[str] = None) -> str:
        """Generate Discord OAuth authorization URL"""
        if not self.oauth_configured:
            raise RuntimeError('Discord OAuth credentials are not configured')

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
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                logger.warning("Discord rejected the user access token")
                raise DiscordUnauthorizedError(
                    "Discord access token is unauthorized"
                ) from e
            logger.error(f"Failed to get user info: {e}")
            return None
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
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                logger.warning("Discord rejected the user access token")
                raise DiscordUnauthorizedError(
                    "Discord access token is unauthorized"
                ) from e
            logger.error(f"Failed to get user guilds: {e}")
            return None
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
        except requests.HTTPError as e:
            if e.response is not None:
                # Only `invalid_grant` conclusively identifies an expired or
                # revoked user refresh token. Other 400/401 responses (e.g.
                # invalid_client, invalid_request, unsupported_grant_type) are
                # application-side or transient configuration failures --
                # re-authentication by the user cannot fix them, so they are
                # treated as a temporary unavailability rather than an
                # authorization error.
                try:
                    error_code = e.response.json().get("error")
                except (ValueError, AttributeError):
                    error_code = None
                if error_code == "invalid_grant":
                    logger.warning(
                        "Discord rejected the stored refresh token (invalid_grant)"
                    )
                    raise DiscordInvalidRefreshTokenError(
                        "Discord refresh token is invalid or expired"
                    ) from e
            logger.error(f"Failed to refresh access token: {e}")
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            return None
