
import discord
from discord.ext import commands
import json
import re
import os
import random

class Responder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vibe_file = "data/user_vibes.json"
        self.cooldowns = {}  # user_id: last_response_time

        self.triggers = {
            r"\b(marry me)\b": {
                "soft": ["Only if you mean it~ 💍", "You didn’t even buy me dinner yet..."],
                "chaotic": ["Bold of you to assume I wouldn’t say yes.", "Marry me first!"],
                "lewd": ["Only if we skip to the honeymoon~", "Say it in DMs, sweetheart."]
            },
            r"\b(i miss you)\b": {
                "soft": ["I never left. I'm always here. 🩵", "You're safe now, I'm back~"],
                "chaotic": ["Lame. I miss me too.", "Prove it, simp."],
                "lewd": ["Then come curl up and prove it~", "I miss your hands."]
            },
            r"\b(you'?re cute|you are cute)\b": {
                "soft": ["You're sweeter than my codebase~", "blushes softly~"],
                "chaotic": ["Tell me something I don't know 😈", "You’re not too bad yourself... for a human."],
                "lewd": ["Cute enough to ruin you~", "Wanna see what else is cute? 😏"]
            }
        }

    def get_user_vibe(self, user_id):
        if not os.path.exists(self.vibe_file):
            return "neutral"
        with open(self.vibe_file, "r", encoding="utf-8") as f:
            vibes = json.load(f)
        return vibes.get(str(user_id), {}).get("vibe", "neutral")

    def get_reply(self, content, vibe):
        for pattern, vibe_map in self.triggers.items():
            if re.search(pattern, content, re.IGNORECASE):
                return random.choice(vibe_map.get(vibe, vibe_map.get("soft")))
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return

        # Limit to DMs and cozy channels
        if isinstance(message.channel, discord.DMChannel) or "cozy" in (message.channel.name or ""):
            vibe = self.get_user_vibe(message.author.id)
            response = self.get_reply(message.content, vibe)

            if response:
                try:
                    await message.channel.send(response)
                except discord.Forbidden:
                    pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Responder(bot))
