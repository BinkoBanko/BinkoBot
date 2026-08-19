import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.wholesome_chaos import WholesomeChaos  # noqa: E402
from discord import app_commands  # noqa: E402


class DummyBot:
    pass


def test_wholesome_chaos_commands_register():
    cog = WholesomeChaos(DummyBot())
    command_names = {cmd.name for cmd in cog.__cog_app_commands__}
    assert 'wholesome' in command_names
    assert 'chaos' in command_names
