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

    @app_commands.command(name="flirt", description="Get a playful flirty message")
    async def flirt(self, interaction: discord.Interaction, intensity: str = "mild"):
        try:
            # Respond immediately to prevent timeout
            await interaction.response.defer()

            user_id = str(interaction.user.id)

            # Load flirts
            try:
                with open("data/flirts.json", "r", encoding="utf-8") as f:
                    flirt_data = json.load(f)
            except FileNotFoundError:
                flirt_data = {"mild": ["You're looking cute today! 💕"]}

            # Get flirts for intensity level
            available_flirts = flirt_data.get(intensity, flirt_data.get("mild", ["Hey there, cutie! 😘"]))

            if not available_flirts:
                await interaction.followup.send("❌ No flirts available for that intensity!", ephemeral=True)
                return

            # Pick random flirt
            flirt_message = random.choice(available_flirts)

            # Personalize it
            personalized = flirt_message.replace("{user}", interaction.user.display_name)

            # Check DM preferences
            try:
                with open("data/dm_preferences.json", "r", encoding="utf-8") as f:
                    dm_prefs = json.load(f)

                if dm_prefs.get(user_id, False):
                    # Send DM
                    try:
                        await interaction.user.send(personalized)
                        await interaction.followup.send("💝 Sent you a little something in DMs~", ephemeral=True)
                    except discord.Forbidden:
                        await interaction.followup.send(personalized)
                else:
                    # Send publicly
                    await interaction.followup.send(personalized)
            except FileNotFoundError:
                # Default to public
                await interaction.followup.send(personalized)

        except Exception as e:
            logging.error(f"Error in flirt command: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Something went wrong with the flirting!", ephemeral=True)
                else:
                    await interaction.followup.send("❌ Something went wrong with the flirting!", ephemeral=True)
            except:
                pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Flirt(bot))