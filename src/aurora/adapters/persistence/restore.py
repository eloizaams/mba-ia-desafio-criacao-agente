import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from aurora.adapters.persistence.connection import open_connection
from aurora.adapters.persistence.schema import create_schema
from aurora.config import database_path, sessions_path
from aurora.domain.reserva import StatusReserva

DADOS_PADRAO = Path("dados")

# Áreas e apartamentos são upsert: reservas canceladas os referenciam por FK, então não podem sumir.
_UPSERT_AREA = (
    "INSERT INTO areas (id, nome, taxa) VALUES (:id, :nome, :taxa) "
    "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, taxa = excluded.taxa"
)
_UPSERT_APARTAMENTO = (
    "INSERT INTO apartamentos (numero, morador) VALUES (:numero, :morador) "
    "ON CONFLICT(numero) DO UPDATE SET morador = excluded.morador"
)
# Reserva do seed cancelada volta a ativa com o mesmo código: é estado inicial, não reserva nova.
_UPSERT_RESERVA = (
    "INSERT INTO reservas (codigo, apartamento, area, data, status) "
    "VALUES (:codigo, :apartamento, :area, :data, :status) "
    "ON CONFLICT(codigo) DO UPDATE SET apartamento = excluded.apartamento, "
    "area = excluded.area, data = excluded.data, status = excluded.status"
)
_INSERT_VISITANTE = (
    "INSERT INTO visitantes (apartamento, nome, data) VALUES (:apartamento, :nome, :data)"
)


def apagar_sessoes(database: Path) -> None:
    """Remove o arquivo de sessões do ADK (e os auxiliares do WAL), se existir."""
    arquivo = sessions_path(database)
    for sufixo in ("", "-wal", "-shm"):
        arquivo.with_name(arquivo.name + sufixo).unlink(missing_ok=True)


def restaurar(database: Path, dados: Path, sessoes: bool = False) -> None:
    """Volta o condomínio ao estado de dados/*.json. Não toca nas sessões ADK nem em dados/.

    - Reservas ativas da conversa são removidas e as do seed são recarregadas.
    - Reservas canceladas fora do seed ficam como histórico: o código nunca é reaproveitado.
    - Visitantes são recarregados do zero.
    Com `sessoes=True`, apaga também o arquivo de sessões do ADK.
    O schema é criado antes da transação, porque executescript fecha qualquer transação aberta.
    """
    apartamentos = _read_json(dados / "apartamentos.json")
    areas = _read_json(dados / "areas.json")
    reservas = _read_json(dados / "reservas.json")
    visitantes = _read_json(dados / "visitantes.json")

    database.parent.mkdir(parents=True, exist_ok=True)
    if sessoes:
        apagar_sessoes(database)
    connection = open_connection(database)
    try:
        create_schema(connection)
        with connection:
            connection.executemany(_UPSERT_AREA, [{**a, "taxa": str(a["taxa"])} for a in areas])
            connection.executemany(_UPSERT_APARTAMENTO, apartamentos)
            connection.execute("DELETE FROM reservas WHERE status = ?", (StatusReserva.ATIVA,))
            connection.executemany(
                _UPSERT_RESERVA, [{**r, "status": StatusReserva.ATIVA} for r in reservas]
            )
            connection.execute("DELETE FROM visitantes")
            connection.executemany(_INSERT_VISITANTE, visitantes)
    finally:
        connection.close()


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        content: list[dict[str, Any]] = json.load(file)
    return content


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aurora-restore",
        description="Restaura reservas e visitantes ao estado inicial de dados/.",
    )
    parser.add_argument("--dados", type=Path, default=DADOS_PADRAO, help="pasta com os JSON")
    parser.add_argument("--banco", type=Path, default=None, help="caminho do SQLite")
    parser.add_argument(
        "--sessoes", action="store_true", help="apaga também as sessões ADK antes de restaurar"
    )
    args = parser.parse_args()
    # Mesma fonte de configuração da API: sem isso, restore e API podem usar bancos diferentes.
    load_dotenv(override=False)
    database: Path = args.banco or database_path()
    restaurar(database, args.dados, sessoes=args.sessoes)
    print(f"Dados restaurados em {database}")


if __name__ == "__main__":
    main()
