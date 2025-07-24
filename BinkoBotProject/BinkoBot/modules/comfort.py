import discord
from discord.ext import commands
import random
from utils.sender import send_private_or_public

class DailyHype(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open("data/mini_affirmations.txt", "r", encoding="utf-8") as f:
            self.soft = [line.strip() for line in f if line.strip()]
        with open("data/gremlin_affirmations.txt", "r", encoding="utf-8") as f:
            self.gremlin = [line.strip() for line in f if line.strip()]

    @commands.command()
    async def dailyhype(self, ctx, *, vibe=None):
        if vibe == "chaotic":
            msg = random.choice(self.gremlin)
        else:
            msg = random.choice(self.soft)

        try:
            await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        await send_private_or_public(ctx, f"☀️ Daily Hype: *{msg}*")

async def setup(bot):
    await bot.add_cog(DailyHype(bot))
