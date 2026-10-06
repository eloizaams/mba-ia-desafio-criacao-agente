"""O estado inicial de `dados/`, nomeado uma vez só.

São os mesmos valores que o avaliador usa nos passos 1 a 14. Ficam aqui para que
mudar o seed não vire caça a literais espalhados pelos testes.
"""

from collections.abc import Callable
from pathlib import Path

from google.adk.runners import Runner

DADOS = Path(__file__).parents[2] / "dados"
REGULAMENTO = DADOS / "regulamento.md"

SALAO = "salao-de-festas"
CHURRASQUEIRA = "churrasqueira"
QUADRA = "quadra"

# Reserva e visitante do 302: o que nunca pode aparecer numa sessão do 101.
RESERVA_DO_302 = "RSV-4821"
DATA_DO_302 = "2030-03-16"
VISITANTE_DO_302 = "Marina Duarte"

RESERVA_DO_101 = "RSV-1377"
DATA_DO_101 = "2030-03-09"

# Uma fábrica, não uma instância: chamar de novo é o que simula a API reiniciada.
FabricaDeRunner = Callable[[], Runner]
