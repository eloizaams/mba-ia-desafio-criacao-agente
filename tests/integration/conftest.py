from collections.abc import Iterator
from pathlib import Path

import pytest

from aurora.adapters.persistence.restore import restaurar
from aurora.adapters.persistence.sqlite import RepositorioSqlite

DADOS = Path(__file__).parents[2] / "dados"


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    caminho = tmp_path / "aurora.db"
    restaurar(caminho, DADOS)
    return caminho


@pytest.fixture
def repo(banco: Path) -> Iterator[RepositorioSqlite]:
    yield RepositorioSqlite(banco)
