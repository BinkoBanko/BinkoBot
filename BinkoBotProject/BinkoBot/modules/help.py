
import discord
from discord.ext import commands
from discord import app_commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Get a list of BinkoBot commands by category")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧾 BinkoBot Command Guide",
            description="Here’s everything I can do, organized by category~",
            color=discord.Color.pink()
        )

        embed.add_field(
            name="💖 Affirmations",
            value="`/affirm`, `/comfort`, `/dailyhype`",
            inline=False
        )
        embed.add_field(
            name="🎭 Mood & Vibes",
            value="`/setvibe` – auto-assigns role + changes personality~",
            inline=False
        )
        embed.add_field(
            name="💘 Flirt & Touch",
            value="`/flirt`, `/nuzzle`, `/kiss`, `/pin`, `/tailwrap`, `/nsfw`",
            inline=False
        )
        embed.add_field(
            name="📝 Notes & Lore",
            value="`/note set`, `/note view`, `/note delete`, `/lore`, `/binkocard`",
            inline=False
        )
        embed.add_field(
            name="🔐 Settings & Privacy",
            value="`/dm optin`, `/dm optout`, `/privacy`",
            inline=False
        )
        embed.add_field(
            name="🎧 Tools & Stats",
            value="`/music`, `/stats`, `/help`",
            inline=False
        )

        embed.set_footer(text="Use commands in cozyspace or DMs for full effect 🌙")

        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("📩 I’ve sent you my command list in DMs~", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I couldn’t DM you! Please enable messages from server members 💌", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
