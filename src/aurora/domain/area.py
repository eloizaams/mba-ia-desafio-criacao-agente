from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Area:
    id: str
    nome: str
    taxa: Decimal

    @property
    def gera_cobranca(self) -> bool:
        return self.taxa > 0
