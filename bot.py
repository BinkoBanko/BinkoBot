import os
import json
import discord
import asyncio
import logging
from datetime import datetime
from discord.ext import commands
from keep_alive import keep_alive
from dotenv import load_dotenv

load_dotenv()

# Load configuration
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

logging_cfg = config.get("logging", {})
logging_enabled = logging_cfg.get("enabled", True)
log_flags_only = logging_cfg.get("log_flags_only", False)

prefix = config.get("prefix", "!")
nightmode_hour = config.get("nightmode_hour", 22)

NIGHTMODE_FILE = "data/nightmode_status.json"
os.makedirs("data", exist_ok=True)
if not os.path.exists(NIGHTMODE_FILE):
    with open(NIGHTMODE_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

def nightmode_enabled(guild_id: int) -> bool:
    with open(NIGHTMODE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(str(guild_id), False)

# Logging setup
logging.basicConfig(
    level=logging.INFO if logging_enabled else logging.WARNING,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
if logging_enabled and log_flags_only:
    class FlagOnlyFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return getattr(record, "flagged", False)

    for handler in logging.getLogger().handlers:
        handler.addFilter(FlagOnlyFilter())

# Intents setup
intents = discord.Intents.default()
intents.message_content = True

# Extension modules (Cogs)
INITIAL_EXTENSIONS = [
    "modules.affirm",           # Affirmations and encouragement
    "modules.flirt",            # Flirt commands
    "modules.touch",            # Touch interactions
    "modules.goodnight",        # Sleep and goodnight wishes
    "modules.mood_with_roles",  # Mood tracking with Discord roles
    "modules.mental_support",   # Mental health support
    "modules.dailyhype",        # Daily motivation
    "modules.help",             # Help command
    "modules.cozyspace",        # Cozy space creation
    "modules.wholesome_chaos",  # Wholesome chaos mode
    "modules.music_player",     # Music player functionality
    "modules.personalization",  # User personalization
    "modules.privacy",          # Privacy controls
    "modules.dm_toggle",        # DM preference toggle
    "modules.note",             # User notes system
    "modules.nightmode",        # Night mode settings
    "modules.nsfw",             # NSFW content toggle
    "modules.playlist",         # Music playlists
    "modules.analytics",        # Analytics collection
    "modules.lore",             # Bot lore system
    "modules.responder",        # Auto responses
    "modules.enhanced_personality",  # Personality enhancements
    "modules.locked",           # Locked/restricted commands
]

# Optional Dev Guild for faster slash command registration
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")


class BinkoBot(commands.Bot):
    async def setup_hook(self):
        """Runs once, before the bot connects. This is the correct place to
        load extensions and sync the command tree - on_ready can fire again
        on every reconnect, which would otherwise re-run this and raise
        ExtensionAlreadyLoaded errors on the second connection."""
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                logging.info(f"Loaded {extension}")
            except Exception:
                logging.exception(f"Failed to load {extension}")

        try:
            if DEV_GUILD_ID:
                guild = discord.Object(id=int(DEV_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logging.info(f"Synced {len(synced)} commands to dev guild {DEV_GUILD_ID}")
            else:
                synced = await self.tree.sync()
                logging.info(f"Synced {len(synced)} global slash commands")
        except discord.Forbidden:
            logging.error("Sync forbidden - bot may be missing the 'applications.commands' scope")
        except discord.HTTPException:
            logging.exception("Failed to sync slash commands")


bot = BinkoBot(command_prefix=prefix, intents=intents, help_command=None)


@bot.check
async def check_nightmode(ctx) -> bool:
    if not ctx.guild:
        return True
    if not nightmode_enabled(ctx.guild.id):
        return True
    if datetime.now().hour >= nightmode_hour:
        if ctx.command and not ctx.command.qualified_name.startswith("nightmode"):
            return False
    return True


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user} (connected to {len(bot.guilds)} guilds)")


@bot.listen("on_command")
async def delete_command_message(ctx):
    try:
        await ctx.message.delete()
    except (discord.NotFound, discord.Forbidden):
        pass


if os.getenv("LEGACY_MODE") == "1":
    @bot.command()
    async def ping(ctx):
        await ctx.send("Pong!")


async def main():
    """Main function to run the bot"""
    # Ping-able web server so an uptime service can keep a free-tier Repl awake.
    # Not needed (and not started) on a normal always-on server.
    if os.getenv("REPLIT") == "1":
        keep_alive()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise EnvironmentError("❌ DISCORD_BOT_TOKEN not found in environment variables.")

    # Validate token format
    if len(token.strip()) < 50 or '.' not in token:
        raise EnvironmentError("❌ DISCORD_BOT_TOKEN appears to be invalid or corrupted.")

    try:
        await bot.start(token.strip())
    except discord.errors.LoginFailure:
        logging.error("❌ Invalid bot token - please check your DISCORD_BOT_TOKEN")
        raise
    except discord.errors.ConnectionClosed as e:
        if e.code == 4004:
            logging.error("❌ Bot token authentication failed (4004) - token may be invalid or expired")
        else:
            logging.error(f"❌ Connection closed: {e}")
        raise
    except Exception as e:
        logging.error(f"❌ Unexpected bot startup error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
