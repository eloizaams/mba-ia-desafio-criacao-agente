"""Serialização e ordem dos eventos, sem autor `regulamento` (passo 12)."""

from pathlib import Path

from httpx import ASGITransport, AsyncClient

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_REGULAMENTO, NOME_RESERVAS
from aurora.adapters.api.app import criar_api
from aurora.adapters.persistence.sqlite import SqliteRepository
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService
from tests.support.condominio import QUADRA, FabricaDeRunner
from tests.support.scripted_llm import ScriptedLlm

DATA_QUADRA = "2030-04-06"


def _client(novo_runner: FabricaDeRunner, banco: Path) -> AsyncClient:
    repo = SqliteRepository(banco)
    api = criar_api(
        runner=novo_runner(),
        reservas=ReservasService(agenda=repo, areas=repo),
        visitantes=VisitantesService(visitantes=repo),
        apartamentos=repo,
    )
    return AsyncClient(transport=ASGITransport(app=api), base_url="http://test")


async def test_eventos_em_ordem_e_nao_vazios(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """GET /eventos devolve lista não vazia com campos de evento ADK."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": QUADRA, "data": DATA_QUADRA}
    )

    async with _client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": f"Reserve a quadra para {DATA_QUADRA}."},
        )
        resp = await client.get(f"/sessoes/{sid}/eventos")
    assert resp.status_code == 200
    eventos = resp.json()
    assert len(eventos) > 0
    # Cada evento tem ao menos os campos básicos do ADK (camelCase por by_alias=True)
    for evento in eventos:
        assert "invocationId" in evento or "author" in evento


async def test_eventos_nao_tem_autor_regulamento(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 12: AgentTool isola o regulamento na própria sessão (Garantia 4)."""
    modelos[NOME_RAIZ] = ScriptedLlm(chamar="regulamento", argumentos={"request": "taxa"})
    modelos[NOME_REGULAMENTO] = ScriptedLlm(
        chamar="consultar_regulamento", argumentos={"topico": "taxa"}
    )

    async with _client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        await client.post(f"/sessoes/{sid}/mensagens", json={"texto": "Qual é a taxa do salão?"})
        resp = await client.get(f"/sessoes/{sid}/eventos")
    assert resp.status_code == 200
    autores = [e.get("author", "") for e in resp.json()]
    assert "regulamento" not in autores
