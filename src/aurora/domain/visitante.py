from dataclasses import dataclass
from datetime import date

from aurora.domain.erros import DadoInvalido


@dataclass(frozen=True)
class Visitante:
    apartamento: str
    nome: str
    data: date

    def __post_init__(self) -> None:
        if not self.nome.strip():
            raise DadoInvalido("visitante precisa de nome")
