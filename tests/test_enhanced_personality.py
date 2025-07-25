import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules import enhanced_personality as ep  # noqa: E402

class DummyBot:
    pass


def test_toggle_persists(tmp_path):
    cfg = tmp_path / "config.json"
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump({}, f)

    ep.CONFIG_FILE = str(cfg)
    cog = ep.EnhancedPersonality(DummyBot())

    ep.set_personality_enabled(True)
    assert ep.is_personality_enabled()
    assert cog.enabled

    ep.set_personality_enabled(False)
    assert not ep.is_personality_enabled()

