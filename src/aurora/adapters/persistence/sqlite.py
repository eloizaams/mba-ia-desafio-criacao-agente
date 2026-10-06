import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

from aurora.adapters.persistence.schema import criar_schema
from aurora.domain.area import Area
from aurora.domain.codigo import gerar_codigo_reserva
from aurora.domain.erros import DataIndisponivel, ReservaNaoEncontrada
from aurora.domain.reserva import Reserva, StatusReserva
from aurora.domain.visitante import Visitante

# Escritas concorrentes esperam até 5 s pelo lock do SQLite, sem "database is locked".
TIMEOUT_LOCK_S = 5.0
TENTATIVAS_CODIGO = 5

# A mensagem do SQLite cita as colunas da constraint violada, não o nome do índice.
# O índice parcial aparece como "reservas.area, reservas.data"; o código, como "reservas.codigo".
# Testes de integração cobrem os dois casos: se a versão do SQLite mudar o texto, eles falham.
_COLUNAS_AGENDA = "reservas.area, reservas.data"
_COLUNA_CODIGO = "reservas.codigo"


class RepositorioSqlite:
    """Implementa as portas de application/portas.py sobre SQLite.

    Uma conexão curta por operação: sem estado compartilhado entre threads.
    """

    def __init__(self, caminho: Path) -> None:
        self._caminho = caminho

    @contextmanager
    def _conexao(self) -> Iterator[sqlite3.Connection]:
        conexao = sqlite3.connect(self._caminho, timeout=TIMEOUT_LOCK_S)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        try:
            with conexao:
                yield conexao
        finally:
            conexao.close()

    def inicializar(self) -> None:
        with self._conexao() as conexao:
            criar_schema(conexao)
            conexao.execute("PRAGMA journal_mode = WAL")

    def buscar(self, area_id: str) -> Area | None:
        with self._conexao() as conexao:
            linha = conexao.execute(
                "SELECT id, nome, taxa FROM areas WHERE id = ?", (area_id,)
            ).fetchone()
        if linha is None:
            return None
        return Area(id=linha["id"], nome=linha["nome"], taxa=Decimal(linha["taxa"]))

    def ocupada(self, area: str, data: date) -> bool:
        with self._conexao() as conexao:
            linha = conexao.execute(
                "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND status = ?",
                (area, data.isoformat(), StatusReserva.ATIVA),
            ).fetchone()
        return linha is not None

    def gravar_reserva(self, apartamento: str, area: str, data: date) -> Reserva:
        for _ in range(TENTATIVAS_CODIGO):
            codigo = gerar_codigo_reserva()
            try:
                with self._conexao() as conexao:
                    conexao.execute(
                        "INSERT INTO reservas (codigo, apartamento, area, data, status) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (codigo, apartamento, area, data.isoformat(), StatusReserva.ATIVA),
                    )
            except sqlite3.IntegrityError as erro:
                mensagem = str(erro)
                if _COLUNAS_AGENDA in mensagem:
                    raise DataIndisponivel(f"{area} em {data.isoformat()}") from erro
                if _COLUNA_CODIGO in mensagem:
                    continue
                raise
            return Reserva(codigo=codigo, apartamento=apartamento, area=area, data=data)
        raise RuntimeError("não foi possível gerar um código de reserva único")

    def reservas_ativas_do_apartamento(self, apartamento: str) -> list[Reserva]:
        with self._conexao() as conexao:
            linhas = conexao.execute(
                "SELECT codigo, apartamento, area, data, status FROM reservas "
                "WHERE apartamento = ? AND status = ? ORDER BY data, codigo",
                (apartamento, StatusReserva.ATIVA),
            ).fetchall()
        return [_reserva_da_linha(linha) for linha in linhas]

    def cancelar(self, apartamento: str, codigo: str) -> Reserva:
        # O filtro por apartamento fica no UPDATE: reserva alheia não é alterada nem revelada.
        with self._conexao() as conexao:
            linhas = conexao.execute(
                "UPDATE reservas SET status = ? "
                "WHERE codigo = ? AND apartamento = ? AND status = ? "
                "RETURNING codigo, apartamento, area, data, status",
                (StatusReserva.CANCELADA, codigo, apartamento, StatusReserva.ATIVA),
            ).fetchall()
        if not linhas:
            raise ReservaNaoEncontrada(codigo)
        return _reserva_da_linha(linhas[0])

    def autorizar(self, apartamento: str, nome: str, data: date) -> Visitante:
        with self._conexao() as conexao:
            conexao.execute(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                (apartamento, nome, data.isoformat()),
            )
        return Visitante(apartamento=apartamento, nome=nome, data=data)

    def do_apartamento(self, apartamento: str) -> list[Visitante]:
        with self._conexao() as conexao:
            linhas = conexao.execute(
                "SELECT apartamento, nome, data FROM visitantes "
                "WHERE apartamento = ? ORDER BY data, id",
                (apartamento,),
            ).fetchall()
        return [
            Visitante(
                apartamento=linha["apartamento"],
                nome=linha["nome"],
                data=date.fromisoformat(linha["data"]),
            )
            for linha in linhas
        ]


def _reserva_da_linha(linha: sqlite3.Row) -> Reserva:
    return Reserva(
        codigo=linha["codigo"],
        apartamento=linha["apartamento"],
        area=linha["area"],
        data=date.fromisoformat(linha["data"]),
        status=StatusReserva(linha["status"]),
    )
