import discord
from discord.ext import commands
from discord import app_commands
import json
import random
import logging
from utils.sender import send_private_or_public
from utils.vibe_check import vibe_gate


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

    @app_commands.command(name="flirt", description="Get a playful flirty message")
    @app_commands.describe(intensity="How spicy? (mild is always available; spicy requires lewd or chaotic vibe)")
    @app_commands.choices(intensity=[
        app_commands.Choice(name="Mild 💕", value="mild"),
        app_commands.Choice(name="Tease 😏", value="tease"),
        app_commands.Choice(name="Spicy 🔥", value="spicy"),
    ])
    async def flirt(self, interaction: discord.Interaction, intensity: app_commands.Choice[str] = None):
        try:
            level = intensity.value if intensity else "mild"

            # Spicy flirts are gated to lewd/chaotic vibes only.
            if level == "spicy":
                if not await vibe_gate(
                    interaction,
                    ["lewd", "chaotic"],
                    "You're not quite in the mood for spicy flirts right now~ Try mild or tease instead!",
                ):
                    return

            await interaction.response.defer()

            user_id = str(interaction.user.id)

            try:
                with open("data/flirts.json", "r", encoding="utf-8") as f:
                    flirt_data = json.load(f)
            except FileNotFoundError:
                flirt_data = {"mild": ["You're looking cute today! 💕"]}

            available_flirts = flirt_data.get(level, flirt_data.get("mild", ["Hey there, cutie! 😘"]))

            if not available_flirts:
                await interaction.followup.send("❌ No flirts available for that intensity!", ephemeral=True)
                return

            flirt_message = random.choice(available_flirts)
            personalized = flirt_message.replace("{user}", interaction.user.display_name)

            try:
                with open("data/dm_preferences.json", "r", encoding="utf-8") as f:
                    dm_prefs = json.load(f)

                if dm_prefs.get(user_id, False):
                    try:
                        await interaction.user.send(personalized)
                        await interaction.followup.send("💝 Sent you a little something in DMs~", ephemeral=True)
                    except discord.Forbidden:
                        await interaction.followup.send(personalized)
                else:
                    await interaction.followup.send(personalized)
            except FileNotFoundError:
                await interaction.followup.send(personalized)

        except Exception as e:
            logging.error(f"Error in flirt command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Something went wrong with the flirting!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Something went wrong with the flirting!", ephemeral=True)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Flirt(bot))
