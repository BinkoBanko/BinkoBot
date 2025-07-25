
#!/usr/bin/env python3
"""
Test script to verify all bot modules load correctly and register commands
"""
import asyncio
import discord
import os
import sys
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

async def test_module_loading():
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ No DISCORD_BOT_TOKEN found in environment")
        return False
    
    print("🤖 Testing BinkoBot module loading...")
    
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    success_count = 0
    total_commands = 0
    
    @bot.event
    async def on_ready():
        nonlocal success_count, total_commands
        
        print(f"✅ Bot connected: {bot.user}")
        print(f"📊 Connected to {len(bot.guilds)} guilds")
        print("\n" + "="*60)
        print("MODULE LOADING TEST")
        print("="*60)
        
        for i, module in enumerate(all_modules, 1):
            try:
                print(f"\n{i:2d}. Loading {module}...")
                await bot.load_extension(module)
                
                # Try to find the cog
                module_name = module.split('.')[-1]
                possible_names = [
                    module_name.title(),
                    module_name.capitalize(), 
                    module_name.replace('_', ' ').title().replace(' ', ''),
                    module_name.upper(),
                    module_name,
                    module_name.replace('_', '')
                ]
                
                cog = None
                for name in possible_names:
                    cog = bot.get_cog(name)
                    if cog:
                        break
                
                if cog:
                    commands = cog.get_app_commands()
                    print(f"    ✅ {cog.__class__.__name__} - {len(commands)} commands")
                    total_commands += len(commands)
                    for cmd in commands:
                        print(f"       /{cmd.name}: {cmd.description}")
                else:
                    print(f"    ✅ Loaded (no cog class found)")
                
                success_count += 1
                
            except Exception as e:
                print(f"    ❌ FAILED: {e}")
                import traceback
                print(f"       {traceback.format_exc()}")
        
        print("\n" + "="*60)
        print("COMMAND SYNC TEST")
        print("="*60)
        
        try:
            print("🔄 Attempting command sync...")
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} commands successfully")
            
            for cmd in synced:
                print(f"   /{cmd.name}: {cmd.description}")
                
        except Exception as e:
            print(f"❌ Command sync failed: {e}")
            import traceback
            print(traceback.format_exc())
        
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Modules loaded successfully: {success_count}/{len(all_modules)}")
        print(f"Total commands found: {total_commands}")
        print(f"Commands synced: {len(synced) if 'synced' in locals() else 0}")
        
        success_rate = (success_count / len(all_modules)) * 100
        if success_rate == 100:
            print("🎉 ALL MODULES LOADED SUCCESSFULLY!")
        else:
            print(f"⚠️  {success_rate:.1f}% success rate")
        
        await bot.close()
        return success_count == len(all_modules)
    
    try:
        await bot.start(token)
    except Exception as e:
        print(f"❌ Bot startup failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_module_loading())
    sys.exit(0 if result else 1)
