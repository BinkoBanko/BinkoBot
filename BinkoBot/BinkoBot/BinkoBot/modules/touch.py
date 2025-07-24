import discord
from discord.ext import commands
from discord import app_commands
import random

class Touch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gestures = {
            "nuzzle": [
                "*nuzzles up to you gently, tail curling around your ankle~*",
                "*presses my nose to your cheek and stays there, warm and close~*",
                "*gives you the softest head bump before curling into your side~*"
            ],
            "tailwrap": [
                "*wraps my tail snugly around your thigh and hums contentedly~*",
                "*circles you once before my tail finds your waist—tight, soft, protective.*",
                "*slides in close and loops my tail lazily over your lap.*"
            ],
            "kiss": [
                "*presses a soft kiss to your temple*",
                "*places a lingering kiss on your neck with a quiet smile~*",
                "*gives you a sudden kiss, bold and full of affection~*"
            ],
            "pin": [
                "*pushes you gently against the wall with a grin.*",
                "*grabs your wrists and pins them softly, but firmly, to the bed.*",
                "*corners you with a wicked smirk—guess what happens next~?*"
            ]
        }

    def get_response(self, gesture):
        return random.choice(self.gestures.get(gesture, ["*...blinks and does nothing.*"]))

    async def send_touch(self, interaction: discord.Interaction, gesture: str, user: discord.User = None):
        action = self.get_response(gesture)
        if user:
            msg = f"{user.mention} {action}"
            await interaction.response.send_message(msg)
        else:
            await interaction.response.send_message(f"*{action}*", ephemeral=True)

    @app_commands.command(name="nuzzle", description="Give someone a soft nuzzle")
    @app_commands.describe(user="Who to nuzzle")
    async def nuzzle(self, interaction: discord.Interaction, user: discord.User = None):
        await self.send_touch(interaction, "nuzzle", user)

    @app_commands.command(name="tailwrap", description="Wrap your tail around someone")
    @app_commands.describe(user="Who to tailwrap")
    async def tailwrap(self, interaction: discord.Interaction, user: discord.User = None):
        await self.send_touch(interaction, "tailwrap", user)

    @app_commands.command(name="kiss", description="Send a kiss")
    @app_commands.describe(user="Who to kiss")
    async def kiss(self, interaction: discord.Interaction, user: discord.User = None):
        await self.send_touch(interaction, "kiss", user)

    @app_commands.command(name="pin", description="Pin someone (playfully)")
    @app_commands.describe(user="Who to pin")
    async def pin(self, interaction: discord.Interaction, user: discord.User = None):
        await self.send_touch(interaction, "pin", user)

async def setup(bot: commands.Bot):
    await bot.add_cog(Touch(bot))
