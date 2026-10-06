import json
import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aurora.adapters.persistence.restore import restaurar
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.domain.erros import DataIndisponivel

DADOS = Path(__file__).parents[2] / "dados"


def _json(nome: str) -> list[dict[str, object]]:
    conteudo: list[dict[str, object]] = json.loads((DADOS / nome).read_text(encoding="utf-8"))
    return conteudo


def _linhas(banco: Path, sql: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(banco) as connection:
        return [tuple(row) for row in connection.execute(sql).fetchall()]


def _reservas_ativas(banco: Path) -> list[tuple[object, ...]]:
    return _linhas(
        banco,
        "SELECT codigo, apartamento, area, data FROM reservas "
        "WHERE status = 'ativa' ORDER BY codigo",
    )


def _visitantes(banco: Path) -> list[tuple[object, ...]]:
    return _linhas(
        banco, "SELECT apartamento, nome, data FROM visitantes ORDER BY apartamento, nome, data"
    )


def _esperado_reservas() -> list[tuple[object, ...]]:
    return sorted(
        (r["codigo"], r["apartamento"], r["area"], r["data"]) for r in _json("reservas.json")
    )


def _esperado_visitantes() -> list[tuple[object, ...]]:
    return sorted((v["apartamento"], v["nome"], v["data"]) for v in _json("visitantes.json"))


def test_restore_grava_exatamente_o_conteudo_dos_json(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"

    restaurar(banco, DADOS)

    assert _reservas_ativas(banco) == _esperado_reservas()
    assert _visitantes(banco) == _esperado_visitantes()
    areas = {(row[0], Decimal(str(row[1]))) for row in _linhas(banco, "SELECT id, taxa FROM areas")}
    assert areas == {(a["id"], Decimal(str(a["taxa"]))) for a in _json("areas.json")}


def _banco_inteiro(banco: Path) -> dict[str, list[tuple[object, ...]]]:
    tabelas = ("areas", "apartamentos", "reservas", "visitantes")
    return {tabela: _linhas(banco, f"SELECT * FROM {tabela} ORDER BY 1") for tabela in tabelas}


def test_restore_duas_vezes_produz_o_mesmo_banco_inteiro(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    primeiro = _banco_inteiro(banco)

    restaurar(banco, DADOS)

    assert _banco_inteiro(banco) == primeiro


def test_restore_desfaz_reservas_e_visitantes_da_conversa(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    repo = SqliteRepository(banco)
    repo.gravar_reserva("101", "salao-de-festas", date(2030, 4, 20))
    repo.autorizar("101", "Joana Ribeiro", date(2030, 4, 21))

    restaurar(banco, DADOS)

    assert _reservas_ativas(banco) == _esperado_reservas()
    assert _visitantes(banco) == _esperado_visitantes()


def test_reserva_do_seed_cancelada_volta_a_ativa_com_o_mesmo_codigo(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    SqliteRepository(banco).cancelar("101", "RSV-1377")

    restaurar(banco, DADOS)

    assert ("RSV-1377", "101", "quadra", "2030-03-09") in _reservas_ativas(banco)


def test_reserva_cancelada_fora_do_seed_fica_como_historico(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    repo = SqliteRepository(banco)
    criada = repo.gravar_reserva("101", "salao-de-festas", date(2030, 4, 20))
    repo.cancelar("101", criada.codigo)

    restaurar(banco, DADOS)

    historico = _linhas(banco, f"SELECT status FROM reservas WHERE codigo = '{criada.codigo}'")
    assert historico == [("cancelada",)]


def test_seed_continua_bloqueando_a_data_depois_do_restore(tmp_path: Path) -> None:
    banco = tmp_path / "aurora.db"
    restaurar(banco, DADOS)
    repo = SqliteRepository(banco)

    with pytest.raises(DataIndisponivel):
        repo.gravar_reserva("201", "quadra", date(2030, 3, 9))
