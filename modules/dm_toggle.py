import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class DMToggle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file = "data/dm_preferences.json"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def load_prefs(self):
        with open(self.file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_prefs(self, data):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    dm_group = app_commands.Group(name="dm", description="Control whether replies are sent via DM")

    @dm_group.command(name="optin", description="Receive responses in DMs instead of public")
    async def dm_optin(self, interaction: discord.Interaction):
        prefs = self.load_prefs()
        prefs[str(interaction.user.id)] = True
        self.save_prefs(prefs)

        await interaction.response.send_message("📩 Alright! I’ll slide back into your DMs~", ephemeral=True)

    @dm_group.command(name="optout", description="Receive responses publicly instead of DMs")
    async def dm_optout(self, interaction: discord.Interaction):
        prefs = self.load_prefs()
        prefs[str(interaction.user.id)] = False
        self.save_prefs(prefs)

        await interaction.response.send_message("💬 Got it! I’ll stop sending DMs and reply here instead~", ephemeral=True)

    async def cog_app_command_group(self):
        return [self.dm_group]

async def setup(bot: commands.Bot):
    await bot.add_cog(DMToggle(bot))
