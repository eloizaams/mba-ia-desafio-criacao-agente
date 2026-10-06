import sqlite3
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from aurora.adapters.persistence.sqlite import RepositorioSqlite
from aurora.domain.erros import DataIndisponivel

CONCORRENTES = 20


def test_disputa_pela_mesma_area_e_data_tem_um_vencedor(banco: Path) -> None:
    repo = RepositorioSqlite(banco)
    apartamentos = ["101", "102", "201", "202", "301", "302"]
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
    with sqlite3.connect(banco) as conexao:
        (ativas,) = conexao.execute(
            "SELECT COUNT(*) FROM reservas WHERE area = 'salao-de-festas' "
            "AND data = '2030-05-11' AND status = 'ativa'"
        ).fetchone()
    assert ativas == 1
