import discord
from discord.ext import commands
import json
import random
import os
from utils.sender import send_private_or_public

class Lore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lore_file = "data/lore_branches.json"
        if os.path.exists(self.lore_file):
            with open(self.lore_file, "r", encoding="utf-8") as f:
                self.lore = json.load(f)
        else:
            self.lore = {}

    def get_lore(self, vibe):
        vibe = vibe.lower()
        return random.choice(self.lore.get(vibe, self.lore.get("core", ["My origin is... unclear."])))

    @commands.command()
    async def binkoshift(self, ctx, vibe=None):
        if not vibe:
            try:
                with open("data/user_vibes.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                vibe = data.get(str(ctx.author.id), {}).get("vibe", "core")
            except:
                vibe = "core"

        scene = self.get_lore(vibe)

        try:
            await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        await send_private_or_public(ctx, f"*Lore shift incoming...*\n{scene}")

    @commands.command()
    async def binkocard(self, ctx):
        try:
            with open("data/user_vibes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            vibe = data.get(str(ctx.author.id), {}).get("vibe", "core")
        except:
            vibe = "core"

        origin = self.get_lore("core")
        flavor = self.get_lore(vibe)

        try:
            await ctx.message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        await send_private_or_public(ctx, f"🌌 **Your BinkoCard**\n\n*Origin:* {origin}\n*Current Vibe:* {vibe}\n*Flavor Line:* {flavor}")

async def setup(bot):
    await bot.add_cog(Lore(bot))
