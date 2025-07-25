
#!/usr/bin/env python3
"""
Debug script to check bot token, module loading, and slash command registration
"""
import asyncio
import discord
import os
import sys
from discord.ext import commands

async def debug_bot():
    print("🔍 BinkoBot Debug Script")
    print("=" * 50)
    
    # Check environment
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in environment")
        return
    
    print(f"✅ Token found: {token[:20]}...")
    
    # Create bot instance
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Bot connected: {bot.user}")
        print(f"📊 Guilds: {len(bot.guilds)}")
        
        # Load modules
        modules = [
            "modules.affirm", "modules.flirt", "modules.touch", "modules.goodnight",
            "modules.comfort", "modules.mood_with_roles", "modules.mental_support",
            "modules.dailyhype", "modules.help", "modules.cozyspace", 
            "modules.wholesome_chaos", "modules.music_player", "modules.personalization",
            "modules.privacy", "modules.dm_toggle", "modules.note", "modules.nightmode",
            "modules.nsfw", "modules.playlist", "modules.analytics", "modules.lore",
            "modules.responder", "modules.enhanced_personality", "modules.locked"
        ]
        
        print("\n📦 Loading modules...")
        loaded_count = 0
        total_commands = 0
        
        for module in modules:
            try:
                await bot.load_extension(module)
                
                # Find the cog
                module_name = module.split('.')[-1]
                possible_names = [
                    module_name.title(), module_name.capitalize(),
                    module_name.replace('_', ' ').title().replace(' ', ''),
                    module_name.upper(), module_name
                ]
                
                cog = None
                for name in possible_names:
                    cog = bot.get_cog(name)
                    if cog:
                        break
                
                if cog:
                    commands = cog.get_app_commands()
                    print(f"✅ {module} -> {len(commands)} commands")
                    total_commands += len(commands)
                    for cmd in commands[:3]:  # Show first 3 commands
                        print(f"   /{cmd.name}: {cmd.description}")
                else:
                    print(f"✅ {module} (no cog found)")
                
                loaded_count += 1
                
            except Exception as e:
                print(f"❌ {module}: {e}")
        
        print(f"\n📋 Summary: {loaded_count}/{len(modules)} modules loaded")
        print(f"🎯 Total commands found: {total_commands}")
        
        # Test command sync
        print("\n🔄 Testing command sync...")
        try:
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands")
            
            print("\n📝 Synced commands:")
            for cmd in synced:
                print(f"   /{cmd.name}: {cmd.description}")
                
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            import traceback
            traceback.print_exc()
        
        await bot.close()
    
    try:
        await bot.start(token)
    except discord.errors.LoginFailure:
        print("❌ Invalid bot token - check your DISCORD_BOT_TOKEN")
    except discord.errors.ConnectionClosed as e:
        print(f"❌ Connection closed: {e}")
        if e.code == 4004:
            print("   This usually means invalid token or token needs to be refreshed")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_bot())
