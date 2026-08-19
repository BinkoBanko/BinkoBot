import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import modules.analytics as analytics  # noqa: E402

class DummyBot:
    pass


def test_analytics_disabled(monkeypatch):
    monkeypatch.setenv('ANALYTICS_ENABLED', '0')
    monkeypatch.setattr(analytics.os.path, 'exists', lambda _p: True)
    cog = analytics.Analytics(DummyBot())
    assert not cog.analytics_enabled
