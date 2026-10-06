from pathlib import Path

import pytest

from aurora.config import database_path, regulamento_path


@pytest.mark.parametrize("valor", [None, ""])
def test_variavel_ausente_ou_vazia_usa_o_padrao(
    monkeypatch: pytest.MonkeyPatch, valor: str | None
) -> None:
    # `.env.example` traz as variáveis sem valor: o `load_dotenv` as define como "".
    for nome in ("AURORA_DB_PATH", "AURORA_REGULAMENTO_PATH"):
        if valor is None:
            monkeypatch.delenv(nome, raising=False)
        else:
            monkeypatch.setenv(nome, valor)

    assert database_path() == Path("aurora.db")
    assert regulamento_path() == Path("dados/regulamento.md")


def test_variavel_preenchida_vence_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AURORA_DB_PATH", "/tmp/outro.db")

    assert database_path() == Path("/tmp/outro.db")
