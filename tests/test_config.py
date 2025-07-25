import json


def test_config_has_prefix():
    with open('config.json', encoding='utf-8') as f:
        config = json.load(f)
    assert config.get('prefix') is not None
