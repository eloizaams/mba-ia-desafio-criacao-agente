from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from google.adk.runners import Runner

from aurora.adapters.adk.agentes import (
    NOME_RAIZ,
    NOME_REGULAMENTO,
    NOME_RESERVAS,
    NOME_VISITANTES,
)
from aurora.adapters.adk.app import construir_runner
from aurora.adapters.persistence.restore import restaurar
from aurora.adapters.persistence.sqlite import SqliteRepository
from tests.support.scripted_llm import ScriptedLlm

DADOS = Path(__file__).parents[2] / "dados"
REGULAMENTO = DADOS / "regulamento.md"


@pytest.fixture
def banco(tmp_path: Path) -> Path:
    path = tmp_path / "aurora.db"
    restaurar(path, DADOS)
    return path


@pytest.fixture
def repo(banco: Path) -> Iterator[SqliteRepository]:
    yield SqliteRepository(banco)


@pytest.fixture
def modelos() -> dict[str, ScriptedLlm]:
    """Um modelo roteirizado por agente. O teste ajusta o roteiro antes de subir o Runner."""
    return {
        nome: ScriptedLlm()
        for nome in (NOME_RAIZ, NOME_RESERVAS, NOME_VISITANTES, NOME_REGULAMENTO)
    }


@pytest.fixture
def novo_runner(banco: Path, modelos: dict[str, ScriptedLlm]) -> Callable[[], Runner]:
    """Fábrica, não instância: chamar de novo é o que simula a API reiniciada.

    Nada sobrevive em memória entre as chamadas; só o SQLite atravessa.
    """

    def _novo() -> Runner:
        return construir_runner(
            banco=banco, regulamento=REGULAMENTO, modelo=lambda nome: modelos[nome]
        )

    return _novo
