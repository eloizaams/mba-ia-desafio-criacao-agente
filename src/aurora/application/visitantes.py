"""Casos de uso de visitante. Autorizar libera acesso: quem chama exige confirmação."""

from dataclasses import dataclass

from aurora.application.ports import VisitanteRepository
from aurora.domain.datas import data_de_texto
from aurora.domain.visitante import Visitante


@dataclass(frozen=True)
class VisitantesService:
    visitantes: VisitanteRepository

    def meus_visitantes(self, apartamento: str) -> list[Visitante]:
        return self.visitantes.do_apartamento(apartamento)

    def autorizar(self, apartamento: str, nome: str, data: str) -> Visitante:
        """Regra de negócio 3. Data fora do formato e nome vazio são recusados antes de gravar."""
        return self.visitantes.autorizar(apartamento, nome, data_de_texto(data))
