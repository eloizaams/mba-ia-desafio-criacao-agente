"""Erro de domínio vira resultado, nunca exceção.

É o que impede a Fase 5 de precisar traduzir 500 — e o que a Garantia 5 exige da
reserva que perde a disputa: "uma resposta normal".
"""

from typing import Any

import pytest

from aurora.adapters.adk.resultados import erro_como_resultado, traduz_erro_de_dominio
from aurora.domain.erros import (
    AreaDesconhecida,
    DadoInvalido,
    DataIndisponivel,
    DominioError,
    ReservaNaoEncontrada,
)


@pytest.mark.parametrize(
    ("erro", "status"),
    [
        (DataIndisponivel("quadra em 2030-04-06"), "data_indisponivel"),
        (ReservaNaoEncontrada("quadra em 2030-04-06"), "nao_encontrada"),
        (AreaDesconhecida("piscina-de-bolinhas"), "area_desconhecida"),
        (DadoInvalido("data precisa estar no formato AAAA-MM-DD"), "invalido"),
    ],
)
def test_cada_erro_de_dominio_tem_seu_status(erro: DominioError, status: str) -> None:
    resultado = erro_como_resultado(erro)

    assert resultado["status"] == status
    assert resultado["motivo"] == str(erro)


def test_erro_de_dominio_desconhecido_cai_em_invalido() -> None:
    class ErroNovo(DominioError):
        pass

    assert erro_como_resultado(ErroNovo("algo"))["status"] == "invalido"


def test_o_decorator_devolve_o_erro_em_vez_de_levantar() -> None:
    @traduz_erro_de_dominio
    def tool(area: str) -> dict[str, Any]:
        raise DataIndisponivel(area)

    assert tool("quadra") == {"status": "data_indisponivel", "motivo": "quadra"}


def test_o_decorator_nao_engole_erro_que_nao_e_de_dominio() -> None:
    """Defeito de programação tem de continuar aparecendo, não virar resultado para o modelo."""

    @traduz_erro_de_dominio
    def tool() -> dict[str, Any]:
        raise RuntimeError("defeito")

    with pytest.raises(RuntimeError):
        tool()


def test_o_decorator_preserva_assinatura_e_docstring() -> None:
    """É delas que o ADK monta a declaração da tool que o modelo enxerga."""

    @traduz_erro_de_dominio
    def reservar(area: str, data: str) -> dict[str, Any]:
        """Reserva uma área."""
        return {"status": "reservada"}

    import inspect

    assert reservar.__doc__ == "Reserva uma área."
    assert list(inspect.signature(reservar).parameters) == ["area", "data"]
