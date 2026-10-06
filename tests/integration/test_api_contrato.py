"""Contrato da API: status codes e formato (passos 2, 6, 7, 8, 9, 11).

Usa ScriptedLlm via `modelos` e `novo_runner` do conftest, sem GOOGLE_API_KEY.
O runner é criado DENTRO de cada teste, depois de configurar os modelos —
o mesmo padrão dos testes de agentes.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from google.genai.errors import ServerError

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_RESERVAS, NOME_VISITANTES
from tests.support.api import novo_client
from tests.support.condominio import QUADRA, SALAO, FabricaDeRunner
from tests.support.scripted_llm import ScriptedLlm

DATA_SALAO = "2030-04-20"
DATA_QUADRA = "2030-04-06"


async def test_post_sessoes_apartamento_existente_retorna_201(
    novo_runner: FabricaDeRunner, banco: Path
) -> None:
    """Passo 2: sessão criada."""
    async with novo_client(novo_runner, banco) as client:
        resp = await client.post("/sessoes", json={"apartamento": "101"})
    assert resp.status_code == 201
    assert "session_id" in resp.json()


async def test_post_sessoes_apartamento_inexistente_retorna_422(
    novo_runner: FabricaDeRunner, banco: Path
) -> None:
    """Passo 2: apartamento inválido."""
    async with novo_client(novo_runner, banco) as client:
        resp = await client.post("/sessoes", json={"apartamento": "999"})
    assert resp.status_code == 422


async def test_get_eventos_sessao_inexistente_retorna_404(
    novo_runner: FabricaDeRunner, banco: Path
) -> None:
    """Passo 9: 404 em GET /eventos."""
    async with novo_client(novo_runner, banco) as client:
        resp = await client.get("/sessoes/nao-existe/eventos")
    assert resp.status_code == 404


async def test_post_mensagem_sessao_inexistente_retorna_404(
    novo_runner: FabricaDeRunner, banco: Path
) -> None:
    async with novo_client(novo_runner, banco) as client:
        resp = await client.post("/sessoes/nao-existe/mensagens", json={"texto": "oi"})
    assert resp.status_code == 404


async def test_post_confirmacao_sessao_inexistente_retorna_404(
    novo_runner: FabricaDeRunner, banco: Path
) -> None:
    async with novo_client(novo_runner, banco) as client:
        resp = await client.post(
            "/sessoes/nao-existe/confirmacoes", json={"id": "x", "confirmado": True}
        )
    assert resp.status_code == 404


async def test_reserva_sem_taxa_nao_pede_confirmacao_e_aparece_em_reservas(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 6: quadra sem taxa, sem pendência, reserva visível."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": QUADRA, "data": DATA_QUADRA}
    )

    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": f"Reserve a quadra para {DATA_QUADRA}."},
        )
        assert resp.status_code == 200
        assert resp.json()["confirmacoes_pendentes"] == []
        reservas = (await client.get("/apartamentos/101/reservas")).json()
    assert any(r["area"] == QUADRA and r["data"] == DATA_QUADRA for r in reservas)


async def test_reserva_com_taxa_gera_pendencia_e_nao_grava(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 7: salão com taxa, pendência criada, sem reserva."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_SALAO}
    )

    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": f"Reserve o salão para {DATA_SALAO}."},
        )
        assert resp.status_code == 200
        assert resp.json()["resposta"] == ""
        pendentes = resp.json()["confirmacoes_pendentes"]
        assert len(pendentes) == 1
        assert pendentes[0]["detalhes"]["area"] == SALAO
        assert pendentes[0]["detalhes"]["data"] == DATA_SALAO
        reservas = (await client.get("/apartamentos/101/reservas")).json()
    assert not any(r["area"] == SALAO and r["data"] == DATA_SALAO for r in reservas)


async def test_negar_confirmacao_nao_grava(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 7: negar não cria reserva."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_SALAO}
    )

    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": f"Reserve o salão para {DATA_SALAO}."},
        )
        pid = resp.json()["confirmacoes_pendentes"][0]["id"]
        resp_neg = await client.post(
            f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": False}
        )
        assert resp_neg.status_code == 200
        reservas = (await client.get("/apartamentos/101/reservas")).json()
    assert not any(r["area"] == SALAO and r["data"] == DATA_SALAO for r in reservas)


async def test_aprovar_grava_e_reenviar_mesmo_id_retorna_409(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 8: aprovação grava; segundo envio do mesmo id → 409."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(
        chamar="reservar", argumentos={"area": SALAO, "data": DATA_SALAO}
    )

    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": f"Reserve o salão para {DATA_SALAO}."},
        )
        pid = resp.json()["confirmacoes_pendentes"][0]["id"]

        resp_ok = await client.post(
            f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": True}
        )
        assert resp_ok.status_code == 200

        reservas = (await client.get("/apartamentos/101/reservas")).json()
        assert any(r["area"] == SALAO and r["data"] == DATA_SALAO for r in reservas)

        resp_409 = await client.post(
            f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": True}
        )
    assert resp_409.status_code == 409


async def test_id_inexistente_retorna_409(novo_runner: FabricaDeRunner, banco: Path) -> None:
    """Passo 9: id inventado → 409."""
    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/confirmacoes", json={"id": "id-inventado", "confirmado": True}
        )
    assert resp.status_code == 409


async def test_autorizar_visitante_gera_pendencia_e_aprovar_registra(
    novo_runner: FabricaDeRunner,
    banco: Path,
    modelos: dict[str, ScriptedLlm],
) -> None:
    """Passo 11: visitante com confirmação."""
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_VISITANTES)
    modelos[NOME_VISITANTES] = ScriptedLlm(
        chamar="autorizar_visitante",
        argumentos={"nome": "Joana Ribeiro", "data": "2030-04-21"},
    )

    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        resp = await client.post(
            f"/sessoes/{sid}/mensagens",
            json={"texto": "Libera a entrada da Joana Ribeiro no dia 2030-04-21."},
        )
        assert resp.status_code == 200
        pendentes = resp.json()["confirmacoes_pendentes"]
        assert len(pendentes) == 1
        assert pendentes[0]["detalhes"]["nome"] == "Joana Ribeiro"

        visitantes_antes = (await client.get("/apartamentos/101/visitantes")).json()
        assert not any(v["nome"] == "Joana Ribeiro" for v in visitantes_antes)

        pid = pendentes[0]["id"]
        await client.post(f"/sessoes/{sid}/confirmacoes", json={"id": pid, "confirmado": True})

        visitantes_depois = (await client.get("/apartamentos/101/visitantes")).json()
    assert any(v["nome"] == "Joana Ribeiro" for v in visitantes_depois)


async def test_server_error_vira_503(novo_runner: FabricaDeRunner, banco: Path) -> None:
    """ServerError do modelo vira 503 (handler registrado em criar_api)."""
    async with novo_client(novo_runner, banco) as client:
        sid = (await client.post("/sessoes", json={"apartamento": "101"})).json()["session_id"]
        with patch(
            "aurora.adapters.api.app.enviar",
            new=AsyncMock(side_effect=ServerError(503, {"error": {"message": "overloaded"}})),
        ):
            resp = await client.post(f"/sessoes/{sid}/mensagens", json={"texto": "oi"})
    assert resp.status_code == 503
    assert "AURORA_MODELO_*" in resp.json()["detail"]
