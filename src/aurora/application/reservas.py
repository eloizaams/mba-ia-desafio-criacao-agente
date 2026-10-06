"""Casos de uso de reserva. O apartamento é sempre parâmetro, nunca escolha do serviço.

Quem chama (a tool) tira o apartamento da sessão. Aqui a regra é: validar antes de
gravar (área inexistente viraria IntegrityError de FK, não resultado de domínio) e
nunca deixar o chamador saber de reserva de outro apartamento.
"""

from dataclasses import dataclass

from aurora.application.portas import AgendaRepository, AreaRepository
from aurora.domain.area import Area
from aurora.domain.datas import data_de_texto
from aurora.domain.erros import AreaDesconhecida, ReservaNaoEncontrada
from aurora.domain.reserva import Reserva


@dataclass(frozen=True)
class ServicoReservas:
    agenda: AgendaRepository
    areas: AreaRepository

    def listar_areas(self) -> list[Area]:
        return self.areas.listar()

    def gera_cobranca(self, area_id: str) -> bool:
        """Regra de negócio 2. Área desconhecida não cobra: a reserva vai falhar antes disso."""
        area = self.areas.buscar(area_id)
        return area is not None and area.gera_cobranca

    def minhas_reservas(self, apartamento: str) -> list[Reserva]:
        return self.agenda.reservas_ativas_do_apartamento(apartamento)

    def disponivel(self, area_id: str, data: str) -> bool:
        """Só diz se a data está livre. Quem reservou não sai daqui (constituição 5)."""
        return not self.agenda.ocupada(self._area(area_id).id, data_de_texto(data))

    def reservar(self, apartamento: str, area_id: str, data: str) -> Reserva:
        """Grava a reserva. Levanta DataIndisponivel se outra reserva ativa vencer a corrida."""
        return self.agenda.gravar_reserva(apartamento, self._area(area_id).id, data_de_texto(data))

    def cancelar(self, apartamento: str, area_id: str, data: str) -> Reserva:
        """Cancela por área e data, dentro das reservas do apartamento.

        O código é resolvido aqui, na lista do próprio apartamento: reserva de outro
        apartamento não está nessa lista, então nem o código dela é tocado.
        """
        procurada = data_de_texto(data)
        for reserva in self.agenda.reservas_ativas_do_apartamento(apartamento):
            if reserva.area == area_id and reserva.data == procurada:
                return self.agenda.cancelar(apartamento, reserva.codigo)
        raise ReservaNaoEncontrada(f"{area_id} em {data}")

    def _area(self, area_id: str) -> Area:
        area = self.areas.buscar(area_id)
        if area is None:
            raise AreaDesconhecida(area_id)
        return area
