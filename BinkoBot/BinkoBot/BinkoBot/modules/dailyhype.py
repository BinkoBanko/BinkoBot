import discord
from discord.ext import commands
from discord import app_commands
import random

class DailyHype(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("data/mini_affirmations.txt", "r", encoding="utf-8") as f:
            self.soft = [line.strip() for line in f if line.strip()]
        with open("data/gremlin_affirmations.txt", "r", encoding="utf-8") as f:
            self.gremlin = [line.strip() for line in f if line.strip()]

    @app_commands.command(name="dailyhype", description="Start your day with a hype boost")
    @app_commands.describe(vibe="Choose between soft or chaotic energy")
    async def dailyhype(self, interaction: discord.Interaction, vibe: str = None):
        vibe = vibe.lower() if vibe else "soft"

        if vibe == "chaotic":
            msg = random.choice(self.gremlin)
        else:
            msg = random.choice(self.soft)

        await interaction.response.send_message(f"☀️ Daily Hype: *{msg}*", ephemeral=True)

async def setup(bot: commands.Bot):
    if "DailyHype" not in bot.cogs:
        await bot.add_cog(DailyHype(bot))
