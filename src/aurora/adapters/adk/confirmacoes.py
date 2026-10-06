"""Confirmações pendentes derivadas dos eventos da sessão (Garantia 1).

Sem estado paralelo: um pedido é o function call `adk_request_confirmation` e deixa
de estar pendente quando existe um function response com o mesmo id. É isso que
sustenta o 409 da rota de confirmações — inclusive depois de reiniciar a API, porque
os eventos vêm do banco.

Padrão comprovado na Fase 2: `docs/ADK-CONFIRMACAO.md`.
"""

from dataclasses import dataclass, field
from typing import Any

from google.adk.events.event import Event
from google.genai import types

CONFIRMACAO = "adk_request_confirmation"

# Texto de `acao` na resposta da API. O `hint` do ADK é um texto genérico em inglês e
# não é configurável pela via nativa de `require_confirmation`, então a frase em
# português é montada aqui, a partir do nome da tool.
ACAO_POR_TOOL = {
    "reservar": "Reservar área comum (gera cobrança)",
    "autorizar_visitante": "Autorizar entrada de visitante",
}


@dataclass(frozen=True)
class PendenciaConfirmacao:
    """Um pedido de confirmação ainda sem resposta.

    `detalhes` são os argumentos originais da tool. Como nenhuma tool recebe
    apartamento, não há o que filtrar: ali só existe o que o morador pediu.
    """

    id: str
    acao: str
    detalhes: dict[str, Any] = field(default_factory=dict)
    tool: str = ""


def pendentes(eventos: list[Event]) -> list[PendenciaConfirmacao]:
    """Pedidos sem resposta, na ordem em que apareceram na sessão."""
    pedidos: dict[str, PendenciaConfirmacao] = {}
    respondidos: set[str] = set()
    for evento in eventos:
        for chamada in evento.get_function_calls():
            if chamada.name == CONFIRMACAO and chamada.id:
                pedidos[chamada.id] = _pendencia(chamada.id, chamada.args or {})
        for resposta in evento.get_function_responses():
            if resposta.name == CONFIRMACAO and resposta.id:
                respondidos.add(resposta.id)
    return [pedido for id_, pedido in pedidos.items() if id_ not in respondidos]


def resposta_de_confirmacao(id_da_pendencia: str, confirmado: bool) -> types.Content:
    """A mensagem que retoma a execução.

    Autor `user` e um `FunctionResponse` com o id do pedido: o `Runner` deduz a
    invocação casando esse id contra os eventos da sessão, então não é preciso
    informar `invocation_id` e a retomada sobrevive ao reinício.
    """
    return types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=id_da_pendencia,
                    name=CONFIRMACAO,
                    response={"confirmed": confirmado},
                )
            )
        ],
    )


def _pendencia(id_: str, args: dict[str, Any]) -> PendenciaConfirmacao:
    original = args.get("originalFunctionCall") or {}
    tool = str(original.get("name") or "")
    detalhes = original.get("args")
    return PendenciaConfirmacao(
        id=id_,
        acao=ACAO_POR_TOOL.get(tool, f"Executar {tool}" if tool else "Confirmar ação"),
        detalhes=dict(detalhes) if isinstance(detalhes, dict) else {},
        tool=tool,
    )
