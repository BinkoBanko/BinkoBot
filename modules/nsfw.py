import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class NSFW(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file = "data/nsfw_status.json"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def load_data(self):
        with open(self.file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_data(self, data):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def is_cozy_or_dm(self, interaction):
        return isinstance(interaction.channel, discord.DMChannel) or \
               ("cozy" in interaction.channel.name.lower() if interaction.channel else False)

    nsfw_group = app_commands.Group(name="nsfw", description="Manage your lewd/NSFW interaction settings")

    @nsfw_group.command(name="enable", description="Enable lewd mode (only in cozyspace or DMs)")
    async def enable(self, interaction: discord.Interaction):
        if not self.is_cozy_or_dm(interaction):
            await interaction.response.send_message(
                "❌ You can only enable lewd mode in DMs or a channel with 'cozy' in its name.", ephemeral=True
            )
            return

        data = self.load_data()
        data[str(interaction.user.id)] = True
        self.save_data(data)

        await interaction.response.send_message(
            "🔞 Lewd mode enabled. Be gentle, or don’t. I’m ready either way~", ephemeral=True
        )

    @nsfw_group.command(name="disable", description="Disable lewd mode")
    async def disable(self, interaction: discord.Interaction):
        data = self.load_data()
        data[str(interaction.user.id)] = False
        self.save_data(data)

        await interaction.response.send_message(
            "Lewd mode disabled. Returning to wholesome tailwraps~", ephemeral=True
        )

    @nsfw_group.command(name="safeword", description="Panic reset (disable lewd mode immediately)")
    async def safeword(self, interaction: discord.Interaction):
        data = self.load_data()
        uid = str(interaction.user.id)

        if uid in data and data[uid] is True:
            data[uid] = False
            self.save_data(data)
            await interaction.response.send_message(
                "🛑 Lewd mode has been disabled. You're safe now, sweetheart.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You weren’t in lewd mode, but I appreciate the caution. 💖", ephemeral=True
            )

    async def cog_app_command_group(self):
        return [self.nsfw_group]

async def setup(bot: commands.Bot):
    await bot.add_cog(NSFW(bot))
