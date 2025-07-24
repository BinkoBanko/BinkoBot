
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from collections import Counter
from datetime import datetime

class Analytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/analytics.json"
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def log_usage(self, user_id, command_name):
        with open(self.data_file, "r", encoding="utf-8") as f:
            logs = json.load(f)

        logs.append({
            "user_id": user_id,
            "command": command_name,
            "timestamp": datetime.utcnow().isoformat()
        })

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command):
        if interaction.user and command:
            self.log_usage(str(interaction.user.id), command.name)

    @app_commands.command(name="stats", description="View command usage statistics")
    async def stats(self, interaction: discord.Interaction):
        if not os.path.exists(self.data_file):
            await interaction.response.send_message("No analytics data found.", ephemeral=True)
            return

        with open(self.data_file, "r", encoding="utf-8") as f:
            logs = json.load(f)

        user_logs = [entry for entry in logs if entry["user_id"] == str(interaction.user.id)]
        all_commands = [entry["command"] for entry in logs]
        personal_commands = [entry["command"] for entry in user_logs]

        most_used = Counter(all_commands).most_common(3)
        user_used = Counter(personal_commands).most_common(3)

        embed = discord.Embed(title="📊 BinkoBot Usage Stats", color=discord.Color.blurple())
        embed.add_field(name="Top Global Commands", value="\n".join([f"`{cmd}`: {count}" for cmd, count in most_used]) or "No data yet", inline=False)
        embed.add_field(name="Your Top Commands", value="\n".join([f"`{cmd}`: {count}" for cmd, count in user_used]) or "No personal usage yet", inline=False)
        embed.set_footer(text="Tracked since first launch")

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Analytics(bot))
