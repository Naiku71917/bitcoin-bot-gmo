from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    path = tmp_path / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path
