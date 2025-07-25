import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.mental_support import MentalSupport

class DummyBot:
    pass

def test_contains_trigger_true():
    cog = MentalSupport(DummyBot())
    assert cog.contains_trigger("I want to die")

def test_contains_trigger_false():
    cog = MentalSupport(DummyBot())
    assert not cog.contains_trigger("Just saying hi")
