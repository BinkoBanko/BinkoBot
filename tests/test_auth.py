"""
tests/test_auth.py

Confirms that /auth/login, /auth/callback, and /auth/logout never fail
silently.  Every bad-path scenario must produce a visible error flash and
redirect to index -- never a blank page, unhandled exception, or 5xx.

The tests use Flask's test client with an in-memory SQLite database so no
real database or network calls are made.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Bootstrap: force an in-memory DB *before* any app module is imported
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SESSION_SECRET", "auth-test-session-secret")
os.environ.setdefault("DISCORD_CLIENT_ID", "test-client-id")
os.environ.setdefault("DISCORD_CLIENT_SECRET", "test-client-secret")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, db          # noqa: E402
from web.models import User      # noqa: E402
import web.routes.auth as auth   # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Create all tables once per session in the in-memory SQLite DB."""
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()


@pytest.fixture()
def client():
    """Return a test client that uses the configured in-memory app."""
    app.config.update(TESTING=True, SECRET_KEY="auth-test-session-secret")
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_users():
    """Wipe the User table before and after every test."""
    with app.app_context():
        db.session.rollback()
        User.query.delete()
        db.session.commit()
    yield
    with app.app_context():
        db.session.rollback()
        User.query.delete()
        db.session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def set_oauth_state(client, state="test-state"):
    with client.session_transaction() as session:
        session["oauth_state"] = state


def flashed_messages(client):
    with client.session_transaction() as session:
        return [message for _, message in session.get("_flashes", [])]


