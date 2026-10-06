"""Spike da Fase 2: confirmação nativa do ADK + retomada após reiniciar o processo.

Código descartável. Serve para responder, com evidência executável:

1. Uma tool com `require_confirmation` dentro de um `sub_agent` gera o pedido
   `adk_request_confirmation`?
2. A retomada por `FunctionResponse` funciona — aprovar executa uma vez, negar
   não executa?
3. Itens 1 e 2 continuam valendo **em outro processo** (sessão vinda do SQLite)?
4. Qual configuração faz a resposta voltar para o agente que pediu?
5. Os eventos internos de um `AgentTool` entram na sessão do pai?

Cada subcomando é um processo separado de propósito: é assim que o passo 13 do
avaliador (reiniciar a aplicação) é reproduzido de verdade.

Uso:
    uv run python spike/spike_confirmacao.py abrir
    uv run python spike/spike_confirmacao.py confirmar <sessao> --aprovar
    uv run python spike/spike_confirmacao.py confirmar <sessao> --negar
    uv run python spike/spike_confirmacao.py eventos <sessao>
    uv run python spike/spike_confirmacao.py agent-tool
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps._configs import ResumabilityConfig
from google.adk.apps.app import App
from google.adk.runners import Runner
from google.adk.sessions.session import Session
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from scripted_llm import ScriptedLlm

RAIZ = Path(__file__).resolve().parent
DB = RAIZ / "spike_sessoes.db"
EXECUCOES = RAIZ / "spike_execucoes.log"

APP = "spike-aurora"
USUARIO = "ap-302"
CHAVE_APARTAMENTO = "apartamento"
CONFIRMACAO = "adk_request_confirmation"


# ---------------------------------------------------------------- tools


def reservar(area: str, data: str, tool_context: ToolContext) -> dict[str, str]:
    """Reserva uma área comum para o apartamento da sessão.

    Args:
        area: nome da área comum.
        data: data no formato AAAA-MM-DD.
    """
    # Garantia 2: o apartamento vem da sessão, nunca de argumento do modelo.
    apartamento = tool_context.state.get(CHAVE_APARTAMENTO)
    registro = {"apartamento": apartamento, "area": area, "data": data}
    with EXECUCOES.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return {"status": "reservada", "codigo": "RES-SPIKE-1", **registro}


def consultar_regulamento(topico: str) -> dict[str, str]:
    """Devolve o capítulo do regulamento sobre o tópico.

    Args:
        topico: assunto procurado.
    """
    return {"topico": topico, "capitulo": f"Capítulo fictício sobre {topico}."}


# ---------------------------------------------------------------- app


def construir_app(*, resumable: bool) -> App:
    """Root roteador + sub_agent especialista com a tool que exige confirmação."""
    reservas = LlmAgent(
        name="reservas",
        model=ScriptedLlm(transferir=False),
        instruction="Especialista em reservas de áreas comuns.",
        tools=[FunctionTool(reservar, require_confirmation=True)],
    )
    raiz = LlmAgent(
        name="aurora",
        model=ScriptedLlm(),
        instruction="Roteia o morador para o especialista certo.",
        sub_agents=[reservas],
    )
    return App(
        name=APP,
        root_agent=raiz,
        resumability_config=ResumabilityConfig(is_resumable=resumable),
    )


def construir_runner(*, resumable: bool = True) -> Runner:
    return Runner(
        app=construir_app(resumable=resumable), session_service=SqliteSessionService(str(DB))
    )


# ---------------------------------------------------------------- leitura de eventos


def confirmacoes_pendentes(sessao: Session) -> list[dict[str, Any]]:
    """Pedidos de confirmação sem resposta — a mesma derivação que a API fará.

    Um pedido é um function call `adk_request_confirmation`; ele deixa de estar
    pendente quando existe um function response com o mesmo id.
    """
    pedidos: dict[str, dict[str, Any]] = {}
    respondidos: set[str] = set()
    for evento in sessao.events:
        for chamada in evento.get_function_calls():
            if chamada.name == CONFIRMACAO and chamada.id:
                original = (chamada.args or {}).get("originalFunctionCall") or {}
                pedidos[chamada.id] = {
                    "id": chamada.id,
                    "autor": evento.author,
                    "tool": original.get("name"),
                    "argumentos": original.get("args"),
                    "dica": (chamada.args or {}).get("hint"),
                }
        for resposta in evento.get_function_responses():
            if resposta.name == CONFIRMACAO and resposta.id:
                respondidos.add(resposta.id)
    return [p for id_, p in pedidos.items() if id_ not in respondidos]


def resumir(sessao: Session) -> None:
    print(f"\n--- eventos da sessão {sessao.id} ({len(sessao.events)}) ---")
    for evento in sessao.events:
        partes: list[str] = []
        for chamada in evento.get_function_calls():
            partes.append(f"call {chamada.name}({chamada.args}) id={chamada.id}")
        for resposta in evento.get_function_responses():
            partes.append(f"resp {resposta.name} -> {resposta.response} id={resposta.id}")
        texto = "".join(
            p.text or "" for p in (evento.content.parts if evento.content else []) or []
        )
        if texto.strip():
            partes.append(f"texto {texto.strip()!r}")
        detalhe = "; ".join(partes) or "(vazio)"
        cabecalho = f"[{evento.author:<9}] branch={evento.branch} inv={evento.invocation_id}"
        print(f"  {cabecalho} :: {detalhe}")


def contar_execucoes() -> int:
    if not EXECUCOES.exists():
        return 0
    return sum(1 for linha in EXECUCOES.read_text(encoding="utf-8").splitlines() if linha.strip())


# ---------------------------------------------------------------- subcomandos


async def cmd_abrir() -> None:
    EXECUCOES.unlink(missing_ok=True)
    runner = construir_runner()
    sessao = await runner.session_service.create_session(
        app_name=APP, user_id=USUARIO, state={CHAVE_APARTAMENTO: "302"}
    )
    mensagem = types.Content(role="user", parts=[types.Part(text="quero reservar a churrasqueira")])
    async for _ in runner.run_async(user_id=USUARIO, session_id=sessao.id, new_message=mensagem):
        pass

    sessao = await _recarregar(runner, sessao.id)
    resumir(sessao)
    pendentes = confirmacoes_pendentes(sessao)
    print(f"\nexecuções da tool até aqui: {contar_execucoes()} (esperado 0)")
    print(f"confirmações pendentes: {json.dumps(pendentes, ensure_ascii=False, indent=2)}")
    print(f"\nsessão: {sessao.id}")


async def cmd_confirmar(sessao_id: str, aprovar: bool) -> None:
    """Retoma num processo novo: nada em memória sobrevive, só o SQLite."""
    runner = construir_runner()
    sessao = await _recarregar(runner, sessao_id)
    pendentes = confirmacoes_pendentes(sessao)
    if not pendentes:
        print("nenhuma confirmação pendente — a API devolveria 409")
        return
    pendente = pendentes[0]
    antes = contar_execucoes()

    resposta = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=pendente["id"],
                    name=CONFIRMACAO,
                    response={"confirmed": aprovar},
                )
            )
        ],
    )
    async for _ in runner.run_async(user_id=USUARIO, session_id=sessao_id, new_message=resposta):
        pass

    sessao = await _recarregar(runner, sessao_id)
    resumir(sessao)
    depois = contar_execucoes()
    esperado = antes + 1 if aprovar else antes
    print(f"\nexecuções da tool: {antes} -> {depois} (esperado {esperado})")
    print(f"pendentes agora: {confirmacoes_pendentes(sessao)}")


async def cmd_eventos(sessao_id: str) -> None:
    runner = construir_runner()
    resumir(await _recarregar(runner, sessao_id))


async def cmd_agent_tool() -> None:
    """Garantia 4: os eventos de um AgentTool aparecem na sessão do pai?"""
    regulamento = LlmAgent(
        name="regulamento",
        model=ScriptedLlm(transferir=False),
        instruction="Responde só com base no regulamento.",
        tools=[FunctionTool(consultar_regulamento)],
    )
    raiz = LlmAgent(
        name="aurora",
        model=ScriptedLlm(transferir=False),
        instruction="Roteador.",
        tools=[AgentTool(agent=regulamento)],
    )
    app = App(
        name=APP + "-at", root_agent=raiz, resumability_config=ResumabilityConfig(is_resumable=True)
    )
    runner = Runner(app=app, session_service=SqliteSessionService(str(DB)))
    sessao = await runner.session_service.create_session(app_name=app.name, user_id=USUARIO)
    mensagem = types.Content(
        role="user", parts=[types.Part(text="o que diz o regulamento sobre barulho?")]
    )
    async for _ in runner.run_async(user_id=USUARIO, session_id=sessao.id, new_message=mensagem):
        pass
    sessao = await runner.session_service.get_session(
        app_name=app.name, user_id=USUARIO, session_id=sessao.id
    )
    assert sessao is not None
    resumir(sessao)
    autores = {evento.author for evento in sessao.events}
    print(f"\nautores na sessão do pai: {sorted(autores)}")
    isolado = "regulamento" not in autores
    print(f"contexto isolado (regulamento não é autor na sessão do pai)? {isolado}")


async def _recarregar(runner: Runner, sessao_id: str) -> Session:
    sessao = await runner.session_service.get_session(
        app_name=APP, user_id=USUARIO, session_id=sessao_id
    )
    if sessao is None:
        raise SystemExit(f"sessão {sessao_id} não encontrada em {DB}")
    return sessao


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("abrir")
    confirmar = sub.add_parser("confirmar")
    confirmar.add_argument("sessao")
    grupo = confirmar.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--aprovar", action="store_true")
    grupo.add_argument("--negar", action="store_true")
    eventos = sub.add_parser("eventos")
    eventos.add_argument("sessao")
    sub.add_parser("agent-tool")

    args = parser.parse_args()
    if args.comando == "abrir":
        asyncio.run(cmd_abrir())
    elif args.comando == "confirmar":
        asyncio.run(cmd_confirmar(args.sessao, aprovar=args.aprovar))
    elif args.comando == "eventos":
        asyncio.run(cmd_eventos(args.sessao))
    elif args.comando == "agent-tool":
        asyncio.run(cmd_agent_tool())


if __name__ == "__main__":
    main()
