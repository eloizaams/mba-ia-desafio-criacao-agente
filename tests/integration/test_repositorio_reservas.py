from datetime import date

import pytest

from aurora.adapters.persistence import sqlite as modulo_sqlite
from aurora.adapters.persistence.sqlite import RepositorioSqlite
from aurora.domain.erros import DataIndisponivel, ReservaNaoEncontrada
from aurora.domain.reserva import StatusReserva

SALAO = "salao-de-festas"
DATA = date(2030, 4, 20)


def test_reserva_gravada_aparece_so_para_o_apartamento_dela(repo: RepositorioSqlite) -> None:
    reserva = repo.gravar_reserva("101", SALAO, DATA)

    codigos_101 = [r.codigo for r in repo.reservas_ativas_do_apartamento("101")]
    assert codigos_101 == ["RSV-1377", reserva.codigo]
    assert [r.codigo for r in repo.reservas_ativas_do_apartamento("302")] == ["RSV-4821"]


def test_mesma_area_e_data_nao_grava_duas_reservas_ativas(repo: RepositorioSqlite) -> None:
    repo.gravar_reserva("101", SALAO, DATA)

    with pytest.raises(DataIndisponivel):
        repo.gravar_reserva("201", SALAO, DATA)


def test_ocupada_reflete_a_agenda_sem_revelar_quem_reservou(repo: RepositorioSqlite) -> None:
    assert repo.ocupada(SALAO, DATA) is False

    repo.gravar_reserva("101", SALAO, DATA)

    assert repo.ocupada(SALAO, DATA) is True


def test_cancelar_libera_a_data_e_o_codigo_nao_volta(repo: RepositorioSqlite) -> None:
    antiga = repo.gravar_reserva("101", SALAO, DATA)
    cancelada = repo.cancelar("101", antiga.codigo)

    nova = repo.gravar_reserva("201", SALAO, DATA)

    assert cancelada.status is StatusReserva.CANCELADA
    assert nova.codigo != antiga.codigo
    assert antiga.codigo not in [r.codigo for r in repo.reservas_ativas_do_apartamento("101")]


def test_cancelar_reserva_de_outro_apartamento_nao_altera_nada(
    repo: RepositorioSqlite,
) -> None:
    with pytest.raises(ReservaNaoEncontrada):
        repo.cancelar("101", "RSV-4821")

    assert [r.codigo for r in repo.reservas_ativas_do_apartamento("302")] == ["RSV-4821"]


def test_cancelar_duas_vezes_diz_nao_encontrada_na_segunda(repo: RepositorioSqlite) -> None:
    reserva = repo.gravar_reserva("101", SALAO, DATA)
    repo.cancelar("101", reserva.codigo)

    with pytest.raises(ReservaNaoEncontrada):
        repo.cancelar("101", reserva.codigo)


def test_codigo_colidido_gera_outro_codigo(
    repo: RepositorioSqlite, monkeypatch: pytest.MonkeyPatch
) -> None:
    sorteios = iter(["RSV-1377", "RSV-NOVO"])
    monkeypatch.setattr(modulo_sqlite, "gerar_codigo_reserva", lambda: next(sorteios))

    reserva = repo.gravar_reserva("101", SALAO, DATA)

    assert reserva.codigo == "RSV-NOVO"


def test_codigo_de_reserva_cancelada_nunca_e_reaproveitado(
    repo: RepositorioSqlite, monkeypatch: pytest.MonkeyPatch
) -> None:
    cancelada = repo.gravar_reserva("101", SALAO, DATA)
    repo.cancelar("101", cancelada.codigo)
    monkeypatch.setattr(modulo_sqlite, "gerar_codigo_reserva", lambda: cancelada.codigo)

    with pytest.raises(RuntimeError):
        repo.gravar_reserva("201", SALAO, date(2030, 4, 21))


def test_visitante_autorizado_persiste_e_lista_por_apartamento(repo: RepositorioSqlite) -> None:
    repo.autorizar("101", "Joana Ribeiro", date(2030, 4, 21))

    visitantes = repo.do_apartamento("101")

    assert [(v.nome, v.data) for v in visitantes] == [("Joana Ribeiro", date(2030, 4, 21))]
    assert repo.do_apartamento("302")[0].nome == "Marina Duarte"
