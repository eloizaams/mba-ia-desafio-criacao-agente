import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from aurora.domain.area import Area
from aurora.domain.codigo import gerar_codigo_reserva
from aurora.domain.reserva import Reserva, StatusReserva

DOMINIO = Path(__file__).parents[2] / "src" / "aurora" / "domain"


@pytest.mark.parametrize(
    ("taxa", "cobra"),
    [(Decimal("150.0"), True), (Decimal("0.01"), True), (Decimal("0"), False)],
)
def test_area_so_cobra_com_taxa_maior_que_zero(taxa: Decimal, cobra: bool) -> None:
    area = Area(id="x", nome="X", taxa=taxa)

    assert area.gera_cobranca is cobra


def test_codigo_de_reserva_tem_formato_rsv_e_muda_entre_chamadas() -> None:
    codigos = {gerar_codigo_reserva() for _ in range(50)}

    assert len(codigos) == 50
    assert all(re.fullmatch(r"RSV-[0-9A-F]{6}", c) for c in codigos)


def test_reserva_nasce_ativa_por_padrao() -> None:
    reserva = Reserva(codigo="RSV-1", apartamento="101", area="quadra", data=date(2030, 4, 6))

    assert reserva.status is StatusReserva.ATIVA


def test_dominio_nao_importa_adk_fastapi_nem_sqlite() -> None:
    proibidos = ("google", "fastapi", "sqlite3", "aiosqlite", "aurora.adapters")
    for arquivo in DOMINIO.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes: list[str] = []
            if isinstance(no, ast.Import):
                nomes = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes = [no.module]
            for nome in nomes:
                assert not nome.startswith(proibidos), f"{arquivo.name} importa {nome}"
