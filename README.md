# BinkoBot

BinkoBot is a modular Discord companion bot focused on cozy vibes and small community use. The bot uses slash commands and can be customized through its configuration file and environment variables.

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

- `DISCORD_TOKEN` – **required**. Your bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- `DEV_GUILD_ID` – optional. If set, slash commands sync to this guild first for faster updates.
- `REPLIT` – set to `1` when running on Replit so the keep-alive web server starts.
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

Once dependencies and environment variables are set, start BinkoBot with:

```bash
python main.py
```

The bot will register slash commands on startup. If `DEV_GUILD_ID` is provided, commands appear in that guild immediately; otherwise, global registration may take up to an hour.

## Voice & Music

BinkoBot can join a voice channel and play music from YouTube links, search terms, or Spotify track URLs. Spotify support requires the `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` environment variables. You also need `ffmpeg` installed on your system for audio playback.

Commands:

- `/join` – Have the bot join your current voice channel.
- `/play <query>` – Play a YouTube link, search term, or Spotify track.
- `/stop` – Stop the current track.
- `/leave` – Disconnect from the voice channel.

See `privacy_policy.md` for details on how the bot handles data.
