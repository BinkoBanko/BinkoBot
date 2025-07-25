import discord
from discord.ext import commands
import json
import random
import os
import logging


class MentalSupport(commands.Cog):
    """Detect concerning phrases and offer gentle support via DM."""

    def __init__(self, bot):
        self.bot = bot

        with open("data/trigger_keywords.json", "r", encoding="utf-8") as f:
            self.keywords = [k.lower() for k in json.load(f)]

        with open("data/trigger_responses.txt", "r", encoding="utf-8") as f:
            self.responses = [line.strip() for line in f if line.strip()]

    def contains_trigger(self, text: str) -> bool:
        """Return True if the text contains a trigger keyword."""
        lower = text.lower()
        return any(kw in lower for kw in self.keywords)

    def get_response(self) -> str:
        return random.choice(self.responses)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return

        if self.contains_trigger(message.content):
            logging.info(
                f"Flagged mental health phrase from {message.author}: {message.content}",
                extra={"flagged": True},
            )
            reply = self.get_response()

            try:
                if isinstance(message.channel, discord.DMChannel):
                    await message.channel.send(reply)
                else:
                    await message.author.send(reply)
            except discord.Forbidden:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(MentalSupport(bot))

