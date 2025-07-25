import discord
from discord.ext import commands
from discord import app_commands
import json
import random
from utils.sender import send_private_or_public

class Flirt(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recent = {"soft": [], "tease": [], "spicy": []}
        self.cache_limit = 3

        with open("data/flirts.json", "r", encoding="utf-8") as f:
            self.flirts = json.load(f)

    def pick_unique(self, pool, vibe):
        options = [line for line in pool if line not in self.recent[vibe]]
        if not options:
            self.recent[vibe].clear()
            options = pool
        pick = random.choice(options)
        self.recent[vibe].append(pick)
        if len(self.recent[vibe]) > self.cache_limit:
            self.recent[vibe].pop(0)
        return pick

    @app_commands.command(name="flirt", description="Send a flirt based on your mood")
    @app_commands.choices(
        mood=[
            app_commands.Choice(name="soft", value="soft"),
            app_commands.Choice(name="tease", value="tease"),
            app_commands.Choice(name="spicy", value="spicy")
        ]
    )
    async def flirt(
        self,
        interaction: discord.Interaction,
        mood: app_commands.Choice[str]
    ):
        try:
            vibe = mood.value.lower()
            line = self.pick_unique(self.flirts[vibe], vibe)
            await send_private_or_public(interaction, f"*{line}*")
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong with the flirt~ Try again!", ephemeral=True)
            else:
                await interaction.followup.send("Something went wrong with the flirt~ Try again!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Flirt(bot))
