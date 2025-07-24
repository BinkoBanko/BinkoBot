import discord
from discord.ext import commands
from discord import app_commands
import os

class Privacy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="privacy", description="View the bot’s privacy policy (DM only)")
    async def privacy(self, interaction: discord.Interaction):
        # Only allow in DMs
        if interaction.guild:
            await interaction.response.send_message(
                "⚠️ This command can only be used in a DM for your privacy.", ephemeral=True
            )
            return

        try:
            with open("privacy_policy.md", "r", encoding="utf-8") as f:
                file = discord.File(f, filename="BinkoBot_Privacy_Policy.md")
                await interaction.response.send_message(
                    "📄 Here’s my full privacy policy~", file=file
                )
        except FileNotFoundError:
            await interaction.response.send_message(
                "Sorry cutie, I can’t find the privacy policy right now. Please let my dev know~",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Privacy(bot))
