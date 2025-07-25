
#!/usr/bin/env python3
"""
Simple test to verify bot token and connection
"""
import asyncio
import discord
import os
from discord.ext import commands

async def test_bot_connection():
    print("🔍 Testing Bot Connection")
    print("=" * 40)
    
    # Check token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found")
        return
    
    # Validate token format
    token = token.strip()
    if len(token) < 50 or '.' not in token:
        print(f"❌ Token appears invalid (length: {len(token)})")
        return
    
    print(f"✅ Token format looks valid: {token[:20]}...")
    
    # Test connection
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"✅ Successfully connected as: {bot.user}")
        print(f"📊 Connected to {len(bot.guilds)} guilds:")
        for guild in bot.guilds:
            print(f"   - {guild.name} (ID: {guild.id})")
        
        # Test if bot has applications.commands scope
        try:
            # Try to register a simple test command
            @bot.tree.command(name="test", description="Test command")
            async def test_cmd(interaction: discord.Interaction):
                await interaction.response.send_message("Test successful!")
            
            print("🔄 Testing command sync...")
            synced = await bot.tree.sync()
            print(f"✅ Command sync successful: {len(synced)} commands")
            
            if len(synced) == 0:
                print("⚠️ No commands synced - this might indicate missing 'applications.commands' scope")
            
        except discord.errors.Forbidden:
            print("❌ Permission denied - bot likely missing 'applications.commands' scope")
        except Exception as e:
            print(f"❌ Sync failed: {e}")
        
        await bot.close()
    
    try:
        await bot.start(token)
    except discord.errors.LoginFailure:
        print("❌ Login failed - invalid token")
    except discord.errors.ConnectionClosed as e:
        if e.code == 4004:
            print("❌ Authentication failed (4004) - token invalid or expired")
        else:
            print(f"❌ Connection closed: {e}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(test_bot_connection())
