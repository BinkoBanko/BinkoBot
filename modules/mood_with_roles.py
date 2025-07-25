import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from config.valid_vibes import VALID_VIBES

class Mood(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vibes_file = "data/user_vibes.json"
        self.valid_vibes = VALID_VIBES

        if not os.path.exists(self.vibes_file):
            with open(self.vibes_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def load_vibes(self):
        with open(self.vibes_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_vibes(self, data):
        with open(self.vibes_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @app_commands.command(name="setvibe", description="Set your current mood/vibe")
    @app_commands.describe(vibe="Choose your vibe (soft, lewd, sad, etc.)")
    async def setvibe(self, interaction: discord.Interaction, vibe: str):
        vibe = vibe.lower()
        if vibe not in self.valid_vibes:
            await interaction.response.send_message(
                f"❌ Invalid vibe. Try one of: {', '.join(self.valid_vibes)}", ephemeral=True
            )
            return

        uid = str(interaction.user.id)
        data = self.load_vibes()
        data[uid] = {
            "vibe": vibe,
            "last_set": datetime.utcnow().isoformat()
        }
        self.save_vibes(data)

        if interaction.guild:
            guild = interaction.guild
            member = await guild.fetch_member(interaction.user.id)
            if not member:
                return

            role = discord.utils.get(guild.roles, name=vibe)
            if not role:
                role = await guild.create_role(name=vibe, reason="Created vibe role dynamically")

            roles_to_remove = [r for r in member.roles if r.name in self.valid_vibes and r != role]
            await member.remove_roles(*roles_to_remove, reason="Switching vibe role")
            await member.add_roles(role, reason="Assigned new vibe role")

        await interaction.response.send_message(
            f"🌟 Your vibe has been set to **{vibe}**!", ephemeral=True
        )

async def setup(bot: commands.Bot):
    print("✅ mood_with_roles setup() called (auto-sync style)")
    await bot.add_cog(Mood(bot))