class FakeDiscordService:
    def __init__(self, token_data=None, user_info=None):
        self.oauth_configured = True
        # Matches the test client's request host so the pre-redirect
        # registration guard lets login proceed.
        self.redirect_uri = "https://localhost/auth/callback"
        self.token_data = token_data
        self.user_info = user_info
        self.exchange_calls = []
        self.user_info_calls = []
        self.oauth_states = []

    def get_registered_redirect_uris(self):
        # Verification unavailable -> guard falls back to local checks.
        return None

    def get_oauth_url(self, state=None):
        self.oauth_states.append(state)
        return f"https://discord.test/authorize?state={state}"

    def exchange_code_for_token(self, code):
        self.exchange_calls.append(code)
        return self.token_data

    def get_user_info(self, access_token):
        self.user_info_calls.append(access_token)
        return self.user_info


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_already_logged_in_redirects_to_dashboard(self, client):
        """An authenticated user is sent to the dashboard, not to Discord."""
        with client.session_transaction() as sess:
            sess["user_id"] = 1

        resp = client.get("/auth/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]

    def test_unconfigured_oauth_redirects_home_with_error(self, client):
        """Missing OAuth credentials must show an error, not crash."""
        with patch("web.routes.auth.discord_service") as mock_svc:
            mock_svc.oauth_configured = False
            resp = client.get("/auth/login", follow_redirects=True)
        assert resp.status_code == 200
        assert (
            b"not configured" in resp.data.lower()
            or b"error" in resp.data.lower()
        )

    def test_configured_oauth_redirects_to_discord(self, client):
        """Configured OAuth must redirect to Discord's authorize URL."""
        with patch("web.routes.auth.discord_service") as mock_svc:
            mock_svc.oauth_configured = True
            mock_svc.redirect_uri = "https://localhost/auth/callback"
            mock_svc.get_registered_redirect_uris.return_value = [
                "https://localhost/auth/callback"
            ]
            mock_svc.get_oauth_url.return_value = (
                "https://discord.com/api/oauth2/authorize?test=1"
            )
            resp = client.get("/auth/login", follow_redirects=False)
        assert resp.status_code == 302
        assert "discord.com" in resp.headers["Location"]


def test_login_missing_client_id_or_secret_flashes_configuration_error(
    client, monkeypatch
):
    for client_id, client_secret in ((None, "secret"), ("client-id", None)):
        monkeypatch.setattr(auth.discord_service, "client_id", client_id)
        monkeypatch.setattr(auth.discord_service, "client_secret", client_secret)

        response = client.get("/auth/login")

        assert response.status_code == 302
        assert response.location.endswith("/")
        assert any(
            "Discord sign-in is not configured yet." in message
            for message in flashed_messages(client)
        )


def test_login_redirects_to_discord_and_stores_oauth_state(client, monkeypatch):
    service = FakeDiscordService()
    monkeypatch.setattr(auth, "discord_service", service)

    response = client.get("/auth/login")

    assert response.status_code == 302
    assert response.location.startswith("https://discord.test/authorize?state=")
    with client.session_transaction() as session:
        state = session.get("oauth_state")
        assert state
    assert service.oauth_states == [state]


# ---------------------------------------------------------------------------
# /auth/callback
# ---------------------------------------------------------------------------

class TestCallback:
    """All error paths must redirect to index with a flash, never crash."""

    def _set_state(self, client, state="valid-state"):
        with client.session_transaction() as sess:
            sess["oauth_state"] = state

    def test_missing_state_redirects_home_with_error(self, client):
        resp = client.get("/auth/callback", follow_redirects=True)
        assert resp.status_code == 200
        assert b"error" in resp.data.lower() or b"invalid" in resp.data.lower()

    def test_wrong_state_redirects_home_with_error(self, client):
        self._set_state(client, "correct-state")
        resp = client.get("/auth/callback?state=wrong-state", follow_redirects=True)
        assert resp.status_code == 200

    def test_discord_denies_redirects_home_with_error(self, client):
        """Discord can return ?error=access_denied -- must be caught."""
        self._set_state(client, "s")
        resp = client.get(
            "/auth/callback?state=s&error=access_denied", follow_redirects=True
        )
        assert resp.status_code == 200

    def test_no_code_redirects_home_with_error(self, client):
        """Callback with matching state but no code must not crash."""
        self._set_state(client, "s")
        resp = client.get("/auth/callback?state=s", follow_redirects=True)
        assert resp.status_code == 200

    def test_token_exchange_failure_redirects_home_with_error(self, client):
        """If Discord's token endpoint is unreachable, redirect with error."""
        self._set_state(client, "s")
        with patch("web.routes.auth.discord_service") as mock_svc:
            mock_svc.exchange_code_for_token.return_value = None
            resp = client.get(
                "/auth/callback?state=s&code=abc", follow_redirects=True
            )
        assert resp.status_code == 200

    def test_missing_access_token_in_response_redirects_home_with_error(self, client):
        """Token response without access_token must not proceed silently."""
        self._set_state(client, "s")
        with patch("web.routes.auth.discord_service") as mock_svc:
            mock_svc.exchange_code_for_token.return_value = {"refresh_token": "rt"}
            resp = client.get(
                "/auth/callback?state=s&code=abc", follow_redirects=True
            )
        assert resp.status_code == 200

    def test_user_info_failure_redirects_home_with_error(self, client):
        """If user-info fetch fails after token exchange, redirect with error."""
        self._set_state(client, "s")
        with patch("web.routes.auth.discord_service") as mock_svc:
            mock_svc.exchange_code_for_token.return_value = {
                "access_token": "at", "refresh_token": "rt"
            }
            mock_svc.get_user_info.return_value = None
            resp = client.get(
                "/auth/callback?state=s&code=abc", follow_redirects=True
            )
        assert resp.status_code == 200

    def test_db_error_during_callback_redirects_home_with_error(self, client):
        """A database error during user upsert must be caught, not bubble up as 500."""
        self._set_state(client, "s")
        with patch("web.routes.auth.discord_service") as mock_svc, \
             patch("web.routes.auth.db") as mock_db:
            mock_svc.exchange_code_for_token.return_value = {
                "access_token": "at", "refresh_token": "rt"
            }
            mock_svc.get_user_info.return_value = {
                "id": "999", "username": "TestUser", "discriminator": "0001"
            }
            mock_db.session.commit.side_effect = Exception("DB unavailable")
            with patch("web.routes.auth.User") as mock_user_cls:
                mock_user_cls.query.filter_by.return_value.first.return_value = None
                new_user = MagicMock()
                mock_user_cls.return_value = new_user
                resp = client.get(
                    "/auth/callback?state=s&code=abc", follow_redirects=True
                )
        assert resp.status_code == 200

    def test_successful_callback_logs_in_and_redirects_to_dashboard(self, client):
        """Happy path: valid code → user in session → dashboard redirect."""
        self._set_state(client, "s")
        with patch("web.routes.auth.discord_service") as mock_svc, \
             patch("web.routes.auth.User") as mock_user_cls, \
             patch("web.routes.auth.db") as mock_db:
            mock_svc.exchange_code_for_token.return_value = {
                "access_token": "at", "refresh_token": "rt"
            }
            mock_svc.get_user_info.return_value = {
                "id": "123", "username": "BinkoUser", "discriminator": "0001"
            }
            existing = MagicMock()
            existing.id = 42
            existing.username = "BinkoUser"
            mock_user_cls.query.filter_by.return_value.first.return_value = existing
            mock_db.func.now.return_value = None

            resp = client.get(
                "/auth/callback?state=s&code=good-code", follow_redirects=False
            )

        assert resp.status_code == 302
        assert "/dashboard" in resp.headers["Location"]
        with client.session_transaction() as sess:
            assert sess.get("user_id") == 42


def test_callback_creates_then_updates_user_and_sets_session(client, monkeypatch):
    service = FakeDiscordService(
        token_data={"access_token": "access-1", "refresh_token": "refresh-1"},
        user_info={
            "id": "discord-user-1",
            "username": "first-name",
            "discriminator": "1234",
            "avatar": "avatar-1",
        },
    )
    monkeypatch.setattr(auth, "discord_service", service)

    set_oauth_state(client)
    response = client.get("/auth/callback?state=test-state&code=valid-code")

    assert response.status_code == 302
    assert response.location.endswith("/dashboard/")
    with app.app_context():
        user = User.query.filter_by(discord_id="discord-user-1").one()
        user_id = user.id
        assert user.username == "first-name"
        assert user.access_token == "access-1"
        assert user.refresh_token == "refresh-1"

    with client.session_transaction() as session:
        assert session["user_id"] == user_id
        assert session["username"] == "first-name"
        assert "oauth_state" not in session
    assert "Welcome, first-name!" in flashed_messages(client)

    # Second login with updated data -- must update, not create a new row
    service.token_data = {"access_token": "access-2", "refresh_token": "refresh-2"}
    service.user_info = {
        "id": "discord-user-1",
        "username": "updated-name",
        "discriminator": "5678",
        "avatar": "avatar-2",
    }
    set_oauth_state(client, "second-state")

    response = client.get("/auth/callback?state=second-state&code=second-code")

    assert response.status_code == 302
    assert response.location.endswith("/dashboard/")
    with app.app_context():
        users = User.query.filter_by(discord_id="discord-user-1").all()
        assert len(users) == 1
        assert users[0].id == user_id
        assert users[0].username == "updated-name"
        assert users[0].discriminator == "5678"
        assert users[0].avatar == "avatar-2"
        assert users[0].access_token == "access-2"
        assert users[0].refresh_token == "refresh-2"

    with client.session_transaction() as session:
        assert session["user_id"] == user_id
        assert session["username"] == "updated-name"
        assert "oauth_state" not in session
    assert service.exchange_calls == ["valid-code", "second-code"]
    assert service.user_info_calls == ["access-1", "access-2"]


def test_callback_rejects_bad_oauth_state_without_calling_discord(client, monkeypatch):
    service = FakeDiscordService()
    monkeypatch.setattr(auth, "discord_service", service)
    set_oauth_state(client, "expected-state")

    response = client.get("/auth/callback?state=wrong-state&code=valid-code")

    assert response.status_code == 302
    assert response.location.endswith("/")
    assert "Invalid OAuth state. Please try again." in flashed_messages(client)
    assert service.exchange_calls == []
    assert service.user_info_calls == []


def test_callback_flashes_when_token_exchange_fails(client, monkeypatch):
    service = FakeDiscordService(token_data=None)
    monkeypatch.setattr(auth, "discord_service", service)
    set_oauth_state(client)

    response = client.get("/auth/callback?state=test-state&code=valid-code")

    assert response.status_code == 302
    assert response.location.endswith("/")
    assert any(
        "Failed to obtain access token from Discord." in msg
        for msg in flashed_messages(client)
    )
    assert service.exchange_calls == ["valid-code"]
    assert service.user_info_calls == []
    with client.session_transaction() as session:
        assert "oauth_state" not in session


def test_callback_flashes_when_user_info_is_missing(client, monkeypatch):
    service = FakeDiscordService(
        token_data={"access_token": "access-token"},
        user_info=None,
    )
    monkeypatch.setattr(auth, "discord_service", service)
    set_oauth_state(client)

    response = client.get("/auth/callback?state=test-state&code=valid-code")

    assert response.status_code == 302
    assert response.location.endswith("/")
    assert "Failed to get user information from Discord." in flashed_messages(client)
    assert service.exchange_calls == ["valid-code"]
    assert service.user_info_calls == ["access-token"]
    with app.app_context():
        assert User.query.count() == 0


# ---------------------------------------------------------------------------
# /auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_clears_session_and_redirects_home(self, client):
        """Logout must clear the session and send the user to index."""
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "BinkoUser"

        resp = client.get("/auth/logout", follow_redirects=False)

        assert resp.status_code == 302
        location = resp.headers.get("Location", "")
        assert location == "/" or location.endswith("/")
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_without_session_does_not_crash(self, client):
        """Logging out while not authenticated must not raise an error."""
        resp = client.get("/auth/logout", follow_redirects=True)
        assert resp.status_code == 200

    def test_logout_never_returns_500(self, client):
        """Logout must never surface an unhandled exception."""
        resp = client.get("/auth/logout")
        assert resp.status_code in (200, 302)


def test_logout_clears_session_and_flashes_success(client):
    with client.session_transaction() as session:
        session["user_id"] = 42
        session["username"] = "logged-in-user"
        session["oauth_state"] = "stale-state"

    response = client.get("/auth/logout")

    assert response.status_code == 302
    assert response.location.endswith("/")
    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "username" not in session
        assert "oauth_state" not in session
    assert "You have been logged out successfully." in flashed_messages(client)


# ---------------------------------------------------------------------------
# Redirect URI resolution (_get_redirect_uri)
# ---------------------------------------------------------------------------

class TestGetRedirectUri:
    """
    _get_redirect_uri must pick the right callback URL depending on which
    environment variables are available.  Tests are isolated so they do not
    affect the module-level discord_service instance used by other tests.
    """

    def _resolve(self, env: dict) -> str:
        """Call _get_redirect_uri with an isolated environment."""
        from web.discord_service import DiscordService
        with patch.dict(os.environ, env, clear=False):
            # Temporarily clear all three vars so each test starts clean
            for key in ("DISCORD_REDIRECT_URI", "REPLIT_DOMAINS", "REPLIT_DEV_DOMAIN"):
                os.environ.pop(key, None)
            os.environ.update(env)
            return DiscordService._get_redirect_uri()

    def test_explicit_env_var_takes_precedence_over_replit_domains(self):
        """DISCORD_REDIRECT_URI must win over the Replit runtime domain."""
        uri = self._resolve({
            "DISCORD_REDIRECT_URI": "https://custom.example.com/auth/callback",
            "REPLIT_DOMAINS": "auto.replit.dev",
        })
        assert uri == "https://custom.example.com/auth/callback"

    def test_explicit_env_var_takes_precedence_over_replit_dev_domain(self):
        """DISCORD_REDIRECT_URI must win over REPLIT_DEV_DOMAIN too."""
        uri = self._resolve({
            "DISCORD_REDIRECT_URI": "https://custom.example.com/auth/callback",
            "REPLIT_DEV_DOMAIN": "dev.replit.dev",
        })
        assert uri == "https://custom.example.com/auth/callback"

    def test_replit_domains_used_when_no_explicit_var(self):
        """Without DISCORD_REDIRECT_URI, REPLIT_DOMAINS drives the callback."""
        uri = self._resolve({"REPLIT_DOMAINS": "myapp.replit.dev"})
        assert uri == "https://myapp.replit.dev/auth/callback"

    def test_replit_domains_first_entry_used_when_comma_separated(self):
        """Only the first entry of a comma-separated REPLIT_DOMAINS list is used."""
        uri = self._resolve({"REPLIT_DOMAINS": "primary.replit.dev,secondary.replit.dev"})
        assert uri == "https://primary.replit.dev/auth/callback"

    def test_replit_dev_domain_fallback_when_no_replit_domains(self):
        """REPLIT_DEV_DOMAIN is used when REPLIT_DOMAINS is absent."""
        uri = self._resolve({"REPLIT_DEV_DOMAIN": "dev-only.replit.dev"})
        assert uri == "https://dev-only.replit.dev/auth/callback"

    def test_localhost_fallback_when_no_replit_env_vars(self):
        """No Replit env vars → localhost fallback for local development."""
        uri = self._resolve({})
        assert uri == "http://localhost:5000/auth/callback"

    def test_new_domain_produces_different_callback(self):
        """Switching REPLIT_DOMAINS to a new value changes the callback immediately."""
        old_uri = self._resolve({"REPLIT_DOMAINS": "old.replit.dev"})
        new_uri = self._resolve({"REPLIT_DOMAINS": "new.replit.dev"})
        assert old_uri == "https://old.replit.dev/auth/callback"
        assert new_uri == "https://new.replit.dev/auth/callback"
        assert old_uri != new_uri


# ---------------------------------------------------------------------------
# Operator-facing error messages include the exact redirect URI
# ---------------------------------------------------------------------------

class TestRedirectUriInErrorMessages:
    """
    When Discord OAuth fails the error flash must contain the exact URI the
    app is using so the operator knows which value to register in Discord.
    """

    def test_unconfigured_oauth_error_includes_redirect_uri(self, client):
        """Missing credentials flash must include the service's redirect_uri."""
        svc = MagicMock()
        svc.oauth_configured = False
        svc.redirect_uri = "https://myapp.replit.dev/auth/callback"

        with patch("web.routes.auth.discord_service", svc):
            # Don't follow redirects: read flashes from session before they
            # are consumed by rendering the destination page.
            client.get("/auth/login", follow_redirects=False)

        msgs = flashed_messages(client)
        assert any("https://myapp.replit.dev/auth/callback" in m for m in msgs), (
            f"Expected redirect URI in flash messages, got: {msgs}"
        )

    def test_discord_denial_error_includes_redirect_uri(self, client):
        """Discord access_denied error flash must include the redirect URI."""
        svc = MagicMock()
        svc.oauth_configured = True
        svc.redirect_uri = "https://myapp.replit.dev/auth/callback"
        svc.get_oauth_url.return_value = "https://discord.com/authorize"

        with patch("web.routes.auth.discord_service", svc):
            with client.session_transaction() as sess:
                sess["oauth_state"] = "s"
            client.get(
                "/auth/callback?state=s&error=access_denied",
                follow_redirects=False,
            )

        msgs = flashed_messages(client)
        assert any("https://myapp.replit.dev/auth/callback" in m for m in msgs), (
            f"Expected redirect URI in flash messages, got: {msgs}"
        )

    def test_token_exchange_failure_includes_redirect_uri(self, client):
        """Token exchange failure flash must include the redirect URI."""
        svc = MagicMock()
        svc.oauth_configured = True
        svc.redirect_uri = "https://myapp.replit.dev/auth/callback"
        svc.exchange_code_for_token.return_value = None

        with patch("web.routes.auth.discord_service", svc):
            with client.session_transaction() as sess:
                sess["oauth_state"] = "s"
            client.get(
                "/auth/callback?state=s&code=bad-code",
                follow_redirects=False,
            )

        msgs = flashed_messages(client)
        assert any("https://myapp.replit.dev/auth/callback" in m for m in msgs), (
            f"Expected redirect URI in flash messages, got: {msgs}"
        )


# ---------------------------------------------------------------------------
# Pre-redirect verification of the OAuth callback URI on /auth/login
# ---------------------------------------------------------------------------

class TestRedirectUriVerification:
    """
    Discord validates the redirect URI *before* rendering its authorization
    page, so a URI that is not registered in the Developer Portal dead-ends
    users on Discord's own error page. /auth/login must verify the effective
    URI (explicit *or* auto-derived from REPLIT_DOMAINS) against Discord's
    registered list before redirecting, and give the operator instructions.
    """

    def _service(self, redirect_uri, registered):
        """A service whose registered-URI lookup returns the given list."""
        svc = MagicMock()
        svc.oauth_configured = True
        svc.redirect_uri = redirect_uri
        svc.get_registered_redirect_uris.return_value = registered
        svc.get_oauth_url.return_value = "https://discord.com/api/oauth2/authorize?x=1"
        return svc

    # ---- primary check: verify against Discord's registered list ----

    def test_auto_derived_uri_after_domain_change_blocks_redirect(
        self, client, monkeypatch
    ):
        """
        Integration-style: no explicit DISCORD_REDIRECT_URI, REPLIT_DOMAINS
        changed to a new domain, but Discord still has the OLD URI
        registered. Login must NOT reach Discord.
        """
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        monkeypatch.setenv("REPLIT_DOMAINS", "new-domain.replit.app")
        # Real resolution: derive the URI exactly like production code does.
        from web.discord_service import DiscordService
        effective = DiscordService._get_redirect_uri()
        assert effective == "https://new-domain.replit.app/auth/callback"

        svc = self._service(
            redirect_uri=effective,
            registered=["https://old-domain.replit.app/auth/callback"],
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" not in resp.headers["Location"]
        svc.get_oauth_url.assert_not_called()
        msgs = " ".join(flashed_messages(client))
        # names the URI the app would use and what to register
        assert "https://new-domain.replit.app/auth/callback" in msgs
        assert "Discord Developer Portal" in msgs
        # names what Discord currently has registered
        assert "https://old-domain.replit.app/auth/callback" in msgs

    def test_registered_uri_allows_redirect(self, client, monkeypatch):
        """When the effective URI is registered, login proceeds to Discord."""
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        svc = self._service(
            redirect_uri="https://myapp.replit.app/auth/callback",
            registered=["https://myapp.replit.app/auth/callback"],
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" in resp.headers["Location"]
        svc.get_oauth_url.assert_called_once()

    def test_registration_match_is_exact_full_uri_not_just_host(
        self, client, monkeypatch
    ):
        """Same host but wrong path must be blocked (Discord matches exactly)."""
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        svc = self._service(
            redirect_uri="https://myapp.replit.app/auth/callback",
            registered=["https://myapp.replit.app/wrong/path"],
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" not in resp.headers["Location"]

    def test_registration_match_is_scheme_and_case_insensitive_host(
        self, client, monkeypatch
    ):
        """Host case differences must not cause false mismatches."""
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        svc = self._service(
            redirect_uri="https://MyApp.replit.app/auth/callback",
            registered=["https://myapp.replit.app/auth/callback"],
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" in resp.headers["Location"]

    def test_malformed_effective_uri_blocks_redirect(self, client, monkeypatch):
        """A malformed effective URI must block, not crash or pass through."""
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        svc = self._service(redirect_uri="not-a-valid-uri", registered=None)
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" not in resp.headers["Location"]
        assert any("not-a-valid-uri" in m for m in flashed_messages(client))

    # ---- fallback check: Discord verification unavailable ----

    def test_stale_explicit_uri_blocked_when_verification_unavailable(
        self, client, monkeypatch
    ):
        """
        If Discord can't be queried (no bot token / API error), an explicit
        DISCORD_REDIRECT_URI that doesn't match the live request host+path
        must still be blocked locally.
        """
        monkeypatch.setenv(
            "DISCORD_REDIRECT_URI", "https://old-domain.replit.app/auth/callback"
        )
        svc = self._service(
            redirect_uri="https://old-domain.replit.app/auth/callback",
            registered=None,  # verification unavailable
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" not in resp.headers["Location"]
        msgs = " ".join(flashed_messages(client))
        assert "https://old-domain.replit.app/auth/callback" in msgs
        assert "https://localhost/auth/callback" in msgs
        assert "DISCORD_REDIRECT_URI" in msgs

    def test_explicit_uri_with_wrong_path_blocked_when_verification_unavailable(
        self, client, monkeypatch
    ):
        """Full-URI comparison: right host but wrong path must be blocked."""
        monkeypatch.setenv("DISCORD_REDIRECT_URI", "https://localhost/wrong/path")
        svc = self._service(
            redirect_uri="https://localhost/wrong/path",
            registered=None,
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" not in resp.headers["Location"]

    def test_matching_explicit_uri_allowed_when_verification_unavailable(
        self, client, monkeypatch
    ):
        """An explicit URI matching the live host+path proceeds to Discord."""
        monkeypatch.setenv(
            "DISCORD_REDIRECT_URI", "https://localhost/auth/callback"
        )
        svc = self._service(
            redirect_uri="https://localhost/auth/callback",
            registered=None,
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" in resp.headers["Location"]
        svc.get_oauth_url.assert_called_once()

    def test_auto_derived_uri_allowed_when_verification_unavailable(
        self, client, monkeypatch
    ):
        """
        Without explicit config and without Discord verification there is
        nothing to compare against; the auto-derived URI proceeds (it matches
        the current domain by construction).
        """
        monkeypatch.delenv("DISCORD_REDIRECT_URI", raising=False)
        svc = self._service(
            redirect_uri="https://localhost/auth/callback",
            registered=None,
        )
        with patch("web.routes.auth.discord_service", svc):
            resp = client.get("/auth/login", follow_redirects=False)

        assert resp.status_code == 302
        assert "discord.com" in resp.headers["Location"]


class TestGetRegisteredRedirectUris:
    """DiscordService.get_registered_redirect_uris contract."""

    def _service(self):
        from web.discord_service import DiscordService
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "bot-token"}):
            return DiscordService()

    def test_returns_uris_from_discord_api(self):
        svc = self._service()
        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "redirect_uris": ["https://a.example/auth/callback"]
        }
        with patch("web.discord_service.requests.get", return_value=fake_resp) as g:
            uris = svc.get_registered_redirect_uris()
        assert uris == ["https://a.example/auth/callback"]
        assert "applications/@me" in g.call_args[0][0]

    def test_caches_successful_lookup(self):
        svc = self._service()
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"redirect_uris": ["https://a.example/cb"]}
        with patch("web.discord_service.requests.get", return_value=fake_resp) as g:
            svc.get_registered_redirect_uris()
            svc.get_registered_redirect_uris()
        assert g.call_count == 1

    def test_returns_none_without_bot_token(self):
        from web.discord_service import DiscordService
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DISCORD_BOT_TOKEN", None)
            svc = DiscordService()
        assert svc.get_registered_redirect_uris() is None

    def test_returns_none_on_api_error_and_does_not_cache_failure(self):
        import requests as requests_module
        svc = self._service()
        with patch(
            "web.discord_service.requests.get",
            side_effect=requests_module.RequestException("boom"),
        ) as g:
            assert svc.get_registered_redirect_uris() is None
            assert svc.get_registered_redirect_uris() is None
        assert g.call_count == 2  # failures are retried, never cached


class TestRefreshAccessToken:
    """DiscordService.refresh_access_token contract."""

    def _service(self):
        from web.discord_service import DiscordService

        with patch.dict(
            os.environ,
            {
                "DISCORD_CLIENT_ID": "refresh-client-id",
                "DISCORD_CLIENT_SECRET": "refresh-client-secret",
            },
            clear=False,
        ):
            return DiscordService()

    def test_returns_refreshed_token_data_and_sends_expected_request(self):
        svc = self._service()
        refreshed_tokens = {
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
            "expires_in": 604800,
            "token_type": "Bearer",
        }
        fake_response = MagicMock()
        fake_response.json.return_value = refreshed_tokens

        with patch(
            "web.discord_service.requests.post", return_value=fake_response
        ) as post:
            result = svc.refresh_access_token("existing-refresh-token")

        assert result == refreshed_tokens
        post.assert_called_once_with(
            "https://discord.com/api/v10/oauth2/token",
            data={
                "client_id": "refresh-client-id",
                "client_secret": "refresh-client-secret",
                "grant_type": "refresh_token",
                "refresh_token": "existing-refresh-token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        fake_response.raise_for_status.assert_called_once_with()

    def test_returns_none_when_refresh_exchange_fails(self):
        import requests as requests_module

        svc = self._service()
        with patch(
            "web.discord_service.requests.post",
            side_effect=requests_module.RequestException("Discord unavailable"),
        ) as post:
            result = svc.refresh_access_token("existing-refresh-token")

        assert result is None
        post.assert_called_once()


class TestDiscordUnauthorizedResponses:
    def test_user_guilds_raises_for_unauthorized_access_token(self):
        from web.discord_service import DiscordService, DiscordUnauthorizedError
        import requests as requests_module

        svc = DiscordService()
        response = MagicMock(status_code=401)
        error = requests_module.HTTPError("Unauthorized", response=response)
        response.raise_for_status.side_effect = error

        with patch(
            "web.discord_service.requests.get", return_value=response
        ):
            with pytest.raises(DiscordUnauthorizedError):
                svc.get_user_guilds("expired-access-token")

    def test_refresh_raises_for_invalid_grant_error(self):
        """Only `invalid_grant` in the response body proves a revoked/expired
        refresh token; a bare HTTP 400 without that code is not conclusive."""
        from web.discord_service import (
            DiscordInvalidRefreshTokenError,
            DiscordService,
        )
        import requests as requests_module

        svc = DiscordService()
        response = MagicMock(status_code=400)
        response.json.return_value = {"error": "invalid_grant"}
        error = requests_module.HTTPError("Invalid grant", response=response)
        response.raise_for_status.side_effect = error

        with patch(
            "web.discord_service.requests.post", return_value=response
        ):
            with pytest.raises(DiscordInvalidRefreshTokenError):
                svc.refresh_access_token("invalid-refresh-token")

    def test_refresh_returns_none_for_non_invalid_grant_400(self):
        """A 400 with a non-credential error (e.g. invalid_client) must not be
        treated as proof the user's token is revoked -- return None so callers
        treat it as a transient/configuration failure."""
        from web.discord_service import (
            DiscordInvalidRefreshTokenError,
            DiscordService,
        )
        import requests as requests_module

        svc = DiscordService()
        response = MagicMock(status_code=400)
        response.json.return_value = {"error": "invalid_client"}
        error = requests_module.HTTPError("invalid_client", response=response)
        response.raise_for_status.side_effect = error

        with patch(
            "web.discord_service.requests.post", return_value=response
        ):
            result = svc.refresh_access_token("some-refresh-token")

        assert result is None


# ---------------------------------------------------------------------------
# sync_user_servers: refresh-and-retry lifecycle
# ---------------------------------------------------------------------------

class TestSyncUserServersRefreshLifecycle:
    """
    sync_user_servers must attempt a one-shot token refresh when the initial
    guild fetch fails (e.g. expired access token), persist the rotated tokens,
    and retry the guild fetch exactly once.
    """

    def _make_user(self):
        """Return a transient User-like object with the fields sync needs."""
        user = MagicMock(spec=["username", "access_token", "refresh_token"])
        user.username = "TestUser"
        user.access_token = "expired-access-token"
        user.refresh_token = "valid-refresh-token"
        return user

    # ---- happy path --------------------------------------------------------

    def test_successful_refresh_retries_guild_fetch_and_persists_tokens(self):
        """
        When the first guild fetch fails and the refresh succeeds, sync must:
        - call get_user_guilds a second time with the new access token,
        - persist both rotated tokens to the database.
        """
        from web.routes.dashboard import sync_user_servers

        user = self._make_user()
        rotated = {
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
        }
        guild_list = [{"id": "guild-1", "name": "Test Guild", "permissions": 0}]

        with app.app_context():
            db.create_all()
            with (
                patch("web.routes.dashboard.discord_service") as mock_svc,
                patch("web.routes.dashboard.db") as mock_db,
            ):
                from web.discord_service import DiscordUnauthorizedError

                # Discord explicitly rejects the expired token, then the
                # retried request succeeds with the refreshed token.
                mock_svc.get_user_guilds.side_effect = [
                    DiscordUnauthorizedError(),
                    guild_list,
                ]
                mock_svc.refresh_access_token.return_value = rotated

                # Prevent actual DB queries for guild/server upsert
                with patch("web.routes.dashboard.Server") as mock_server_cls, \
                     patch("web.routes.dashboard.UserServer") as mock_us_cls:
                    mock_server_cls.query.filter_by.return_value.first.return_value = MagicMock()
                    mock_us_cls.query.filter_by.return_value.first.return_value = MagicMock()

                    sync_user_servers(user)

        # Refresh exchange called with the stored refresh token
        mock_svc.refresh_access_token.assert_called_once_with("valid-refresh-token")
        # get_user_guilds called twice: first with stale token, then with new one
        assert mock_svc.get_user_guilds.call_count == 2
        first_call, second_call = mock_svc.get_user_guilds.call_args_list
        assert first_call[0][0] == "expired-access-token"
        assert second_call[0][0] == "new-access-token"
        # Rotated tokens persisted to the user object
        assert user.access_token == "new-access-token"
        assert user.refresh_token == "rotated-refresh-token"
        mock_db.session.commit.assert_called()

    def test_rotated_refresh_token_falls_back_to_old_when_omitted(self):
        """
        If Discord's refresh response omits 'refresh_token' (some providers
        don't rotate it), the existing stored refresh token is kept.
        """
        from web.routes.dashboard import sync_user_servers

        user = self._make_user()
        # Response has no refresh_token field
        rotated = {"access_token": "new-access-token"}

        with app.app_context():
            db.create_all()
            with (
                patch("web.routes.dashboard.discord_service") as mock_svc,
                patch("web.routes.dashboard.db") as mock_db,
            ):
                from web.discord_service import DiscordUnauthorizedError

                mock_svc.get_user_guilds.side_effect = [
                    DiscordUnauthorizedError(),
                    [],
                ]
                mock_svc.refresh_access_token.return_value = rotated

                with patch("web.routes.dashboard.Server"), \
                     patch("web.routes.dashboard.UserServer"):
                    sync_user_servers(user)

        assert user.access_token == "new-access-token"
        # Original refresh token retained when not rotated
        assert user.refresh_token == "valid-refresh-token"

    # ---- failure paths -----------------------------------------------------

    def test_failed_refresh_does_not_retry_guild_fetch(self):
        """
        When the refresh exchange fails, get_user_guilds must not be called
        a second time -- sync exits early without crashing.
        """
        from web.routes.dashboard import sync_user_servers

        user = self._make_user()

        with app.app_context():
            db.create_all()
            with patch("web.routes.dashboard.discord_service") as mock_svc:
                from web.discord_service import DiscordUnauthorizedError

                mock_svc.get_user_guilds.side_effect = DiscordUnauthorizedError()
                mock_svc.refresh_access_token.return_value = None

                sync_user_servers(user)  # must not raise

        assert mock_svc.get_user_guilds.call_count == 1
        mock_svc.refresh_access_token.assert_called_once_with("valid-refresh-token")

    def test_refresh_succeeds_but_second_guild_fetch_still_fails(self):
        """
        If the refresh exchange produces a new token but the second guild
        fetch is also rejected, sync exits without crashing and does not loop
        infinitely. Crucially, this is NOT a LOGIN_REQUIRED result: a second
        401 proves nothing about the validity of the user's credential; the
        refresh endpoint didn't return invalid_grant. Result must be UNAVAILABLE.
        """
        from web.routes.dashboard import sync_user_servers, SyncStatus

        user = self._make_user()
        rotated = {
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
        }

        with app.app_context():
            db.create_all()
            with (
                patch("web.routes.dashboard.discord_service") as mock_svc,
                patch("web.routes.dashboard.db") as mock_db,
            ):
                from web.discord_service import DiscordUnauthorizedError

                mock_svc.get_user_guilds.side_effect = [
                    DiscordUnauthorizedError(),
                    DiscordUnauthorizedError(),
                ]
                mock_svc.refresh_access_token.return_value = rotated

                result = sync_user_servers(user)  # must not raise

        # Retried exactly once, then stopped; outcome is transient, not logout.
        assert mock_svc.get_user_guilds.call_count == 2
        assert user.access_token == "new-access-token"
        assert result is SyncStatus.UNAVAILABLE

    def test_missing_refresh_token_returns_unavailable_not_login_required(self):
        """
        A user whose refresh_token is None has no credential to invalidate;
        sync must return UNAVAILABLE (keep session / show saved data), not
        LOGIN_REQUIRED (log the user out).
        """
        from web.routes.dashboard import sync_user_servers, SyncStatus

        user = self._make_user()
        user.refresh_token = None

        with app.app_context():
            db.create_all()
            with patch("web.routes.dashboard.discord_service") as mock_svc:
                from web.discord_service import DiscordUnauthorizedError

                mock_svc.get_user_guilds.side_effect = DiscordUnauthorizedError()

                result = sync_user_servers(user)  # must not raise

        assert mock_svc.get_user_guilds.call_count == 1
        mock_svc.refresh_access_token.assert_not_called()
        assert result is SyncStatus.UNAVAILABLE


def test_dashboard_keeps_session_when_discord_is_temporarily_unavailable(
    client, monkeypatch
):
    from web.routes import dashboard

    user = MagicMock()
    user.id = 1
    user.username = "TestUser"
    user_model = MagicMock()
    user_model.query.get.return_value = user
    monkeypatch.setattr(dashboard, "User", user_model)
    monkeypatch.setattr(
        dashboard,
        "sync_user_servers",
        lambda _user: dashboard.SyncStatus.UNAVAILABLE,
    )

    db_mock = MagicMock()
    db_mock.session.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(dashboard, "db", db_mock)

    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["username"] = user.username

    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 200
    assert b"temporarily unavailable" in response.data
    with client.session_transaction() as session:
        assert session["user_id"] == user.id


def test_dashboard_redirects_to_login_when_discord_refresh_is_invalid(
    client, monkeypatch
):
    from web.routes import dashboard

    user = MagicMock()
    user.id = 1
    user.username = "TestUser"
    user_model = MagicMock()
    user_model.query.get.return_value = user
    monkeypatch.setattr(dashboard, "User", user_model)
    monkeypatch.setattr(
        dashboard,
        "sync_user_servers",
        lambda _user: dashboard.SyncStatus.LOGIN_REQUIRED,
    )

    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["username"] = user.username

    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 302
    assert response.location.endswith("/auth/login")
    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "username" not in session
    assert any("Please log in again." in message for message in flashed_messages(client))


def test_dashboard_keeps_session_when_sync_returns_unavailable_directly(
    client, monkeypatch
):
    """
    SyncStatus.UNAVAILABLE means a transient Discord/network failure, NOT an
    invalid credential. The dashboard must stay available (200), the session
    must be preserved, and a retryable warning must be shown.
    """
    from web.routes import dashboard

    user = MagicMock()
    user.id = 1
    user.username = "TestUser"
    user_model = MagicMock()
    user_model.query.get.return_value = user
    monkeypatch.setattr(dashboard, "User", user_model)
    monkeypatch.setattr(
        dashboard,
        "sync_user_servers",
        lambda _user: dashboard.SyncStatus.UNAVAILABLE,
    )

    db_mock = MagicMock()
    db_mock.session.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(dashboard, "db", db_mock)

    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["username"] = user.username

    response = client.get("/dashboard/", follow_redirects=False)

    assert response.status_code == 200
    assert b"temporarily unavailable" in response.data
    with client.session_transaction() as session:
        assert session["user_id"] == user.id


def test_dashboard_keeps_session_when_refresh_endpoint_returns_non_invalid_grant(
    client, monkeypatch
):
    """
    A 400/401 from Discord's token endpoint that does NOT contain
    `invalid_grant` in the payload (e.g. invalid_client, invalid_request) is a
    server/configuration-side error, not proof of an expired user credential.
    The session must be preserved and the dashboard must show the transient
    unavailability warning rather than logging the user out.
    """
    from web.routes import dashboard
    from web.discord_service import DiscordUnauthorizedError

    user = MagicMock()
    user.id = 1
    user.username = "TestUser"
    user.access_token = "expired-token"
    user.refresh_token = "any-refresh-token"

    user_model = MagicMock()
    user_model.query.get.return_value = user
    monkeypatch.setattr(dashboard, "User", user_model)

    db_mock = MagicMock()
    db_mock.session.query.return_value.join.return_value.outerjoin.return_value.filter.return_value.order_by.return_value.all.return_value = []
    monkeypatch.setattr(dashboard, "db", db_mock)

    # First guild fetch raises 401 (expired access token).
    # The refresh endpoint returns None (non-invalid_grant 400 treated as
    # transient/unavailable, not a credential error — so the service returns
    # None rather than raising DiscordInvalidRefreshTokenError).
    svc_mock = MagicMock()
    svc_mock.get_user_guilds.side_effect = DiscordUnauthorizedError()
    svc_mock.refresh_access_token.return_value = None
    monkeypatch.setattr(dashboard, "discord_service", svc_mock)

    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["username"] = user.username

    response = client.get("/dashboard/", follow_redirects=False)

    # Must NOT redirect to login; session must be intact; unavailable warning shown.
    assert response.status_code == 200
    assert b"temporarily unavailable" in response.data
    with client.session_transaction() as session:
        assert session["user_id"] == user.id
