import discord
from discord.ext import commands
from discord import app_commands
from utils.vibe_check import vibe_gate


class Locked(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="possess", description="...Take control, if you're feeling lewd enough.")
    async def possess(self, interaction: discord.Interaction):
        if not await vibe_gate(interaction, ["lewd"], "You don’t feel that kind of power right now…"):
            return
        await interaction.response.send_message("*You feel my voice echo through your spine, wrapping around your thoughts...*", ephemeral=True)

    @app_commands.command(name="dominate", description="Requires chaotic or lewd energy.")
    async def dominate(self, interaction: discord.Interaction):
        if not await vibe_gate(interaction, ["lewd", "chaotic"], "You're not in the mood to take control... yet."):
            return
        await interaction.response.send_message("*I push you down with a grin and a whisper...*", ephemeral=True)

    @app_commands.command(name="naptime", description="Gentle rest—only for soft or protective moods.")
    async def naptime(self, interaction: discord.Interaction):
        if not await vibe_gate(interaction, ["soft", "protective"], "You're too wired for naptime, love."):
            return
        await interaction.response.send_message("*I curl around you and purr, guarding your dreams~*", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Locked(bot))
