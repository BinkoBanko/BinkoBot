import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
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

    @app_commands.command(name="setvibe", description="Set your current mood and get a matching role")
    async def setvibe(self, interaction: discord.Interaction, vibe: str):
        # Respond immediately to prevent timeout
        await interaction.response.defer()

        if not interaction.guild:
            await interaction.followup.send("❌ This command only works in servers!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # Find matching vibe category
        matched_category = None
        for category, keywords in self.get_mood_keywords().items():
            if any(keyword.lower() in vibe.lower() for keyword in keywords):
                matched_category = category
                break

        if not matched_category:
            await interaction.followup.send(
                f"❌ Couldn't match '{vibe}' to a mood! Try words like: happy, sad, excited, chill, chaotic, sleepy",
                ephemeral=True
            )
            return

        # Save user's vibe
        self.save_user_vibe(user_id, guild_id, matched_category, vibe)

        # Try to add role if possible
        try:
            role_name = f"🌟 {matched_category.title()}"
            role = discord.utils.get(interaction.guild.roles, name=role_name)

            if not role:
                # Try to create role
                try:
                    role = await interaction.guild.create_role(
                        name=role_name,
                        color=self.get_role_color(matched_category),
                        mentionable=False
                    )
                    logging.info(f"Created new role: {role_name}")
                except discord.Forbidden:
                    await interaction.followup.send(
                        f"✨ Vibe set to **{matched_category}**! (Couldn't create role - missing permissions)",
                        ephemeral=True
                    )
                    return

            # Remove old mood roles
            mood_roles = [r for r in interaction.user.roles if r.name.startswith("🌟 ")]
            for old_role in mood_roles:
                try:
                    await interaction.user.remove_roles(old_role)
                except discord.Forbidden:
                    pass

            # Add new role
            await interaction.user.add_roles(role)

            await interaction.followup.send(
                f"✨ Vibe set to **{matched_category}**! You now have the {role.mention} role! 🎭",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                f"✨ Vibe set to **{matched_category}**! (Couldn't manage roles - missing permissions)",
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error in setvibe: {e}")
            await interaction.followup.send(
                f"✨ Vibe set to **{matched_category}**! (Role error: {str(e)})",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    print("✅ mood_with_roles setup() called (auto-sync style)")
    await bot.add_cog(Mood(bot))