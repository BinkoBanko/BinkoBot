
import os
import json
import discord
import asyncio
import logging
from discord.ext import commands
from keep_alive import keep_alive

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# Intents setup
intents = discord.Intents.default()
intents.message_content = True

# Load configuration
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

prefix = config.get("prefix", "!")

# Bot setup
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

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
    "modules.privacy",
    "modules.dm_toggle",
    "modules.help",
    "modules.responder",
    "modules.locked",
]

# Optional Dev Guild for faster slash command registration
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID")

@bot.event
async def on_ready():
    logging.info(f"✅ Logged in as {bot.user}")
    await load_all_extensions()

    try:
        bot.tree.clear_commands(guild=None)
        synced = await bot.tree.sync()
        logging.info(f"🔁 Slash commands forcibly re-synced globally: {len(synced)}")

        for command in bot.tree.get_commands():
            logging.info(f"📋 Registered slash command: /{command.name} – {command.description}")

    except Exception as e:
        logging.error(f"⚠️ Slash command sync failed: {e}")

# Load extensions in parallel
async def load_all_extensions():
    tasks = [load_extension_safe(ext) for ext in initial_extensions]
    await asyncio.gather(*tasks)

async def load_extension_safe(ext):
    try:
        await bot.load_extension(ext)
        logging.info(f"✔️ Loaded: {ext}")
    except Exception as e:
        logging.error(f"❌ Failed to load {ext}: {e}")

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

if os.getenv("REPLIT") == "1":
    keep_alive()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise EnvironmentError("❌ DISCORD_TOKEN not found in environment variables.")
bot.run(token)
