# Running BinkoBot on Replit

The Replit workflow starts the Flask dashboard and Discord bot together:

```bash
RUN_MODE=both python3 main.py
```

The dashboard is available in the Preview pane on port 5000. Replit provides
the database connection automatically. `SESSION_SECRET` and
`DISCORD_BOT_TOKEN` are configured as Replit Secrets.

To launch only the dashboard for local troubleshooting, run:

```bash
RUN_MODE=web python3 main.py
```

## Discord OAuth setup

Discord dashboard sign-in requires `DISCORD_CLIENT_ID` and
`DISCORD_CLIENT_SECRET` as Replit Secrets.

### How the callback URI is chosen

`DiscordService._get_redirect_uri()` (in `web/discord_service.py`) resolves
the callback URI at startup using this priority order:

1. **`DISCORD_REDIRECT_URI`** — a regular (non-secret) Replit environment
   variable. Set this only when the app has a *stable* public URL (custom
   domain or published deployment URL). It takes precedence over everything
   else and must exactly match a URI registered in the Discord Developer
   Portal.
2. **`REPLIT_DOMAINS`** — managed by Replit; automatically tracks the
   current domain. Used when `DISCORD_REDIRECT_URI` is not set.
3. **`REPLIT_DEV_DOMAIN`** — secondary Replit-managed fallback.
4. **`http://localhost:5000/auth/callback`** — last resort for purely local
   development.

Note: whichever URI is chosen, Discord only accepts it if that exact URI is
registered in the Discord Developer Portal. The automatic fallbacks keep the
URI in sync with the current domain, but the Portal registration must be
updated by the operator whenever the domain changes.

### Pre-redirect verification (prevents dead-end logins)

Discord validates the redirect URI **before** showing its authorization
page. If the URI the app sends is not registered, users land on an error
page on Discord's own site and the app never gets a chance to explain.

To prevent that dead end, `/auth/login` verifies the effective callback URI
**before** redirecting:

1. **Primary check** — the app queries Discord's API
   (`GET /applications/@me`, authenticated with the bot token) for the list
   of redirect URIs actually registered for this application, and requires
   an exact match against the URI it is about to send. Lookups are cached
   for 5 minutes; failures are never cached.
2. **Fallback check** — if Discord cannot be queried (no bot token, API
   error), an explicitly set `DISCORD_REDIRECT_URI` must exactly match
   `https://<current-request-host>/auth/callback` (full URI: scheme, host,
   and path).

On any mismatch the login is stopped and the error names:
- the URI the app would have sent,
- the exact URI to register (`https://<current-domain>/auth/callback`),
- the URIs currently registered in Discord (when known), and
- instructions to update `DISCORD_REDIRECT_URI` and the Discord Developer
  Portal (OAuth2 → Redirects).

The OAuth callback error flashes (denied authorization, failed token
exchange) include the same exact-URI guidance.

### Operator checklist when the domain changes

1. In the **Discord Developer Portal → OAuth2 → Redirects**, register
   `https://<new-domain>/auth/callback` and remove the outdated entry.
2. If `DISCORD_REDIRECT_URI` is set, update it to the same value — or
   delete it in development so the `REPLIT_DOMAINS` fallback derives the
   URI automatically.

Do **not** set `DISCORD_REDIRECT_URI` to a temporary dev Preview URL
(`*.replit.dev` with a session hash) — those change between sessions and a
pinned stale value overrides the automatic fallback. Use it only for stable
domains.
