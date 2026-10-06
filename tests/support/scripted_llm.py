"""LLM roteirizado: substitui o Gemini nos testes, sem chave de API.

Os testes provam a *mecânica* (confirmação, retomada, estado da sessão, isolamento
do regulamento) e as regras do código, não a inteligência do modelo. Um modelo
roteirizado torna isso determinístico e executável no CI sem `GOOGLE_API_KEY`.

Duas decisões que vêm da Fase 2 (`DESAFIOS.md`):

- A decisão de cada turno é **reativa**: olha o histórico que chega no
  `LlmRequest`, não um contador interno. Assim o roteiro continua correto depois
  de o processo reiniciar, quando o objeto do modelo nasce de novo e o histórico
  vem do banco.
- **Uma instância por agente.** Com uma instância compartilhada, o especialista
  também enxergava `transfer_to_agent` e tentava transferir para si mesmo.

O roteiro é declarado pelo teste, não deduzido do texto do morador: o papel diz o
que fazer (`transferir_para`, `chamar`, `argumentos`) e o modelo só decide *quando
parar* — ao ver a resposta da tool no histórico.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

# Nome da tool sintética que o ADK expõe ao modelo para trocar de agente.
TRANSFER_TOOL = "transfer_to_agent"
CONFIRMACAO = "adk_request_confirmation"


class ScriptedLlm(BaseLlm):
    """Modelo que decide o turno a partir do histórico, sem chamar a rede.

    Campos:
    - `transferir_para`: nome do sub-agente para onde delegar (papel de roteador);
    - `chamar`: nome da tool a chamar quando ela estiver disponível;
    - `argumentos`: argumentos dessa chamada;
    - `foco`: quando o resultado da tool chega, o modelo responde com a primeira
      frase do resultado que contém este termo. É o que faz o teste do regulamento
      provar que a resposta saiu do capítulo recuperado, e não do roteiro.
    """

    model: str = "scripted-llm"
    transferir_para: str | None = None
    chamar: str | None = None
    argumentos: dict[str, Any] = Field(default_factory=dict)
    foco: str = ""

    @property
    def capabilities(self) -> Any:
        from google.adk.models._capabilities import LlmCapabilities

        return LlmCapabilities(output_schema_and_tools=True)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        ultimo = _ultimo_turno(llm_request)
        ferramentas = _ferramentas_disponiveis(llm_request)

        # 1) Alguma tool já respondeu neste turno: fecha em texto. Sem esta porta de
        #    saída o roteiro reemite a mesma chamada para sempre e o ADK estoura o
        #    limite de 500 chamadas ao modelo (DESAFIOS.md).
        resposta = _resposta_de_tool(ultimo)
        if resposta is not None:
            yield _texto(self._responder(resposta))
            return

        # 2) Roteador: delega ao especialista.
        if self.transferir_para and TRANSFER_TOOL in ferramentas:
            yield _chamada(TRANSFER_TOOL, {"agent_name": self.transferir_para})
            return

        # 3) Quem tem a tool do roteiro, chama.
        if self.chamar and self.chamar in ferramentas:
            yield _chamada(self.chamar, dict(self.argumentos))
            return

        yield _texto(f"Nada a fazer com: {_texto_do_turno(ultimo)!r}")

    def _responder(self, resposta: types.FunctionResponse) -> str:
        bruto = json.dumps(resposta.response, ensure_ascii=False)
        if self.foco:
            frase = _frase_com(bruto, self.foco)
            if frase:
                return f"{resposta.name}: {frase}"
            return f"{resposta.name}: nada encontrado sobre {self.foco}."
        return f"{resposta.name}: {bruto}"


def _ultimo_turno(llm_request: LlmRequest) -> types.Content | None:
    contents = llm_request.contents or []
    return contents[-1] if contents else None


def _resposta_de_tool(content: types.Content | None) -> types.FunctionResponse | None:
    """A resposta de tool do turno, ignorando as sintéticas do próprio ADK."""
    if content is None:
        return None
    for part in content.parts or []:
        resposta = part.function_response
        if resposta is None or resposta.name in (TRANSFER_TOOL, CONFIRMACAO):
            continue
        return resposta
    return None


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


def _frase_com(texto: str, termo: str) -> str | None:
    for frase in texto.replace("\\n", " ").split(". "):
        if termo.lower() in frase.lower():
            return frase.strip()
    return None


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
