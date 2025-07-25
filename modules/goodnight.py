import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.sender import send_private_or_public

class Goodnight(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        with open("data/sleep_wishes.txt", "r", encoding="utf-8") as f:
            self.sleep_lines = [line.strip() for line in f if line.strip()]
        with open("data/emoji_attacks.txt", "r", encoding="utf-8") as f:
            self.attack_lines = [line.strip() for line in f if line.strip()]

    @app_commands.command(name="goodnight", description="Send a cozy goodnight wish")
    async def goodnight(self, interaction: discord.Interaction):
        line = random.choice(self.sleep_lines)
        await send_private_or_public(interaction, line)

    @app_commands.command(name="emojiattack", description="Unleash a chaotic emoji attack")
    async def emojiattack(self, interaction: discord.Interaction):
        line = random.choice(self.attack_lines)
        await send_private_or_public(interaction, line)

async def setup(bot: commands.Bot):
    await bot.add_cog(Goodnight(bot))
