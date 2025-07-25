import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class Notes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/user_notes.json"
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def load_notes(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_notes(self, notes):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2)

    note_group = app_commands.Group(name="note", description="Manage your personal notes")

    @note_group.command(name="set", description="Save a personal note for later")
    @app_commands.describe(content="The note you want to save")
    async def set_note(self, interaction: discord.Interaction, content: str):
        notes = self.load_notes()
        notes[str(interaction.user.id)] = content
        self.save_notes(notes)

        await interaction.response.send_message("✅ Your note has been saved.", ephemeral=True)

    @note_group.command(name="view", description="View your saved personal note")
    async def view_note(self, interaction: discord.Interaction):
        notes = self.load_notes()
        note = notes.get(str(interaction.user.id))

        if note:
            await interaction.response.send_message(f"📓 Your note: {note}", ephemeral=True)
        else:
            await interaction.response.send_message("You don’t have a note saved.", ephemeral=True)

    @note_group.command(name="delete", description="Delete your saved note")
    async def delete_note(self, interaction: discord.Interaction):
        notes = self.load_notes()
        uid = str(interaction.user.id)

        if uid in notes:
            del notes[uid]
            self.save_notes(notes)
            await interaction.response.send_message("🗑️ Your note has been deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("No note found to delete.", ephemeral=True)

    async def cog_app_command_group(self):
        return [self.note_group]

async def setup(bot: commands.Bot):
    await bot.add_cog(Notes(bot))
