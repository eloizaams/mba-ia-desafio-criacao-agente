from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Visitante:
    apartamento: str
    nome: str
    data: date
