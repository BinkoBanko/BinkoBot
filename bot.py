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
    "modules.analytics",
    "modules.flirt",
    "modules.note",
    "modules.playlist",
    "modules.comfort",
    "modules.affirm",
    "modules.dailyhype",
    "modules.nsfw",
    "modules.mood_with_roles",
    "modules.touch",
    "modules.lore",
    "modules.goodnight",
    "modules.privacy",
    "modules.dm_toggle",
    "modules.cozyspace",
    "modules.help",
    "modules.music_player",
    "modules.responder",
    "modules.locked",
    "modules.mental_support",
    "modules.wholesome_chaos",
    "modules.nightmode",
    "modules.enhanced_personality",
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
        
        # Get the cog that was just loaded
        cog_name = ext.split('.')[-1]
        cog_classes = [cog_name.title(), cog_name.capitalize(), cog_name.upper()]
        
        loaded_cog = None
        for class_name in cog_classes:
            loaded_cog = bot.get_cog(class_name)
            if loaded_cog:
                break
        
        if loaded_cog:
            # Count app commands in this cog
            app_commands = [cmd for cmd in loaded_cog.get_app_commands()]
            logging.info(f"✔️ Loaded {ext} with {len(app_commands)} slash commands")
            for cmd in app_commands:
                logging.info(f"   /{cmd.name}")
        else:
            logging.info(f"✔️ Loaded {ext} (no slash commands found)")
        
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