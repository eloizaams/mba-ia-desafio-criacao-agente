"""Consulta ao regulamento: devolve capítulo, não documento (Garantia 4)."""

from dataclasses import dataclass

from aurora.application.ports import RegulamentoRepository
from aurora.domain.regulamento import Capitulo, capitulos_relevantes


@dataclass(frozen=True)
class ConsultaRegulamento:
    """Capítulos pertinentes ao tópico. Vazio vem com os títulos, para uma nova tentativa."""

    capitulos: list[Capitulo]
    titulos_disponiveis: list[str]


@dataclass(frozen=True)
class RegulamentoService:
    fonte: RegulamentoRepository

    def consultar(self, topico: str) -> ConsultaRegulamento:
        capitulos = self.fonte.capitulos()
        pertinentes = capitulos_relevantes(capitulos, topico)
        if pertinentes:
            return ConsultaRegulamento(capitulos=pertinentes, titulos_disponiveis=[])
        return ConsultaRegulamento(
            capitulos=[], titulos_disponiveis=[capitulo.titulo for capitulo in capitulos]
        )
