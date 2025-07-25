import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime


class NightMode(commands.Cog):
    """Toggle server-wide night mode to limit commands after hours."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.file = "data/nightmode_status.json"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump({}, f)

        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        self.night_hour = cfg.get("nightmode_hour", 22)

    def load_status(self):
        with open(self.file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_status(self, data):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def night_enabled(self, guild_id: int) -> bool:
        data = self.load_status()
        return data.get(str(guild_id), False)

    night_group = app_commands.Group(name="nightmode", description="Manage night mode")

    @night_group.command(name="on", description="Enable night mode for this server")
    async def enable(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        data = self.load_status()
        data[str(interaction.guild.id)] = True
        self.save_status(data)
        await interaction.response.send_message("\U0001F319 Night mode enabled.", ephemeral=True)

    @night_group.command(name="off", description="Disable night mode for this server")
    async def disable(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        data = self.load_status()
        data[str(interaction.guild.id)] = False
        self.save_status(data)
        await interaction.response.send_message("\u2600\ufe0f Night mode disabled.", ephemeral=True)

    async def cog_app_command_group(self):
        return [self.night_group]

