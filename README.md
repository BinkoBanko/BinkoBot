# BinkoBot

BinkoBot is a modular Discord companion bot focused on cozy vibes and small community use. The bot uses slash commands and can be customized through its configuration file and environment variables.

## Project Structure

```
bot.py            Discord bot entrypoint
app.py            Flask dashboard entrypoint
main.py           Runs both together (RUN_MODE env var: both/bot/web)
modules/          Discord bot cogs (one file per feature/slash command group)
utils/            Shared bot helpers (e.g. DM-preference-aware sending)
config/           Bot-side constants (valid vibes, etc.)
config.json       Bot runtime settings
data/             JSON/text data the bot reads and writes at runtime
web/              Flask dashboard: models.py, discord_service.py, vibe_analyzer.py,
                  routes/, templates/, static/
tests/            Pytest suite
docs/             Privacy policy and other reference docs
```

## Setup

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd BinkoBot
   ```
2. **Create a virtual environment (optional but recommended)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure the bot**
   - Adjust `config.json` if you need to change the command prefix or other defaults.
   - Set the required environment variables described below.
   - Optionally store them in a `.env` file for automatic loading.

## Environment Variables

- `DISCORD_BOT_TOKEN` – **required**. Your bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `DEV_GUILD_ID` – optional. If set, slash commands sync to this guild first for faster updates.
- `REPLIT` – set to `1` when running on a free-tier Repl so a small ping-able web server starts on port 8080, letting an uptime service keep the Repl from going to sleep. Not needed on Replit Deployments/Always On or on a normal server.
- `LEGACY_MODE` – set to `1` to enable some legacy prefix commands such as `!ping`.
- `ANALYTICS_ENABLED` – set to `0` to disable command usage analytics.
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` – optional. Required if you
  want to play Spotify track links through the new music player.

You can export these variables in your shell or simply place them in an `.env` file.
`main.py` automatically loads this file using `python-dotenv` on startup.

## Configuration

All default settings for the bot are stored in [`config.json`](config.json).
Each key in this file tweaks a piece of BinkoBot's behavior:

- `prefix` – Prefix used for legacy text commands.
- `privacy_mode` – Controls how much temporary data the bot keeps. Set to
  `standard` for basic features or `strict` to minimize logging and storage.
- `unclassified_music_enabled` – When `true`, the playlist module can suggest
  songs without vibe tags.
- `enhanced_personality_enabled` – Enables extra responses and flirtiness.
- `max_cozyspaces` – Maximum number of cozyspaces the bot maintains
  simultaneously.
- `auto_delete_inactive_after` – Seconds before inactive vibe or note data is
  purged automatically.
- `allow_lewd_in_cozyspace_only` – Restricts lewd commands to cozyspace
  channels and DMs.
- `nightmode_hour` – Hour of day (0-23) after which non-essential commands are
  blocked when night mode is enabled.
- `logging.enabled` – When `false`, regular log messages are suppressed and only
  warnings/errors are shown.
- `logging.log_flags_only` – If `true`, only log records marked with
  `extra={"flagged": True}` will be printed.

## Running the Bot

Once dependencies and environment variables are set:

```bash
python bot.py          # Discord bot only
python app.py          # Web dashboard only (dev server)
python main.py         # Both, in one process (set RUN_MODE=bot or RUN_MODE=web to run just one)
```

The bot will register slash commands on startup. If `DEV_GUILD_ID` is provided, commands appear in that guild immediately; otherwise, global registration may take up to an hour.

## Deployment

For a production server, run the bot and the web dashboard as two separate
processes (e.g. two systemd services, or two containers) rather than
`main.py`'s combined single-process mode, so each can be restarted, scaled,
and monitored independently:

```bash
python bot.py                                    # Discord bot process
gunicorn --bind 0.0.0.0:5000 app:app             # Web dashboard process
```

The web dashboard additionally needs `SESSION_SECRET`, `DATABASE_URL`, and
(for Discord OAuth login) `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` /
`DISCORD_REDIRECT_URI` set in the environment.

### Free-tier Replit

A `.replit` config is included so importing this project runs `python3 main.py`
out of the box. Set `REPLIT=1` (already default in `.replit`'s `[env]` block)
so `bot.py` starts the keep-alive ping server on port 8080, then point an
uptime service (e.g. UptimeRobot) at the Repl's URL to prevent it from
sleeping. This isn't needed on Replit Deployments/Always On, or any other
always-on host — see the Deployment section above instead.

## Voice & Music

BinkoBot can join a voice channel and play music from YouTube links, search terms, or
Spotify URLs (tracks, albums, playlists, and artists). Audio always streams through
YouTube; Spotify credentials are used only to resolve track metadata.

**Requirements:**
- `ffmpeg` – declared in `.replit` (`[nix] packages = ["ffmpeg"]`) and installed
  automatically in Replit environments. For other hosts, ensure `ffmpeg` is on `PATH`.
- `PyNaCl` – included in `requirements.txt`; enables discord.py voice connections.
- `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` – optional Replit Secrets or
  environment variables. Required only for Spotify link support.

**Commands:**

| Command | Description |
|---|---|
| `/join` | Have the bot join your current voice channel |
| `/play <query>` | Play a YouTube link/search term, or Spotify track/album/playlist/artist URL. Queues automatically if something is already playing |
| `/queue` | Show the current track and what's up next |
| `/skip` | Skip the current track and play the next in queue |
| `/pause` | Pause playback |
| `/resume` | Resume paused playback |
| `/stop` | Stop playback and clear the entire queue |
| `/leave` | Disconnect from the voice channel |

**Spotify support** handles:
- Track URLs: `https://open.spotify.com/track/<id>`
- Album URLs: up to 25 tracks queued automatically
- Playlist URLs: up to 25 tracks queued automatically
- Artist URLs: top tracks queued (up to 25)
- `spotify:track:<id>` and other `spotify:` URI formats

See [`docs/privacy_policy.md`](docs/privacy_policy.md) for details on how the bot handles data.
