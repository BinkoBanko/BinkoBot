#!/usr/bin/env python3
"""
Test script to check if slash commands are being registered properly
"""
import asyncio
import discord
import os
from discord.ext import commands
from discord import app_commands

async def test_commands():
    token = os.getenv('DISCORD_BOT_TOKEN')
    intents = discord.Intents.default()
    intents.message_content = True
    
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    # Add a simple test command
    @bot.tree.command(name="test", description="Test slash command")
    async def test_command(interaction: discord.Interaction):
        await interaction.response.send_message("Test command works!")
    
    @bot.event
    async def on_ready():
        print(f'Bot logged in as: {bot.user}')
        
        # Try to sync commands
        try:
            synced = await bot.tree.sync()
            print(f'Successfully synced {len(synced)} commands')
            for cmd in synced:
                print(f'- /{cmd.name}: {cmd.description}')
                
            # Wait a moment then check if commands appear
            print("\nWaiting 5 seconds for commands to propagate...")
            await asyncio.sleep(5)
            
            # List all registered commands
            all_commands = bot.tree.get_commands()
            print(f"\nAll registered commands ({len(all_commands)}):")
            for cmd in all_commands:
                print(f'- /{cmd.name}: {cmd.description}')
                
        except Exception as e:
            print(f'Error syncing commands: {e}')
        
        await bot.close()
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(test_commands())