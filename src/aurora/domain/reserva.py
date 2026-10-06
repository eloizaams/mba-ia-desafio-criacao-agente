from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class StatusReserva(StrEnum):
    ATIVA = "ativa"
    CANCELADA = "cancelada"


@dataclass(frozen=True)
class Reserva:
    codigo: str
    apartamento: str
    area: str
    data: date
    status: StatusReserva = StatusReserva.ATIVA
