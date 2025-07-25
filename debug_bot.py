#!/usr/bin/env python3
import asyncio
import discord
import os
import sys
from discord.ext import commands

async def debug_bot():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No DISCORD_BOT_TOKEN found")
        return
    
    print("🔍 Starting bot debug...")
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Bot online: {bot.user}")
        print(f"📊 Connected to {len(bot.guilds)} guilds")
        
        # Load one test cog
        try:
            await bot.load_extension("modules.affirm")
            print("✅ Loaded affirm module")
            
            # Check for commands
            affirm_cog = bot.get_cog("Affirm")
            if affirm_cog:
                commands = affirm_cog.get_app_commands()
                print(f"📋 Found {len(commands)} app commands in Affirm cog")
                for cmd in commands:
                    print(f"   - /{cmd.name}: {cmd.description}")
            
            # Try to sync
            synced = await bot.tree.sync()
            print(f"🔄 Synced {len(synced)} global commands")
            
            # List all synced commands
            for cmd in synced:
                print(f"   ✓ /{cmd.name}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("🛑 Stopping bot...")
        await bot.close()
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")

if __name__ == "__main__":
    asyncio.run(debug_bot())