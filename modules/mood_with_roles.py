import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
from datetime import datetime, timezone
from config.valid_vibes import VALID_VIBES


# Colour per vibe for the Discord role.
_ROLE_COLOURS: dict[str, discord.Colour] = {
    "soft":       discord.Colour.from_rgb(255, 182, 193),   # pastel pink
    "chaotic":    discord.Colour.from_rgb(255, 140,   0),   # orange
    "lewd":       discord.Colour.from_rgb(220,  20,  60),   # crimson
    "sad":        discord.Colour.from_rgb( 70, 130, 180),   # steel blue
    "protective": discord.Colour.from_rgb( 34, 139,  34),   # forest green
    "neutral":    discord.Colour.from_rgb(169, 169, 169),   # grey
}


class Mood(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vibes_file = "data/user_vibes.json"
        self.valid_vibes = VALID_VIBES

        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.vibes_file):
            with open(self.vibes_file, "w", encoding="utf-8") as f:
                json.dump({}, f)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def load_vibes(self) -> dict:
        try:
            with open(self.vibes_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_vibes(self, data: dict) -> None:
        with open(self.vibes_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_user_vibe(self, user_id: str, guild_id: str, vibe: str) -> None:
        data = self.load_vibes()
        data[user_id] = {
            "vibe": vibe,
            "guild_id": guild_id,
            "last_set": datetime.now(timezone.utc).isoformat(),
        }
        self.save_vibes(data)

    def get_role_colour(self, vibe: str) -> discord.Colour:
        return _ROLE_COLOURS.get(vibe, discord.Colour.default())

    # ------------------------------------------------------------------
    # /setvibe command — string parameter with autocomplete
    # ------------------------------------------------------------------

    @app_commands.command(name="setvibe", description="Set your current mood and get a matching role")
    @app_commands.describe(vibe="Start typing to see available vibes")
    async def setvibe(self, interaction: discord.Interaction, vibe: str):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ This command only works in servers!", ephemeral=True)
            return

        # Server-side validation: autocomplete is a hint, not a guarantee.
        chosen = vibe.strip().lower()
        if chosen not in self.valid_vibes:
            vibe_list = ", ".join(f"**{v}**" for v in self.valid_vibes)
            await interaction.followup.send(
                f"❌ **{vibe}** isn't a valid vibe! Choose one of: {vibe_list}",
                ephemeral=True,
            )
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        # Persist the vibe first so even a role-permission failure still records it.
        self.save_user_vibe(user_id, guild_id, chosen)

        # --- Role management ---
        new_role_name = f"🌟 {chosen.title()}"
        try:
            # 1. Collect the user's existing vibe roles before we touch anything.
            old_vibe_roles = [r for r in interaction.user.roles if r.name.startswith("🌟 ")]

            # 2. Ensure the new role exists.
            new_role = discord.utils.get(interaction.guild.roles, name=new_role_name)
            if not new_role:
                new_role = await interaction.guild.create_role(
                    name=new_role_name,
                    colour=self.get_role_colour(chosen),
                    mentionable=False,
                )
                logging.info(f"Created vibe role: {new_role_name}")

            # 3. Remove old vibe roles from the user.
            #    We intentionally do NOT delete roles from the server:
            #    the bot runs without the Members intent, so guild.members is an
            #    incomplete cache and we cannot safely determine whether a role
            #    still has other holders. Server role cleanup can be done manually.
            for old_role in old_vibe_roles:
                if old_role.id == new_role.id:
                    continue  # already wearing the right role – skip
                try:
                    await interaction.user.remove_roles(old_role, reason="Vibe changed")
                except discord.Forbidden:
                    pass

            # 4. Assign the new role only when the member doesn't already have it.
            already_has_role = any(r.id == new_role.id for r in interaction.user.roles)
            if not already_has_role:
                await interaction.user.add_roles(new_role, reason="Vibe set")

            await interaction.followup.send(
                f"✨ Vibe set to **{chosen}**! You now have the {new_role.mention} role! 🎭",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                f"✨ Vibe set to **{chosen}**! "
                f"(I don't have permission to manage roles — ask a server admin to grant me the Manage Roles permission.)",
                ephemeral=True,
            )
        except Exception as e:
            logging.error(f"Error in setvibe: {e}")
            await interaction.followup.send(
                f"✨ Vibe set to **{chosen}**! (Role update failed: {e})",
                ephemeral=True,
            )

    @setvibe.autocomplete("vibe")
    async def setvibe_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Return matching vibes as the user types, filtered by what they've typed so far."""
        current_lower = current.lower()
        return [
            app_commands.Choice(name=v.title(), value=v)
            for v in self.valid_vibes
            if current_lower in v
        ]


async def setup(bot: commands.Bot):
    await bot.add_cog(Mood(bot))
