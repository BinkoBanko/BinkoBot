import discord
from discord.ext import commands
from discord import app_commands

class Personalization(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="personalize", description="Set your personal preferences")
    async def personalize(self, interaction: discord.Interaction, setting: str = ""):
        await interaction.response.send_message("Personalization features coming soon!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Personalization(bot))