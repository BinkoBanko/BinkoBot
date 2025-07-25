import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.goodnight import Goodnight
from discord import app_commands

class DummyBot:
    pass


def test_goodnight_commands_register():
    cog = Goodnight(DummyBot())
    command_names = {cmd.name for cmd in cog.__cog_app_commands__}
    assert 'goodnight' in command_names
    assert 'emojiattack' in command_names
