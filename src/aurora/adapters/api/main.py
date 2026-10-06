"""Ponto de entrada do `aurora-api`.

Lê o `.env` antes de montar o runner, porque o ADK como biblioteca não lê `.env`
sozinho. `override=False` respeita variáveis já exportadas no shell.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from aurora.adapters.adk.app import construir_runner
from aurora.adapters.api.app import criar_api
from aurora.adapters.persistence.connection import open_connection
from aurora.adapters.persistence.schema import create_schema
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService
from aurora.config import database_path


def main() -> None:
    load_dotenv(override=False)

    banco = database_path()
    runner = construir_runner(banco=banco)
    repo = SqliteRepository(banco)
    reservas = ReservasService(agenda=repo, areas=repo)
    visitantes = VisitantesService(visitantes=repo)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        conn = open_connection(banco)
        try:
            create_schema(conn)
        finally:
            conn.close()
        yield

    api = criar_api(runner=runner, reservas=reservas, visitantes=visitantes, apartamentos=repo)
    api.router.lifespan_context = lifespan

    host = os.environ.get("AURORA_HOST", "127.0.0.1")
    port = int(os.environ.get("AURORA_PORT", "8000"))
    uvicorn.run(api, host=host, port=port)


if __name__ == "__main__":
    main()
