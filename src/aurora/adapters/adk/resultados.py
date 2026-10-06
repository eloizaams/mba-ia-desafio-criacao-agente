"""Erro de domínio vira resultado de tool, nunca exceção.

Se uma exceção subisse até o `Runner`, a Fase 5 teria de traduzir 500 — e a
Garantia 5 exige que a reserva perdida na disputa seja "uma resposta normal".
"""

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
