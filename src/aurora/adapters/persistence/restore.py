import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from aurora.adapters.persistence.schema import criar_schema
from aurora.config import caminho_banco

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
    "VALUES (:codigo, :apartamento, :area, :data, 'ativa') "
    "ON CONFLICT(codigo) DO UPDATE SET apartamento = excluded.apartamento, "
    "area = excluded.area, data = excluded.data, status = 'ativa'"
)
_INSERT_VISITANTE = (
    "INSERT INTO visitantes (apartamento, nome, data) VALUES (:apartamento, :nome, :data)"
)


def restaurar(banco: Path, dados: Path) -> None:
    """Volta o condomínio ao estado de dados/*.json. Não toca nas sessões ADK nem em dados/.

    - Reservas ativas da conversa são removidas e as do seed são recarregadas.
    - Reservas canceladas fora do seed ficam como histórico: o código nunca é reaproveitado.
    - Visitantes são recarregados do zero.
    O schema é criado antes da transação, porque executescript fecha qualquer transação aberta.
    """
    apartamentos = _ler_json(dados / "apartamentos.json")
    areas = _ler_json(dados / "areas.json")
    reservas = _ler_json(dados / "reservas.json")
    visitantes = _ler_json(dados / "visitantes.json")

    banco.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(banco)
    try:
        conexao.execute("PRAGMA foreign_keys = ON")
        criar_schema(conexao)
        with conexao:
            conexao.executemany(_UPSERT_AREA, [{**a, "taxa": str(a["taxa"])} for a in areas])
            conexao.executemany(_UPSERT_APARTAMENTO, apartamentos)
            conexao.execute("DELETE FROM reservas WHERE status = 'ativa'")
            conexao.executemany(_UPSERT_RESERVA, reservas)
            conexao.execute("DELETE FROM visitantes")
            conexao.executemany(_INSERT_VISITANTE, visitantes)
        conexao.execute("PRAGMA journal_mode = WAL")
    finally:
        conexao.close()


def _ler_json(caminho: Path) -> list[dict[str, Any]]:
    with caminho.open(encoding="utf-8") as arquivo:
        conteudo: list[dict[str, Any]] = json.load(arquivo)
    return conteudo


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aurora-restore",
        description="Restaura reservas e visitantes ao estado inicial de dados/.",
    )
    parser.add_argument("--dados", type=Path, default=DADOS_PADRAO, help="pasta com os JSON")
    parser.add_argument("--banco", type=Path, default=None, help="caminho do SQLite")
    args = parser.parse_args()
    banco: Path = args.banco or caminho_banco()
    restaurar(banco, args.dados)
    print(f"Dados restaurados em {banco}")


if __name__ == "__main__":
    main()
