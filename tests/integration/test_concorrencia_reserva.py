import sqlite3
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.domain.erros import DataIndisponivel

CONCORRENTES = 20
APARTAMENTOS = ["101", "102", "201", "202", "301", "302"]


def test_disputa_pela_mesma_area_e_data_tem_um_vencedor(banco: Path) -> None:
    repo = SqliteRepository(banco)
    apartamentos = APARTAMENTOS
    barreira = threading.Barrier(CONCORRENTES)

    def tentar(indice: int) -> str:
        barreira.wait()
        try:
            repo.gravar_reserva(
                apartamentos[indice % len(apartamentos)], "salao-de-festas", date(2030, 5, 11)
            )
        except DataIndisponivel:
            return "indisponivel"
        return "gravada"

    with ThreadPoolExecutor(max_workers=CONCORRENTES) as pool:
        resultados = Counter(pool.map(tentar, range(CONCORRENTES)))

    assert resultados == Counter({"gravada": 1, "indisponivel": CONCORRENTES - 1})
    with sqlite3.connect(banco) as connection:
        (ativas,) = connection.execute(
            "SELECT COUNT(*) FROM reservas WHERE area = 'salao-de-festas' "
            "AND data = '2030-05-11' AND status = 'ativa'"
        ).fetchone()
    assert ativas == 1


def test_sem_o_indice_checar_e_gravar_deixa_todos_gravarem(banco: Path) -> None:
    # Prova de contraste: sem a constraint, a checagem prévia não impede nada.
    # A barreira entre checar e gravar força todas as checagens antes de qualquer gravação.
    with sqlite3.connect(banco) as connection:
        connection.execute("DROP INDEX uq_reserva_ativa_area_data")
    repo = SqliteRepository(banco)
    barreira = threading.Barrier(CONCORRENTES)

    def checar_e_gravar(indice: int) -> str:
        livre = not repo.ocupada("salao-de-festas", date(2030, 5, 11))
        barreira.wait()
        if livre:
            repo.gravar_reserva(
                APARTAMENTOS[indice % len(APARTAMENTOS)],
                "salao-de-festas",
                date(2030, 5, 11),
            )
            return "gravada"
        return "indisponivel"

    with ThreadPoolExecutor(max_workers=CONCORRENTES) as pool:
        resultados = Counter(pool.map(checar_e_gravar, range(CONCORRENTES)))

    assert resultados == Counter({"gravada": CONCORRENTES})
