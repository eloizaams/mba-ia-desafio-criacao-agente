"""Passo 15: o contrato das tools, verificado na estrutura e não na leitura.

As tools saem da topologia de verdade (`construir_raiz`), caminhando pelo root, pelos
`sub_agents` e pelo agente embrulhado em `AgentTool`. Montar a lista pelas fábricas
deixaria passar uma tool pendurada direto num agente.
"""

import inspect
from pathlib import Path

import pytest
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.function_tool import FunctionTool

from aurora.adapters.adk.agentes import construir_raiz
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.adapters.regulamento import RegulamentoArquivo
from aurora.application.regulamento import RegulamentoService
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService

PALAVRAS_PROIBIDAS = ("apartamento", "apto", "unidade", "morador")
TOOLS_QUE_CONFIRMAM = {"reservar", "autorizar_visitante"}
TOOLS_ESPERADAS = {
    "listar_areas",
    "listar_minhas_reservas",
    "verificar_disponibilidade",
    "reservar",
    "cancelar_minha_reserva",
    "listar_meus_visitantes",
    "autorizar_visitante",
    "consultar_regulamento",
}


def _tools_do_agente(agente: LlmAgent) -> list[FunctionTool]:
    """Todas as FunctionTool alcançáveis a partir deste agente, inclusive via AgentTool."""
    encontradas: list[FunctionTool] = []
    for tool in agente.tools:
        if isinstance(tool, FunctionTool):
            encontradas.append(tool)
        elif isinstance(tool, AgentTool) and isinstance(tool.agent, LlmAgent):
            encontradas.extend(_tools_do_agente(tool.agent))
    for sub_agente in agente.sub_agents:
        if isinstance(sub_agente, LlmAgent):
            encontradas.extend(_tools_do_agente(sub_agente))
    return encontradas


@pytest.fixture
def tools() -> list[FunctionTool]:
    """A topologia de verdade. Nenhuma tool é chamada aqui, então o banco nem precisa existir."""
    repositorio = SqliteRepository(Path("nao-abre.db"))
    raiz = construir_raiz(
        reservas=ReservasService(agenda=repositorio, areas=repositorio),
        visitantes=VisitantesService(visitantes=repositorio),
        regulamento=RegulamentoService(fonte=RegulamentoArquivo(Path("nao-abre.md"))),
        modelo=lambda _: "modelo-de-teste",
    )
    return _tools_do_agente(raiz)


def test_a_topologia_expoe_exatamente_as_tools_da_spec(tools: list[FunctionTool]) -> None:
    """Tool nova que não passe por aqui não seria vista pelos dois testes abaixo."""
    assert {tool.name for tool in tools} == TOOLS_ESPERADAS


def test_nenhuma_tool_aceita_apartamento(tools: list[FunctionTool]) -> None:
    """Garantia 2: o apartamento vem do state, e não existe caminho alternativo."""
    for tool in tools:
        parametros = set(inspect.signature(tool.func).parameters)
        assert not parametros & set(PALAVRAS_PROIBIDAS), tool.name
        for parametro in parametros:
            assert not any(proibida in parametro for proibida in PALAVRAS_PROIBIDAS), tool.name


def test_so_cobranca_e_acesso_exigem_confirmacao(tools: list[FunctionTool]) -> None:
    """Garantia 1: nem mais (cancelar não confirma), nem menos.

    Lê um atributo privado do ADK porque não há superfície pública que diga se uma tool
    exige confirmação. Vale enquanto a versão estiver fixada em 2.11.0: se o pin subir,
    este teste é um dos lugares a conferir antes de qualquer outra coisa.
    """
    com_confirmacao = {tool.name for tool in tools if tool._require_confirmation is not False}

    assert com_confirmacao == TOOLS_QUE_CONFIRMAM


def test_toda_tool_tem_descricao_para_o_modelo(tools: list[FunctionTool]) -> None:
    """O decorator que traduz erro de domínio não pode comer a docstring que o ADK declara."""
    for tool in tools:
        assert tool.description, tool.name
