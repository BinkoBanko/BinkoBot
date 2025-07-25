#!/usr/bin/env python3
"""
Force load all bot modules and sync commands
This script connects to Discord, loads all 24 modules, and syncs commands
"""

import asyncio
import discord
import os
import sys
import logging
from discord.ext import commands

# Add current directory to path
sys.path.insert(0, '.')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# All modules from bot.py
ALL_MODULES = [
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

async def main():
    logger.info("🚀 Starting BinkoBot with all modules...")
    
    # Get token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("❌ DISCORD_BOT_TOKEN not found")
        return
    
    # Create bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"✅ Connected as {bot.user}")
        logger.info(f"📡 Connected to {len(bot.guilds)} guilds")
        
        # Load all modules
        logger.info(f"📦 Loading {len(ALL_MODULES)} modules...")
        
        loaded_count = 0
        failed_count = 0
        
        for module in ALL_MODULES:
            try:
                await bot.load_extension(module)
                loaded_count += 1
                logger.info(f"✅ Loaded: {module}")
            except Exception as e:
                failed_count += 1
                logger.error(f"❌ Failed to load {module}: {e}")
        
        logger.info(f"📊 Modules loaded: {loaded_count}/{len(ALL_MODULES)} (Failed: {failed_count})")
        logger.info(f"🤖 Active cogs: {list(bot.cogs.keys())}")
        
        # Wait for all cogs to initialize
        await asyncio.sleep(3)
        
        # Count commands
        all_commands = bot.tree.get_commands()
        logger.info(f"🔧 Found {len(all_commands)} slash commands ready to sync")
        
        # List commands by cog
        for cog_name, cog in bot.cogs.items():
            app_commands = cog.get_app_commands()
            logger.info(f"  📋 {cog_name}: {len(app_commands)} commands")
            for cmd in app_commands:
                logger.info(f"    /{cmd.name} - {cmd.description[:50]}...")
        
        # Sync commands globally
        try:
            logger.info("🌍 Syncing commands globally...")
            synced = await bot.tree.sync()
            logger.info(f"✅ Successfully synced {len(synced)} commands globally")
            
            # List synced commands
            logger.info("📝 Synced commands:")
            for i, cmd in enumerate(synced, 1):
                desc = getattr(cmd, 'description', 'No description')
                logger.info(f"  {i:2d}. /{cmd.name} - {desc}")
                
        except discord.Forbidden as e:
            logger.error(f"❌ Sync failed - missing 'applications.commands' scope: {e}")
            logger.error("🔗 Use this invite URL to fix:")
            logger.error("https://discord.com/api/oauth2/authorize?client_id=1367271562142683349&permissions=2240518825457348590&scope=bot%20applications.commands")
        except Exception as e:
            logger.error(f"❌ Sync error: {e}")
        
        logger.info("🎉 Bot setup complete! All modules loaded and commands synced.")
        
        # Keep running
        while True:
            await asyncio.sleep(60)
            logger.info(f"💗 Bot alive - {len(bot.cogs)} cogs, {len(bot.tree.get_commands())} commands")
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("👋 Bot shutdown requested")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())