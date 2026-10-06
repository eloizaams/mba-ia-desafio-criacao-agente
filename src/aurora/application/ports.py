from datetime import date
from typing import Protocol

from aurora.domain.area import Area
from aurora.domain.regulamento import Capitulo
from aurora.domain.reserva import Reserva
from aurora.domain.visitante import Visitante


class AreaRepository(Protocol):
    def buscar(self, area_id: str) -> Area | None: ...

    def listar(self) -> list[Area]: ...


class AgendaRepository(Protocol):
    def ocupada(self, area: str, data: date) -> bool:
        """Só diz se a data está ocupada. Não revela quem reservou."""
        ...

    def gravar_reserva(self, apartamento: str, area: str, data: date) -> Reserva:
        """Grava a reserva ativa. Levanta DataIndisponivel se a área já estiver ocupada na data."""
        ...

    def reservas_ativas_do_apartamento(self, apartamento: str) -> list[Reserva]: ...

    def cancelar(self, apartamento: str, codigo: str) -> Reserva:
        """Cancela só reserva ativa do apartamento. Senão, levanta ReservaNaoEncontrada."""
        ...


class VisitanteRepository(Protocol):
    def autorizar(self, apartamento: str, nome: str, data: date) -> Visitante: ...

    def do_apartamento(self, apartamento: str) -> list[Visitante]: ...


class ApartamentoRepository(Protocol):
    def existe(self, numero: str) -> bool: ...


class RegulamentoRepository(Protocol):
    def capitulos(self) -> list[Capitulo]:
        """Todos os capítulos. Não vai para a conversa: serve à seleção por tópico."""
        ...
