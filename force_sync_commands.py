
#!/usr/bin/env python3
"""
Force sync Discord slash commands
"""
import asyncio
import discord
import os
from discord.ext import commands

async def force_sync():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No DISCORD_BOT_TOKEN found")
        return
    
    intents = discord.Intents.default()
    intents.message_content = True
    
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f'✅ Bot logged in as: {bot.user}')
        print(f'📊 Connected to {len(bot.guilds)} guilds')
        
        try:
            # Clear existing commands first
            print("🧹 Clearing existing commands...")
            bot.tree.clear_commands(guild=None)
            await asyncio.sleep(2)
            
            # Force sync
            print("🚀 Force syncing commands...")
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} commands")
            
            if len(synced) == 0:
                print("⚠️ No commands synced - checking for module issues...")
            else:
                print("📋 Synced commands:")
                for cmd in synced:
                    print(f"  /{cmd.name}: {cmd.description}")
            
        except discord.Forbidden as e:
            print(f"❌ Permission denied: {e}")
            print("🔧 Bot may still lack 'applications.commands' scope")
        except Exception as e:
            print(f"❌ Sync error: {e}")
        
        await bot.close()
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ Bot start error: {e}")

if __name__ == "__main__":
    asyncio.run(force_sync())
