"""Passo 15: o contrato das tools, verificado na estrutura e não na leitura.

Nenhuma tool aceita apartamento, e só as duas ações que geram cobrança ou liberam
acesso exigem confirmação. Se alguém acrescentar um parâmetro ou esquecer uma
confirmação, estes testes caem.
"""

import inspect
from pathlib import Path

import pytest
from google.adk.tools.function_tool import FunctionTool

from aurora.adapters.adk.tools_regulamento import tools_de_regulamento
from aurora.adapters.adk.tools_reservas import tools_de_reservas
from aurora.adapters.adk.tools_visitantes import tools_de_visitantes
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.adapters.regulamento import RegulamentoArquivo
from aurora.application.regulamento import ServicoRegulamento
from aurora.application.reservas import ServicoReservas
from aurora.application.visitantes import ServicoVisitantes

PALAVRAS_PROIBIDAS = ("apartamento", "apto", "unidade", "morador")
TOOLS_QUE_CONFIRMAM = {"reservar", "autorizar_visitante"}


@pytest.fixture
def tools() -> list[FunctionTool]:
    """As tools de verdade. Nenhuma é chamada aqui, então o banco nem precisa existir."""
    repositorio = SqliteRepository(Path("nao-abre.db"))
    return [
        *tools_de_reservas(ServicoReservas(agenda=repositorio, areas=repositorio)),
        *tools_de_visitantes(ServicoVisitantes(visitantes=repositorio)),
        *tools_de_regulamento(ServicoRegulamento(fonte=RegulamentoArquivo(Path("nao-abre.md")))),
    ]


def test_nenhuma_tool_aceita_apartamento(tools: list[FunctionTool]) -> None:
    """Garantia 2: o apartamento vem do state, e não existe caminho alternativo."""
    for tool in tools:
        parametros = set(inspect.signature(tool.func).parameters)
        assert not parametros & set(PALAVRAS_PROIBIDAS), tool.name
        for parametro in parametros:
            assert not any(proibida in parametro for proibida in PALAVRAS_PROIBIDAS), tool.name


def test_so_cobranca_e_acesso_exigem_confirmacao(tools: list[FunctionTool]) -> None:
    """Garantia 1: nem mais (cancelar não confirma), nem menos."""
    com_confirmacao = {tool.name for tool in tools if tool._require_confirmation is not False}

    assert com_confirmacao == TOOLS_QUE_CONFIRMAM


def test_toda_tool_tem_descricao_para_o_modelo(tools: list[FunctionTool]) -> None:
    for tool in tools:
        assert tool.description, tool.name
