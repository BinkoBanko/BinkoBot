import discord
from discord.ext import commands
from discord import app_commands


class CozySpace(commands.Cog):
    """Manage the cozyspace text channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    cozyspace_group = app_commands.Group(
        name="cozyspace", description="Manage the cozyspace channel"
    )

    @cozyspace_group.command(name="create", description="Create the cozyspace channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def create_channel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        existing = discord.utils.get(guild.text_channels, name="cozyspace")
        if existing:
            await interaction.response.send_message(
                "#cozyspace already exists.", ephemeral=True
            )
            return
        try:
            await guild.create_text_channel("cozyspace")
            await interaction.response.send_message(
                "Created #cozyspace.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I lack permissions to create the channel.", ephemeral=True
            )

    @cozyspace_group.command(name="delete", description="Delete the cozyspace channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def delete_channel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )
            return
        channel = discord.utils.get(guild.text_channels, name="cozyspace")
        if not channel:
            await interaction.response.send_message(
                "#cozyspace does not exist.", ephemeral=True
            )
            return
        try:
            await channel.delete()
            await interaction.response.send_message(
                "Deleted #cozyspace.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I lack permissions to delete the channel.", ephemeral=True
            )

    async def cog_app_command_group(self):
        return [self.cozyspace_group]


async def setup(bot: commands.Bot):
    await bot.add_cog(CozySpace(bot))
