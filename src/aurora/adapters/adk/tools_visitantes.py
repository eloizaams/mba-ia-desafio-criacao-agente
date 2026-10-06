"""Tools do especialista de visitantes. Autorizar libera acesso: confirma sempre."""

from typing import Any

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from aurora.adapters.adk.estado import apartamento_da_sessao
from aurora.adapters.adk.resultados import traduz_erro_de_dominio
from aurora.application.visitantes import VisitantesService


def tools_de_visitantes(servico: VisitantesService) -> list[FunctionTool]:
    def listar_meus_visitantes(tool_context: ToolContext) -> dict[str, Any]:
        """Lista os visitantes autorizados pelo apartamento desta sessão."""
        visitantes = servico.meus_visitantes(apartamento_da_sessao(tool_context))
        return {"visitantes": [{"nome": v.nome, "data": v.data.isoformat()} for v in visitantes]}

    @traduz_erro_de_dominio
    def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Autoriza a entrada de um visitante no apartamento desta sessão.

        Libera acesso ao prédio, então exige sempre a confirmação do morador.

        Args:
            nome: nome completo do visitante.
            data: data da visita, no formato AAAA-MM-DD.
        """
        visitante = servico.autorizar(apartamento_da_sessao(tool_context), nome, data)
        return {
            "status": "autorizado",
            "nome": visitante.nome,
            "data": visitante.data.isoformat(),
        }

    return [
        FunctionTool(listar_meus_visitantes),
        # Garantia 1: liberar acesso nunca depende do que o morador escreve na conversa.
        FunctionTool(autorizar_visitante, require_confirmation=True),
    ]
