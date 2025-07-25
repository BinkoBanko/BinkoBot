# BinkoBot - Discord Companion Bot

## Overview

BinkoBot is a modular Discord companion bot designed for cozy vibes and small community use. The project consists of two main components:

1. **Discord Bot** - A Python-based Discord bot using discord.py with slash commands for emotional support, affirmations, music, and social features
2. **Web Dashboard** - A Flask-based web application for server analytics and vibe monitoring

The bot focuses on providing emotional support, mood tracking, and community engagement through various interactive commands and features.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Hybrid Architecture
- **Discord Bot Application**: Python-based bot using discord.py framework
- **Web Dashboard**: Flask web application with SQLAlchemy ORM
- **Shared Data Storage**: JSON files for bot data, SQL database for web analytics
- **Dual Communication**: Discord OAuth for web access, bot token for Discord integration

### Key Components

#### Discord Bot Core (main.py)
- **Framework**: discord.py with slash commands
- **Configuration**: JSON-based config with environment variable overrides
- **Modular Design**: Cogs-based architecture for feature separation
- **Keep-Alive Service**: Web server for hosting platforms like Replit

#### Web Application (app.py)
- **Framework**: Flask with SQLAlchemy ORM
- **Authentication**: Discord OAuth2 integration
- **Database**: PostgreSQL with SQLAlchemy models
- **Analytics**: Server vibe scoring and historical tracking

#### Data Storage Strategy
- **Bot Data**: JSON files in `/data` directory for user preferences, vibes, notes
- **Analytics Data**: PostgreSQL database for persistent server metrics
- **Configuration**: JSON config files with environment variable overrides

### Module System

#### Core Modules
- **Affirmations**: Mood-based encouragement system (`affirm.py`, `dailyhype.py`)
- **Flirt & Touch**: Interactive social commands (`flirt.py`, `touch.py`)
- **Mood Management**: Vibe tracking with Discord role integration (`mood_with_roles.py`)
- **Mental Support**: Trigger detection and supportive responses (`mental_support.py`)
- **Music Player**: YouTube/Spotify integration (`music_player.py`)
- **Privacy Controls**: DM preferences and settings (`dm_toggle.py`, `privacy.py`)

#### Analytics & Web Features
- **Vibe Analyzer**: Server mood scoring algorithm
- **Discord Service**: OAuth and API integration
- **Dashboard**: Server analytics visualization
- **User Management**: Discord user synchronization

## Data Flow

### Bot Command Flow
1. Discord interaction received
2. Command routing through Discord.py cogs
3. User preference lookup (JSON files)
4. Response generation based on user vibe/mood
5. Analytics logging (if enabled)
6. Response delivery (public/DM based on preferences)

### Web Dashboard Flow
1. User authenticates via Discord OAuth
2. Server data synced from Discord API
3. Vibe analysis performed on server data
4. Analytics stored in PostgreSQL
5. Dashboard displays historical trends and insights

### Data Synchronization
- **User Vibes**: Stored in JSON, expires after 24h inactivity
- **Server Analytics**: Real-time sync with Discord API
- **Cross-Component**: Bot analytics feed into web dashboard

## External Dependencies

### Required Services
- **Discord API**: Bot token and OAuth credentials
- **Database**: PostgreSQL for web analytics
- **Optional Integrations**:
  - Spotify API (music recommendations)
  - YouTube-DL (music playback)

### Key Libraries
- **Discord Bot**: discord.py, python-dotenv, aiohttp
- **Web App**: Flask, SQLAlchemy, psycopg2-binary
- **Music**: yt-dlp, spotipy
- **Utilities**: requests, email_validator

### Environment Variables
- `DISCORD_TOKEN` - Bot authentication (required)
- `DISCORD_CLIENT_ID/SECRET` - OAuth credentials
- `DATABASE_URL` - PostgreSQL connection
- `SPOTIFY_CLIENT_ID/SECRET` - Music integration (optional)
- `DEV_GUILD_ID` - Development server for faster command sync

## Deployment Strategy

### Replit-Optimized
- **Keep-Alive**: Web server prevents bot shutdown
- **Environment Detection**: `REPLIT=1` enables keep-alive service
- **File Storage**: JSON files for bot data persistence

### Configuration Management
- **JSON Config**: Default settings in `config.json`
- **Environment Overrides**: Sensitive data via environment variables
- **Feature Toggles**: Runtime configuration for personality modes, analytics

### Database Strategy
- **Development**: SQLite for local testing
- **Production**: PostgreSQL for web analytics
- **Bot Data**: JSON files for rapid development and easy backup

### Privacy & Security
- **User Control**: DM preference system, data clearing options
- **Minimal Logging**: Optional analytics with user control
- **Secure Authentication**: Discord OAuth with state verification
- **Data Retention**: 24-hour expiry for user mood data