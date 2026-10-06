"""Garantia 5, passo 14: aprovações simultâneas pela API nunca devolvem 500."""

import asyncio
from pathlib import Path

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_RESERVAS
from tests.support.api import novo_client
from tests.support.condominio import SALAO, FabricaDeRunner
from tests.support.scripted_llm import ScriptedLlm

DATA_DISPUTA = "2030-05-11"
APARTAMENTOS = ["101", "102", "201", "202", "301", "302"]


async def test_aprovacoes_simultaneas_respondem_200_e_gravam_uma_reserva(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_DISPUTA}
    )

    async with novo_client(novo_runner, banco) as client:
        pendencias: list[tuple[str, str]] = []
        for apartamento in APARTAMENTOS:
            sid = (await client.post("/sessoes", json={"apartamento": apartamento})).json()[
                "session_id"
            ]
            resp = await client.post(
                f"/sessoes/{sid}/mensagens",
                json={"texto": f"Reserve o salão de festas para {DATA_DISPUTA}."},
            )
            pendencias.append((sid, resp.json()["confirmacoes_pendentes"][0]["id"]))

        respostas = await asyncio.gather(
            *(
                client.post(f"/sessoes/{sid}/confirmacoes", json={"id": cid, "confirmado": True})
                for sid, cid in pendencias
            )
        )
        assert [r.status_code for r in respostas] == [200] * len(APARTAMENTOS)

        reservas = [
            r
            for apartamento in APARTAMENTOS
            for r in (await client.get(f"/apartamentos/{apartamento}/reservas")).json()
            if r["area"] == SALAO and r["data"] == DATA_DISPUTA
        ]
    assert len(reservas) == 1
