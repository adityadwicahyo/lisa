"""Settings: `config.default.json` (every setting, documented in docs/configuration.md) overlaid with your `config.json`.

Standard library only, because the hook loads it on every Claude Code event.
"""

import json

from lisa.paths import CONFIG_DEFAULT, CONFIG_USER


def merge(defaults, overrides):
    """Overlay `overrides` on `defaults`, section by section, so a user file only needs the changed keys.

    :param defaults: Full settings
    :param overrides: Partial settings that win
    """
    merged = dict(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config():
    config = json.loads(CONFIG_DEFAULT.read_text(encoding="utf-8"))
    if CONFIG_USER.exists():
        config = merge(config, json.loads(CONFIG_USER.read_text(encoding="utf-8-sig")))
    return config
