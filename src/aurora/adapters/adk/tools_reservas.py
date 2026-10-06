"""Tools do especialista de reservas.

Nenhuma recebe apartamento: ele vem de `tool_context.state` (Garantia 2). As
tools são finas — estado, caso de uso, dicionário — e não decidem regra nenhuma.
Erro de domínio vira resultado pelo decorator, nunca exceção para o `Runner`.
"""

from typing import Any

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

from aurora.adapters.adk.estado import apartamento_da_sessao
from aurora.adapters.adk.resultados import traduz_erro_de_dominio
from aurora.application.reservas import ReservasService


def tools_de_reservas(servico: ReservasService) -> list[FunctionTool]:
    """Monta as tools em cima de um serviço já ligado ao banco."""

    def listar_areas() -> dict[str, Any]:
        """Lista as áreas comuns do condomínio, com o id de cada uma e se gera cobrança.

        Use para descobrir o id da área antes de qualquer outra tool de reserva.
        """
        return {
            "areas": [
                {
                    "id": area.id,
                    "nome": area.nome,
                    "taxa": str(area.taxa),
                    "gera_cobranca": area.gera_cobranca,
                }
                for area in servico.listar_areas()
            ]
        }

    def listar_minhas_reservas(tool_context: ToolContext) -> dict[str, Any]:
        """Lista as reservas ativas do apartamento desta sessão."""
        reservas = servico.minhas_reservas(apartamento_da_sessao(tool_context))
        return {
            "reservas": [
                {"codigo": r.codigo, "area": r.area, "data": r.data.isoformat()} for r in reservas
            ]
        }

    @traduz_erro_de_dominio
    def verificar_disponibilidade(area: str, data: str) -> dict[str, Any]:
        """Diz se uma área está livre ou ocupada numa data.

        Nunca informa de quem é a reserva: a agenda de outro morador não entra na conversa.

        Args:
            area: id da área, como em listar_areas.
            data: data no formato AAAA-MM-DD.
        """
        livre = servico.disponivel(area, data)
        return {
            "status": "ok",
            "area": area,
            "data": data,
            "situacao": "livre" if livre else "ocupada",
        }

    @traduz_erro_de_dominio
    def reservar(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Reserva uma área comum para o apartamento desta sessão.

        Área com taxa maior que zero gera cobrança e exige confirmação do morador.

        Args:
            area: id da área, como em listar_areas.
            data: data no formato AAAA-MM-DD.
        """
        feita = servico.reservar(apartamento_da_sessao(tool_context), area, data)
        return {
            "status": "reservada",
            "codigo": feita.reserva.codigo,
            "area": feita.reserva.area,
            "data": feita.reserva.data.isoformat(),
            "gera_cobranca": feita.gera_cobranca,
        }

    @traduz_erro_de_dominio
    def cancelar_minha_reserva(area: str, data: str, tool_context: ToolContext) -> dict[str, Any]:
        """Cancela uma reserva do apartamento desta sessão, pela área e pela data.

        Reserva de outro apartamento não é encontrada por esta tool.

        Args:
            area: id da área, como em listar_areas.
            data: data no formato AAAA-MM-DD.
        """
        reserva = servico.cancelar(apartamento_da_sessao(tool_context), area, data)
        return {
            "status": "cancelada",
            "codigo": reserva.codigo,
            "area": reserva.area,
            "data": reserva.data.isoformat(),
        }

    def _reserva_gera_cobranca(area: str, data: str, tool_context: ToolContext) -> bool:
        """Garantia 1: só a taxa da área decide se a reserva precisa de confirmação.

        O ADK invoca este callable com os mesmos argumentos de `reservar`, então a
        assinatura precisa acompanhar a da tool.
        """
        return servico.gera_cobranca(area)

    return [
        FunctionTool(listar_areas),
        FunctionTool(listar_minhas_reservas),
        FunctionTool(verificar_disponibilidade),
        FunctionTool(reservar, require_confirmation=_reserva_gera_cobranca),
        FunctionTool(cancelar_minha_reserva),
    ]
