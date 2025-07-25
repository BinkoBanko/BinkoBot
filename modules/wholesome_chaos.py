import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.sender import send_private_or_public


class WholesomeChaos(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open("data/wholesome_lines.txt", "r", encoding="utf-8") as f:
            self.wholesome_lines = [line.strip() for line in f if line.strip()]
        with open("data/chaos_lines.txt", "r", encoding="utf-8") as f:
            self.chaos_lines = [line.strip() for line in f if line.strip()]

    @app_commands.command(name="wholesome", description="Send a wholesome line")
    async def wholesome(self, interaction: discord.Interaction):
        line = random.choice(self.wholesome_lines)
        await send_private_or_public(interaction, line)

    @app_commands.command(name="chaos", description="Send a chaotic line")
    async def chaos(self, interaction: discord.Interaction):
        line = random.choice(self.chaos_lines)
        await send_private_or_public(interaction, line)


async def setup(bot: commands.Bot):
    await bot.add_cog(WholesomeChaos(bot))
