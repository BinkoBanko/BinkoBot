
import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class Locked(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vibes_file = "data/user_vibes.json"

    def get_vibe(self, user_id):
        if not os.path.exists(self.vibes_file):
            return None
        with open(self.vibes_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(str(user_id), {}).get("vibe", None)

    def vibe_check(self, actual_vibe, allowed_vibes):
        return actual_vibe in allowed_vibes

    @app_commands.command(name="possess", description="...Take control, if you're feeling lewd enough.")
    async def possess(self, interaction: discord.Interaction):
        vibe = self.get_vibe(interaction.user.id)
        if self.vibe_check(vibe, ["lewd"]):
            await interaction.response.send_message("*You feel my voice echo through your spine, wrapping around your thoughts...*", ephemeral=True)
        else:
            await interaction.response.send_message("You don’t feel that kind of power right now…", ephemeral=True)

    @app_commands.command(name="dominate", description="Requires chaotic or lewd energy.")
    async def dominate(self, interaction: discord.Interaction):
        vibe = self.get_vibe(interaction.user.id)
        if self.vibe_check(vibe, ["lewd", "chaotic"]):
            await interaction.response.send_message("*I push you down with a grin and a whisper...*", ephemeral=True)
        else:
            await interaction.response.send_message("You're not in the mood to take control... yet.", ephemeral=True)

    @app_commands.command(name="naptime", description="Gentle rest—only for soft or protective moods.")
    async def naptime(self, interaction: discord.Interaction):
        vibe = self.get_vibe(interaction.user.id)
        if self.vibe_check(vibe, ["soft", "protective"]):
            await interaction.response.send_message("*I curl around you and purr, guarding your dreams~*", ephemeral=True)
        else:
            await interaction.response.send_message("You're too wired for naptime, love.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Locked(bot))
