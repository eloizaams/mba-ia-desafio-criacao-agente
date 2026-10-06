"""LLM roteirizado: substitui o Gemini no spike, sem chave de API.

O spike precisa provar a *mecânica* do ADK (confirmação, retomada, persistência),
não a inteligência do modelo. Um modelo roteirizado torna isso determinístico e
executável no CI sem `GOOGLE_API_KEY`.

A decisão de cada turno é **reativa** (olha o último conteúdo da conversa), não
baseada num contador interno: assim o roteiro continua correto depois de o
processo reiniciar, quando o objeto do modelo nasce de novo e o histórico vem
do banco.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

# Nome da tool sintética que o ADK expõe ao modelo para trocar de agente.
TRANSFER_TOOL = "transfer_to_agent"


def _ultimo_turno(llm_request: LlmRequest) -> types.Content | None:
    contents = llm_request.contents or []
    return contents[-1] if contents else None


def _tem_resposta_de(content: types.Content | None, nome_tool: str) -> bool:
    if content is None:
        return False
    for part in content.parts or []:
        fr = part.function_response
        if fr is not None and fr.name == nome_tool:
            return True
    return False


def _texto_do_turno(content: types.Content | None) -> str:
    if content is None:
        return ""
    return " ".join(part.text or "" for part in content.parts or []).lower()


def _ferramentas_disponiveis(llm_request: LlmRequest) -> set[str]:
    nomes: set[str] = set()
    for tool in llm_request.config.tools or []:
        for declaracao in getattr(tool, "function_declarations", None) or []:
            if declaracao.name:
                nomes.add(declaracao.name)
    return nomes


class ScriptedLlm(BaseLlm):
    """Modelo que decide o turno a partir do histórico, sem chamar a rede.

    Roteiro (uma instância por agente, para que cada um tenha seu papel):
    - `transferir=True` (roteador): delega para `destino_transferencia`;
    - `transferir=False` (especialista): chama `reservar(area, data)`;
    - se o último turno traz a resposta de `reservar`, responde em texto.
    """

    model: str = "scripted-llm"
    transferir: bool = True
    destino_transferencia: str = "reservas"
    area: str = "churrasqueira"
    data: str = "2026-10-20"

    @property
    def capabilities(self) -> Any:
        from google.adk.models._capabilities import LlmCapabilities

        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        ultimo = _ultimo_turno(llm_request)
        ferramentas = _ferramentas_disponiveis(llm_request)

        # 1) Alguma tool de negócio já respondeu neste turno: fecha em texto.
        #    Sem esta porta de saída o roteiro reemite a mesma chamada para
        #    sempre e o ADK estoura o limite de 500 chamadas ao modelo.
        for nome in ("reservar", "regulamento", "consultar_regulamento"):
            if _tem_resposta_de(ultimo, nome):
                yield _texto(f"Pedido tratado por {nome}.")
                return

        # 2) Agente roteador: delega ao especialista.
        if self.transferir and TRANSFER_TOOL in ferramentas:
            yield _chamada(TRANSFER_TOOL, {"agent_name": self.destino_transferencia})
            return

        # 3) Especialista: pede a reserva.
        if "reservar" in ferramentas:
            yield _chamada("reservar", {"area": self.area, "data": self.data})
            return

        # 4) Root do teste de AgentTool: delega ao agente embrulhado como tool.
        if "regulamento" in ferramentas:
            yield _chamada("regulamento", {"request": "barulho"})
            return

        if "consultar_regulamento" in ferramentas:
            yield _chamada("consultar_regulamento", {"topico": "barulho"})
            return

        yield _texto(f"Não sei o que fazer com: {_texto_do_turno(ultimo)!r}")


def _texto(texto: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=texto)]),
        partial=False,
    )


def _chamada(nome: str, args: dict[str, Any]) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(function_call=types.FunctionCall(name=nome, args=args))],
        ),
        partial=False,
    )
