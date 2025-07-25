import importlib


def test_music_player_loads():
    module = importlib.import_module('modules.music_player')

    class DummyBot:
        pass

    cog = module.MusicPlayer(DummyBot())
    assert isinstance(cog, module.MusicPlayer)
