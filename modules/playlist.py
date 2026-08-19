import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import os

class Playlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_file = "data/music_themes.json"
        if os.path.exists(self.music_file):
            with open(self.music_file, "r", encoding="utf-8") as f:
                self.music = json.load(f)
        else:
            self.music = {}

        self.vibes_file = "data/user_vibes.json"

    def get_user_vibe(self, user_id: str) -> str:
        if not os.path.exists(self.vibes_file):
            return "neutral"
        with open(self.vibes_file, "r", encoding="utf-8") as f:
            vibes = json.load(f)
        return vibes.get(user_id, {}).get("vibe", "neutral")

    @app_commands.command(name="music", description="Get a music link for your vibe")
    @app_commands.describe(vibe="Optional vibe to override your saved one")
    async def music(self, interaction: discord.Interaction, vibe: str = None):
        user_id = str(interaction.user.id)

        if not vibe:
            vibe = self.get_user_vibe(user_id)

        vibe = vibe.lower()
        if vibe not in self.music:
            await interaction.response.send_message(
                "I don’t have music for that vibe yet, sweetheart.", ephemeral=True
            )
            return

        song = random.choice(self.music[vibe])
        link = song["link"] if isinstance(song, dict) else song

        await interaction.response.send_message(
            f"🎶 Here's your **{vibe}** vibe track: {link}", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Playlist(bot))
