"""Tool do agente de regulamento. Devolve capítulo, não o documento (Garantia 4)."""

from typing import Any

from google.adk.tools.function_tool import FunctionTool

from aurora.application.regulamento import ServicoRegulamento


def tools_de_regulamento(servico: ServicoRegulamento) -> list[FunctionTool]:
    def consultar_regulamento(topico: str) -> dict[str, Any]:
        """Busca no regulamento interno os capítulos que tratam de um assunto.

        Devolve no máximo dois capítulos. Quando nenhum capítulo casa com o tópico,
        devolve a lista de títulos em `titulos_disponiveis` para uma segunda tentativa.

        Args:
            topico: o assunto da dúvida, em poucas palavras (por exemplo "piscina",
                "animais de estimação", "garagem").
        """
        consulta = servico.consultar(topico)
        return {
            "capitulos": [
                {"titulo": capitulo.titulo, "texto": capitulo.texto}
                for capitulo in consulta.capitulos
            ],
            "titulos_disponiveis": consulta.titulos_disponiveis,
        }

    return [FunctionTool(consultar_regulamento)]
