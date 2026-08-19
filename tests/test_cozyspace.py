import importlib


def test_cozyspace_loads():
    module = importlib.import_module('modules.cozyspace')

    class DummyBot:
        pass

    cog = module.CozySpace(DummyBot())
    assert isinstance(cog, module.CozySpace)
