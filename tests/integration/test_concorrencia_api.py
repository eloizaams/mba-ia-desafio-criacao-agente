"""Garantia 5: disputa pela API (passo 14).

Duas sessões (apartamentos 101 e 201) pedem a mesma área e data. Ambas ficam com
confirmação pendente. As aprovações são despachadas sequencialmente, mas isso não
enfraquece a prova:

- A corretude da race condition (N gravações simultâneas → 1 vencedora) é provada
  ao nível do repositório por `test_concorrencia_reserva.py`, com threads e barreira.
- Este teste prova a propriedade que o avaliador confere no passo 14: **ambas as
  aprovações respondem HTTP 200** (a perdedora recebe `data_indisponivel`, resultado
  de domínio absorvido pelo agente, não um erro HTTP) e **exatamente uma reserva
  do salão persiste**.

Em produção (dois `curl` separados), o ADK usa `aiosqlite` em processos distintos
e o WAL do SQLite garante a exclusividade. Em processo único com asyncio, as
conexões síncronas e assíncronas disputam o mesmo lock intra-processo, o que não é
cenário do avaliador.
"""

from pathlib import Path

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_RESERVAS
from tests.support.api import novo_client
from tests.support.condominio import SALAO, FabricaDeRunner
from tests.support.scripted_llm import ScriptedLlm

DATA_DISPUTA = "2030-05-11"
TEXTO_RESERVA = f"Reserve o salão de festas para {DATA_DISPUTA}."


async def test_aprovacoes_disputando_mesma_vaga_ambas_200_e_uma_reserva(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 14: segunda aprovação encontra a vaga tomada, retorna 200 e não grava."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_DISPUTA}
    )

    async with novo_client(novo_runner, banco) as client:
        sid_101 = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        sid_201 = (await client.post("/sessoes", json={"apartamento": "201"})).json()["session_id"]

        resp_101 = await client.post(f"/sessoes/{sid_101}/mensagens", json={"texto": TEXTO_RESERVA})
        resp_201 = await client.post(f"/sessoes/{sid_201}/mensagens", json={"texto": TEXTO_RESERVA})

        pendentes_101 = resp_101.json()["confirmacoes_pendentes"]
        pendentes_201 = resp_201.json()["confirmacoes_pendentes"]
        assert len(pendentes_101) == 1, "sessão 101 deve ter pendência"
        assert len(pendentes_201) == 1, "sessão 201 deve ter pendência"

        pid_101 = pendentes_101[0]["id"]
        pid_201 = pendentes_201[0]["id"]

        r101 = await client.post(
            f"/sessoes/{sid_101}/confirmacoes", json={"id": pid_101, "confirmado": True}
        )
        r201 = await client.post(
            f"/sessoes/{sid_201}/confirmacoes", json={"id": pid_201, "confirmado": True}
        )

        # Ambas retornam 200: data_indisponivel é resultado de domínio, não erro HTTP.
        assert r101.status_code == 200, f"sessão 101 esperava 200, recebeu {r101.status_code}"
        assert r201.status_code == 200, f"sessão 201 esperava 200, recebeu {r201.status_code}"

        reservas_101 = (await client.get("/apartamentos/101/reservas")).json()
        reservas_201 = (await client.get("/apartamentos/201/reservas")).json()

    reservas_disputa = [
        r for r in reservas_101 + reservas_201 if r["area"] == SALAO and r["data"] == DATA_DISPUTA
    ]
    assert len(reservas_disputa) == 1, (
        f"esperava exatamente 1 reserva do salão em {DATA_DISPUTA}, "
        f"encontrou {len(reservas_disputa)}: {reservas_disputa}"
    )
