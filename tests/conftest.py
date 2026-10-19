import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "snapshot.json"


@pytest.fixture
def fixture_blocks():
    j = json.loads(FIXTURE.read_text())
    return {
        "identity": bytes.fromhex(j["identity"]),
        "config": bytes.fromhex(j["config"]),
        "layers": [bytes.fromhex(x) for x in j["layers"]],
        "macros": bytes.fromhex(j["macros"]),
        "key_colors": bytes.fromhex(j["key_colors"]),
        "palette": bytes.fromhex(j["palette"]),
    }
