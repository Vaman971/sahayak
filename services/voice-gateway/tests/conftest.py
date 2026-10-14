from collections.abc import Iterator
from pathlib import Path

import pytest
from sahayak_core.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    monkeypatch.setenv("SAHAYAK_ENV", "test")
    monkeypatch.setenv("SAHAYAK_RECORD_CALLS", "false")
    monkeypatch.setenv("SAHAYAK_RECORDINGS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
