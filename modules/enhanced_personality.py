import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_FILE = "config.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def is_personality_enabled() -> bool:
    try:
        cfg = load_config()
    except FileNotFoundError:
        return True
    return cfg.get("enhanced_personality_enabled", True)


def set_personality_enabled(state: bool) -> None:
    try:
        cfg = load_config()
    except FileNotFoundError:
        cfg = {}
    cfg["enhanced_personality_enabled"] = state
    save_config(cfg)


class EnhancedPersonality(commands.Cog):
    """Toggle the bot's enhanced personality mode."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.enabled = is_personality_enabled()

    personality_group = app_commands.Group(
        name="personality", description="Manage enhanced personality"
    )

    @personality_group.command(name="on", description="Enable enhanced personality")
    async def personality_on(self, interaction: discord.Interaction):
        set_personality_enabled(True)
        self.enabled = True
        await interaction.response.send_message(
            "Enhanced personality enabled.", ephemeral=True
        )

    @personality_group.command(name="off", description="Disable enhanced personality")
    async def personality_off(self, interaction: discord.Interaction):
        set_personality_enabled(False)
        self.enabled = False
        await interaction.response.send_message(
            "Enhanced personality disabled.", ephemeral=True
        )

    async def cog_app_command_group(self):
        return [self.personality_group]


async def setup(bot: commands.Bot):
    await bot.add_cog(EnhancedPersonality(bot))
