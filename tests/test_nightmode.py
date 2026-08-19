import json
import asyncio

from modules.nightmode import NightMode


class DummyBot:
    pass


class DummyInteraction:
    def __init__(self, guild_id):
        self.guild = type("Guild", (), {"id": guild_id})()
        self.response = self
        self._sent = None

    async def send_message(self, msg, ephemeral=False):
        self._sent = msg

    # For compatibility with command check
    async def followup(self, *args, **kwargs):
        self._sent = args[0]

    @property
    def is_done(self):
        return False


def test_toggle_persists(tmp_path):
    file = tmp_path / "night.json"
    bot = DummyBot()
    cog = NightMode(bot)
    cog.file = str(file)
    with open(file, "w", encoding="utf-8") as f:
        json.dump({}, f)

    assert not cog.night_enabled(1)

    cog.save_status({"1": True})
    assert cog.night_enabled(1)

    cog.save_status({"1": False})
    assert not cog.night_enabled(1)
