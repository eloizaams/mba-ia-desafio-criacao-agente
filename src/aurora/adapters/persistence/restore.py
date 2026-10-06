import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from aurora.adapters.persistence.schema import criar_schema
from aurora.config import caminho_banco

DADOS_PADRAO = Path("dados")


def restaurar(banco: Path, dados: Path) -> None:
    """Recria o estado do condomínio a partir de dados/*.json, numa única transação.

    Apaga e recarrega as tabelas de domínio. Não toca nas sessões ADK e não altera dados/.
    """
    apartamentos = _ler_json(dados / "apartamentos.json")
    areas = _ler_json(dados / "areas.json")
    reservas = _ler_json(dados / "reservas.json")
    visitantes = _ler_json(dados / "visitantes.json")

    banco.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(banco)
    try:
        conexao.execute("PRAGMA foreign_keys = ON")
        with conexao:
            criar_schema(conexao)
            for tabela in ("reservas", "visitantes", "apartamentos", "areas"):
                conexao.execute(f"DELETE FROM {tabela}")
            conexao.executemany(
                "INSERT INTO areas (id, nome, taxa) VALUES (:id, :nome, :taxa)",
                [{**a, "taxa": str(a["taxa"])} for a in areas],
            )
            conexao.executemany(
                "INSERT INTO apartamentos (numero, morador) VALUES (:numero, :morador)",
                apartamentos,
            )
            conexao.executemany(
                "INSERT INTO reservas (codigo, apartamento, area, data, status) "
                "VALUES (:codigo, :apartamento, :area, :data, 'ativa')",
                reservas,
            )
            conexao.executemany(
                "INSERT INTO visitantes (apartamento, nome, data) "
                "VALUES (:apartamento, :nome, :data)",
                visitantes,
            )
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
