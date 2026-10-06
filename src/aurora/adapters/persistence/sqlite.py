import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

from aurora.adapters.persistence.connection import open_connection
from aurora.domain.area import Area
from aurora.domain.codigo import gerar_codigo_reserva
from aurora.domain.erros import DataIndisponivel, ReservaNaoEncontrada
from aurora.domain.reserva import Reserva, StatusReserva
from aurora.domain.visitante import Visitante

CODE_ATTEMPTS = 5

# A mensagem do SQLite cita as colunas da constraint violada, não o nome do índice.
# O índice parcial aparece como "reservas.area, reservas.data"; o código, como "reservas.codigo".
# Testes de integração cobrem os dois casos: se a versão do SQLite mudar o texto, eles falham.
_AGENDA_COLUMNS = "reservas.area, reservas.data"
_CODE_COLUMN = "reservas.codigo"


class SqliteRepository:
    """Implementa as portas de application/portas.py sobre SQLite.

    Uma conexão curta por operação: sem estado compartilhado entre threads.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = open_connection(self._path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def existe(self, numero: str) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM apartamentos WHERE numero = ?", (numero,)
            ).fetchone()
        return row is not None

    def buscar(self, area_id: str) -> Area | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, nome, taxa FROM areas WHERE id = ?", (area_id,)
            ).fetchone()
        if row is None:
            return None
        return _area_from_row(row)

    def listar(self) -> list[Area]:
        with self._connection() as connection:
            rows = connection.execute("SELECT id, nome, taxa FROM areas ORDER BY nome").fetchall()
        return [_area_from_row(row) for row in rows]

    def ocupada(self, area: str, data: date) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM reservas WHERE area = ? AND data = ? AND status = ?",
                (area, data.isoformat(), StatusReserva.ATIVA),
            ).fetchone()
        return row is not None

    def gravar_reserva(self, apartamento: str, area: str, data: date) -> Reserva:
        for _ in range(CODE_ATTEMPTS):
            codigo = gerar_codigo_reserva()
            try:
                with self._connection() as connection:
                    connection.execute(
                        "INSERT INTO reservas (codigo, apartamento, area, data, status) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (codigo, apartamento, area, data.isoformat(), StatusReserva.ATIVA),
                    )
            except sqlite3.IntegrityError as erro:
                mensagem = str(erro)
                if _AGENDA_COLUMNS in mensagem:
                    raise DataIndisponivel(f"{area} em {data.isoformat()}") from erro
                if _CODE_COLUMN in mensagem:
                    continue
                raise
            return Reserva(codigo=codigo, apartamento=apartamento, area=area, data=data)
        raise RuntimeError("não foi possível gerar um código de reserva único")

    def reservas_ativas_do_apartamento(self, apartamento: str) -> list[Reserva]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT codigo, apartamento, area, data, status FROM reservas "
                "WHERE apartamento = ? AND status = ? ORDER BY data, codigo",
                (apartamento, StatusReserva.ATIVA),
            ).fetchall()
        return [_reservation_from_row(row) for row in rows]

    def cancelar(self, apartamento: str, codigo: str) -> Reserva:
        # O filtro por apartamento fica no UPDATE: reserva alheia não é alterada nem revelada.
        with self._connection() as connection:
            rows = connection.execute(
                "UPDATE reservas SET status = ? "
                "WHERE codigo = ? AND apartamento = ? AND status = ? "
                "RETURNING codigo, apartamento, area, data, status",
                (StatusReserva.CANCELADA, codigo, apartamento, StatusReserva.ATIVA),
            ).fetchall()
        if not rows:
            raise ReservaNaoEncontrada(codigo)
        return _reservation_from_row(rows[0])

    def autorizar(self, apartamento: str, nome: str, data: date) -> Visitante:
        # Valida antes de gravar: o domínio recusa nome vazio.
        visitante = Visitante(apartamento=apartamento, nome=nome, data=data)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                (apartamento, nome, data.isoformat()),
            )
        return visitante

    def do_apartamento(self, apartamento: str) -> list[Visitante]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT apartamento, nome, data FROM visitantes "
                "WHERE apartamento = ? ORDER BY data, id",
                (apartamento,),
            ).fetchall()
        return [
            Visitante(
                apartamento=row["apartamento"],
                nome=row["nome"],
                data=date.fromisoformat(row["data"]),
            )
            for row in rows
        ]


def _area_from_row(row: sqlite3.Row) -> Area:
    return Area(id=row["id"], nome=row["nome"], taxa=Decimal(row["taxa"]))


def _reservation_from_row(row: sqlite3.Row) -> Reserva:
    return Reserva(
        codigo=row["codigo"],
        apartamento=row["apartamento"],
        area=row["area"],
        data=date.fromisoformat(row["data"]),
        status=StatusReserva(row["status"]),
    )
