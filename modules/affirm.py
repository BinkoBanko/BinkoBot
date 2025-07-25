import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.sender import send_private_or_public

class Affirm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vibes = ["soft", "chaotic"]
        with open("data/mini_affirmations.txt", "r", encoding="utf-8") as f:
            self.soft = [line.strip() for line in f if line.strip()]
        with open("data/gremlin_affirmations.txt", "r", encoding="utf-8") as f:
            self.chaotic = [line.strip() for line in f if line.strip()]

    @app_commands.command(name="affirm", description="Send a vibe-based affirmation.")
    @app_commands.describe(vibe="Choose a vibe: soft or chaotic (optional)")
    async def affirm(self, interaction: discord.Interaction, vibe: str = None):
        try:
            if vibe == "chaotic":
                msg = random.choice(self.chaotic)
            else:
                msg = random.choice(self.soft)

            # Use the sender utility to respect DM preferences
            await send_private_or_public(interaction, f"*{msg}*")
        except Exception as e:
            # Fallback response if something goes wrong
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong with the affirmation~ Try again!", ephemeral=True)
            else:
                await interaction.followup.send("Something went wrong with the affirmation~ Try again!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Affirm(bot))
