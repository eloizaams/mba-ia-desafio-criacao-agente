"""Erro de domínio vira resultado de tool, nunca exceção.

Se uma exceção subisse até o `Runner`, a Fase 5 teria de traduzir 500 — e a
Garantia 5 exige que a reserva perdida na disputa seja "uma resposta normal".
"""

import functools
from collections.abc import Callable
from typing import Any

from aurora.domain.erros import (
    AreaDesconhecida,
    DadoInvalido,
    DataIndisponivel,
    DominioError,
    ReservaNaoEncontrada,
)

_STATUS_POR_ERRO: dict[type[DominioError], str] = {
    DataIndisponivel: "data_indisponivel",
    ReservaNaoEncontrada: "nao_encontrada",
    AreaDesconhecida: "area_desconhecida",
    DadoInvalido: "invalido",
}


def erro_como_resultado(erro: DominioError) -> dict[str, Any]:
    status = _STATUS_POR_ERRO.get(type(erro), "invalido")
    return {"status": status, "motivo": str(erro)}


def traduz_erro_de_dominio[**Argumentos](
    tool: Callable[Argumentos, dict[str, Any]],
) -> Callable[Argumentos, dict[str, Any]]:
    """Faz a tool devolver o erro de domínio em vez de levantá-lo.

    `functools.wraps` preserva assinatura e docstring, que é o que o ADK lê para montar
    a declaração da tool — conferido em `test_tools_contrato.py`, que inspeciona as
    tools de verdade.
    """

    @functools.wraps(tool)
    def com_erro_traduzido(*args: Argumentos.args, **kwargs: Argumentos.kwargs) -> dict[str, Any]:
        try:
            return tool(*args, **kwargs)
        except DominioError as erro:
            return erro_como_resultado(erro)

    return com_erro_traduzido
