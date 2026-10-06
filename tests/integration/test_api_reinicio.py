"""Garantia 3: app novo sobre o mesmo banco (passo 13).

Sessões e eventos persistem no SQLite; um novo processo continua de onde parou.
"""

from pathlib import Path

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_RESERVAS
from aurora.adapters.persistence.sqlite import SqliteRepository
from tests.support.api import novo_client
from tests.support.condominio import SALAO, FabricaDeRunner
from tests.support.scripted_llm import ScriptedLlm

DATA_SALAO = "2030-04-20"


async def test_app_novo_ve_mesmos_eventos_e_aceita_nova_mensagem(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 13a: eventos sobrevivem ao reinício."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_SALAO}
    )

    async with novo_client(novo_runner, banco) as c1:
        sid = (await c1.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        await c1.post(
            f"/sessoes/{sid}/mensagens", json={"texto": f"Reserve o salão para {DATA_SALAO}."}
        )
        eventos_antes = (await c1.get(f"/sessoes/{sid}/eventos")).json()

    async with novo_client(novo_runner, banco) as c2:
        eventos_depois = (await c2.get(f"/sessoes/{sid}/eventos")).json()
        assert len(eventos_depois) == len(eventos_antes)

        resp = await c2.post(f"/sessoes/{sid}/mensagens", json={"texto": "Olá de novo."})
        assert resp.status_code == 200
        eventos_apos_nova = (await c2.get(f"/sessoes/{sid}/eventos")).json()
        assert len(eventos_apos_nova) > len(eventos_depois)


async def test_app_novo_aprova_pendencia_anterior(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 13b: confirmação pendente continua respondível após reinício."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_SALAO}
    )

    async with novo_client(novo_runner, banco) as c1:
        sid = (await c1.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await c1.post(
            f"/sessoes/{sid}/mensagens", json={"texto": f"Reserve o salão para {DATA_SALAO}."}
        )
        pid = resp.json()["confirmacoes_pendentes"][0]["id"]

    async with novo_client(novo_runner, banco) as c2:
        resp_conf = await c2.post(
            f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": True}
        )
        assert resp_conf.status_code == 200

    repo = SqliteRepository(banco)
    reservas = repo.reservas_ativas_do_apartamento("101")
    assert any(r.area == SALAO for r in reservas)
