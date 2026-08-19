---
name: Discord OAuth redirect URI lesson
description: Discord validates redirect URIs before its authorization page renders; the registered list is readable but not writable via API
---

# Discord OAuth redirect URI lesson

Discord validates the OAuth2 redirect URI **before** rendering its authorization page. An unregistered or stale URI dead-ends users on Discord's own error page; the app's callback route never runs, so callback-side error handling cannot surface or repair this failure.

**Why:** Redirect-URI drift (e.g. after a domain change) is invisible to the app unless it checks *before* redirecting. `GET /applications/@me` (bot-token auth) returns the registered `redirect_uris`, enabling pre-redirect verification — but `PATCH /applications/@me` silently ignores `redirect_uris` (returns 200 without applying), so automatic re-registration is impossible; only the Developer Portal can change the list.

**How to apply:** Any protection against redirect-URI mismatch must run before the redirect to Discord — verify the effective URI against Discord's registered list (exact full-URI match: scheme, host, path) and surface operator instructions on mismatch. Never pin a redirect-URI env var to a volatile dev preview domain, since an explicit value overrides domain-tracking fallbacks.
