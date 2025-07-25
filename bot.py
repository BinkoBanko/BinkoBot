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
if logging_enabled:
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )
    if log_flags_only:
        class FlagOnlyFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                return getattr(record, "flagged", False)

        for handler in logging.getLogger().handlers:
            handler.addFilter(FlagOnlyFilter())
else:
    logging.basicConfig(
        level=logging.WARNING,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )

# Intents setup
intents = discord.Intents.default()
intents.message_content = True

# Bot setup
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

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

# Extension modules (Cogs)
initial_extensions = [
    "modules.affirm",        # Affirmations and encouragement
    "modules.flirt",         # Flirt commands
    "modules.touch",         # Touch interactions
    "modules.goodnight",     # Sleep and goodnight wishes
    "modules.comfort",       # Comforting responses
    "modules.mood_with_roles", # Mood tracking with Discord roles
    "modules.mental_support", # Mental health support
    "modules.dailyhype",     # Daily motivation
    "modules.help",          # Help command
    "modules.cozyspace",     # Cozy space creation
    "modules.wholesome_chaos", # Wholesome chaos mode
    "modules.music_player",  # Music player functionality
    "modules.personalization", # User personalization
    "modules.privacy",       # Privacy controls
    "modules.dm_toggle",     # DM preference toggle
    "modules.note",          # User notes system
    "modules.nightmode",     # Night mode settings
    "modules.nsfw",          # NSFW content toggle
    "modules.playlist",      # Music playlists
    "modules.analytics",     # Analytics collection
    "modules.lore",          # Bot lore system
    "modules.responder",     # Auto responses
    "modules.enhanced_personality", # Personality enhancements
    "modules.locked"         # Locked/restricted commands
]

# Optional Dev Guild for faster slash command registration
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user}")
    logging.info(f"Connected to {len(bot.guilds)} guilds")
    
    # Load all extensions first
    await load_all_extensions()
    
    # Wait a moment for cogs to fully initialize
    await asyncio.sleep(2)
    
    try:
        # Clear existing commands first
        bot.tree.clear_commands(guild=None)
        
        # Get all commands from loaded cogs
        all_commands = bot.tree.get_commands()
        logging.info(f"Found {len(all_commands)} commands to sync")
        
        # Sync to dev guild first if specified (faster)
        if DEV_GUILD_ID:
            dev_guild = discord.Object(id=int(DEV_GUILD_ID))
            # Copy commands to dev guild
            for cmd in all_commands:
                bot.tree.add_command(cmd, guild=dev_guild)
            dev_synced = await bot.tree.sync(guild=dev_guild)
            logging.info(f"🔁 Synced {len(dev_synced)} slash commands to dev guild {DEV_GUILD_ID}")
        
        # Sync globally
        synced = await bot.tree.sync()
        logging.info(f"🔁 Synced {len(synced)} slash commands globally")

        # List all synced commands
        for command in synced:
            desc = getattr(command, 'description', None) or 'No description'
            logging.info(f"📋 /{command.name} – {desc}")

    except Exception as e:
        logging.error(f"⚠️ Slash command sync failed: {e}")
        import traceback
        logging.error(traceback.format_exc())

# Load extensions in parallel
async def load_all_extensions():
    tasks = [load_extension_safe(ext) for ext in initial_extensions]
    await asyncio.gather(*tasks)

async def load_extension_safe(ext):
    try:
        await bot.load_extension(ext)
        
        # Get the cog that was just loaded - try different name patterns
        cog_name = ext.split('.')[-1]
        possible_names = [
            cog_name.title(),           # affirm -> Affirm  
            cog_name.capitalize(),      # affirm -> Affirm
            cog_name.replace('_', ''),  # mood_with_roles -> moodwithroles
            cog_name.replace('_', ' ').title().replace(' ', ''), # mood_with_roles -> MoodWithRoles
            cog_name.upper(),           # affirm -> AFFIRM
            cog_name                    # affirm -> affirm
        ]
        
        loaded_cog = None
        for name in possible_names:
            loaded_cog = bot.get_cog(name)
            if loaded_cog:
                break
        
        if loaded_cog:
            # Count app commands in this cog
            app_commands = [cmd for cmd in loaded_cog.get_app_commands()]
            logging.info(f"✔️ Loaded {ext} -> {loaded_cog.__class__.__name__} ({len(app_commands)} commands)")
            for cmd in app_commands:
                logging.info(f"   /{cmd.name}: {cmd.description}")
        else:
            # Still successful load, just no cog found (might be function-based)
            logging.info(f"✔️ Loaded {ext} (cog class not detected)")
        
    except Exception as e:
        logging.error(f"❌ Failed to load {ext}: {e}")
        import traceback
        logging.error(traceback.format_exc())

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
    # Start keep-alive service for Replit
    if os.getenv("REPLIT") == "1":
        keep_alive()
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise EnvironmentError("❌ DISCORD_BOT_TOKEN not found in environment variables.")
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())