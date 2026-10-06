"""Fábrica de AsyncClient para os testes de API."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from aurora.adapters.api.app import criar_api
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService
from tests.support.condominio import FabricaDeRunner


def novo_client(novo_runner: FabricaDeRunner, banco: Path) -> AsyncClient:
    repo = SqliteRepository(banco)
    api = criar_api(
        runner=novo_runner(),
        reservas=ReservasService(agenda=repo, areas=repo),
        visitantes=VisitantesService(visitantes=repo),
        apartamentos=repo,
    )
    return AsyncClient(transport=ASGITransport(app=api), base_url="http://test")
