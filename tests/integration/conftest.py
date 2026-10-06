from collections.abc import Iterator
from pathlib import Path

import pytest

from aurora.adapters.persistence.restore import restaurar
from aurora.adapters.persistence.sqlite import SqliteRepository

DADOS = Path(__file__).parents[2] / "dados"


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    path = tmp_path / "aurora.db"
    restaurar(path, DADOS)
    return path


@pytest.fixture
def repo(banco: Path) -> Iterator[SqliteRepository]:
    yield SqliteRepository(banco)
