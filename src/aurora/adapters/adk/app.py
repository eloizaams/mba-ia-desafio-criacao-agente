"""Montagem do App e do Runner de Aurora.

Um lugar só liga repositório, serviços, agentes e sessão: a API da Fase 5 e os
testes usam esta fábrica, para não existirem duas topologias diferentes.
"""

from pathlib import Path

from google.adk.apps._configs import ResumabilityConfig
from google.adk.apps.app import App
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService

from aurora.adapters.adk.agentes import (
    NOME_RAIZ,
    ModeloPorAgente,
    construir_raiz,
    modelo_do_ambiente,
)
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.adapters.regulamento import RegulamentoArquivo
from aurora.application.regulamento import RegulamentoService
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService
from aurora.config import database_path, regulamento_path


def construir_app(
    *,
    banco: Path,
    regulamento: Path | None = None,
    modelo: ModeloPorAgente = modelo_do_ambiente,
) -> App:
    """App com retomada ligada.

    `is_resumable=True` deixa explícito o roteamento da resposta de confirmação para o
    agente que a pediu (docs/ADK-CONFIRMACAO.md). É feature experimental no 2.11.0, e é
    por isso que a versão do ADK está fixada.
    """
    repositorio = SqliteRepository(banco)
    raiz = construir_raiz(
        reservas=ReservasService(agenda=repositorio, areas=repositorio),
        visitantes=VisitantesService(visitantes=repositorio),
        regulamento=RegulamentoService(fonte=RegulamentoArquivo(regulamento or regulamento_path())),
        modelo=modelo,
    )
    return App(
        name=NOME_RAIZ,
        root_agent=raiz,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )


def construir_runner(
    *,
    banco: Path | None = None,
    regulamento: Path | None = None,
    modelo: ModeloPorAgente = modelo_do_ambiente,
) -> Runner:
    """Runner com as sessões no mesmo SQLite dos dados do condomínio.

    `SqliteSessionService`, não `DatabaseSessionService`: o segundo exige o extra
    `google-adk[db]` (SQLAlchemy), que o projeto não instala (DESAFIOS.md).
    """
    caminho = banco or database_path()
    return Runner(
        app=construir_app(banco=caminho, regulamento=regulamento, modelo=modelo),
        session_service=SqliteSessionService(db_path=str(caminho)),
    )
