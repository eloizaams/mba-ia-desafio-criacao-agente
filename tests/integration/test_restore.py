import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from aurora.adapters.persistence.restore import restaurar
from aurora.adapters.persistence.sqlite import RepositorioSqlite
from aurora.domain.erros import DataIndisponivel

DADOS = Path(__file__).parents[2] / "dados"


def _contagens(banco: Path) -> dict[str, int]:
    with sqlite3.connect(banco) as conexao:
        return {
            tabela: conexao.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("areas", "apartamentos", "reservas", "visitantes")
        }


def test_restore_carrega_os_json_de_dados(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"

    restaurar(banco, DADOS)

    esperado = {
        "areas": len(json.loads((DADOS / "areas.json").read_text())),
        "apartamentos": len(json.loads((DADOS / "apartamentos.json").read_text())),
        "reservas": len(json.loads((DADOS / "reservas.json").read_text())),
        "visitantes": len(json.loads((DADOS / "visitantes.json").read_text())),
    }
    assert _contagens(banco) == esperado


def test_restore_desfaz_mudancas_da_conversa_e_e_idempotente(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    repo = RepositorioSqlite(banco)
    repo.gravar_reserva("101", "salao-de-festas", date(2030, 4, 20))
    assert _contagens(banco)["reservas"] == 4

    restaurar(banco, DADOS)
    primeira = _contagens(banco)
    restaurar(banco, DADOS)

    assert primeira["reservas"] == 3
    assert _contagens(banco) == primeira


def test_reserva_do_seed_bloqueia_a_mesma_data(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    repo = RepositorioSqlite(banco)

    with pytest.raises(DataIndisponivel):
        repo.gravar_reserva("201", "quadra", date(2030, 3, 9))
