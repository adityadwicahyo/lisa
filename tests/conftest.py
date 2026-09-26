import json

import pytest

from lisa.paths import CONFIG_DEFAULT


@pytest.fixture
def config():
    """The shipped defaults only, so tests don't depend on a local config.json."""
    return json.loads(CONFIG_DEFAULT.read_text(encoding="utf-8"))
