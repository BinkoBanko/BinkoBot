#!/usr/bin/env python3
"""
Test script to load ALL bot modules and verify slash commands
"""
import asyncio
import discord
import os
from discord.ext import commands

# All modules to test
all_modules = [
    "modules.affirm",
    "modules.flirt", 
    "modules.touch",
    "modules.goodnight",
    "modules.comfort",
    "modules.mood_with_roles",
    "modules.mental_support",
    "modules.dailyhype",
    "modules.help",
    "modules.cozyspace",
    "modules.wholesome_chaos",
    "modules.music_player",
    "modules.personalization",
    "modules.privacy",
    "modules.dm_toggle",
    "modules.note",
    "modules.nightmode",
    "modules.nsfw",
    "modules.playlist",
    "modules.analytics",
    "modules.lore",
    "modules.responder",
    "modules.enhanced_personality",
    "modules.locked"
]

async def test_all_modules():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No DISCORD_BOT_TOKEN found")
        return
    
    print("🚀 Testing ALL bot modules...")
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Bot online: {bot.user}")
        print(f"📊 Connected to {len(bot.guilds)} guilds")
        
        loaded_count = 0
        command_count = 0
        
        print("\n📦 Loading modules...")
        for module in all_modules:
            try:
                await bot.load_extension(module)
                
                # Try to find the cog
                module_name = module.split('.')[-1]
                possible_names = [
                    module_name.title(),
                    module_name.capitalize(), 
                    module_name.replace('_', ' ').title().replace(' ', ''),
                    module_name.upper(),
                    module_name
                ]
                
                cog = None
                for name in possible_names:
                    cog = bot.get_cog(name)
                    if cog:
                        break
                
                if cog:
                    commands = cog.get_app_commands()
                    print(f"✅ {module} -> {cog.__class__.__name__} ({len(commands)} commands)")
                    for cmd in commands:
                        print(f"   /{cmd.name}: {cmd.description}")
                        command_count += 1
                else:
                    print(f"✅ {module} (loaded, no cog detected)")
                
                loaded_count += 1
                
            except Exception as e:
                print(f"❌ {module}: {e}")
        
        print(f"\n📊 Summary: {loaded_count}/{len(all_modules)} modules loaded, {command_count} commands found")
        
        # Sync commands
        try:
            print("\n🔄 Syncing commands...")
            synced = await bot.tree.sync()
            print(f"✅ Successfully synced {len(synced)} commands!")
            
            print("\n📋 All synced commands:")
            for cmd in synced:
                print(f"   /{cmd.name}: {cmd.description}")
                
        except Exception as e:
            print(f"❌ Sync failed: {e}")
        
        print("\n🛑 Test complete, shutting down...")
        await bot.close()
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")

if __name__ == "__main__":
    asyncio.run(test_all_modules())