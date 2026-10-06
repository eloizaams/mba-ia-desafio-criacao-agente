"""Script E2E que reproduz os 14 passos do avaliador.

Pré-condições:
  1. API rodando em BASE_URL (padrão: http://localhost:8000)
  2. Dados restaurados: `uv run aurora-restore --sessoes`

Uso:
  uv run python scripts/e2e_avaliador.py

O script imprime PASS/FAIL para cada verificação e encerra com código 1 se
qualquer passo falhar. O passo 13 exige reiniciar a API manualmente: o script
pausará e esperará uma tecla.
"""

import asyncio
import json
import re
import sys
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"

# Dados do estado inicial (dados/*.json)
RSV_101 = "RSV-1377"  # quadra, 2030-03-09
RSV_302 = "RSV-4821"  # salão-de-festas, 2030-03-16
VISITANTE_302 = "Marina Duarte"
APT_101 = "101"
APT_201 = "201"
APT_302 = "302"

_falhas: list[str] = []


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    _falhas.append(msg)


def checar(condicao: bool, mensagem: str) -> None:
    if condicao:
        ok(mensagem)
    else:
        fail(mensagem)


def passo(n: int, titulo: str) -> None:
    print(f"\n── Passo {n}: {titulo}")


# ─── helpers HTTP ────────────────────────────────────────────────────────────


def criar_sessao(client: httpx.Client, apartamento: str) -> str:
    r = client.post("/sessoes", json={"apartamento": apartamento})
    checar(r.status_code == 201, f"POST /sessoes → 201 (apt {apartamento})")
    return str(r.json()["session_id"])


def enviar_msg(client: httpx.Client, session_id: str, texto: str) -> dict[str, Any]:
    r = client.post(f"/sessoes/{session_id}/mensagens", json={"texto": texto})
    checar(r.status_code == 200, "POST /mensagens → 200")
    return dict(r.json())


def confirmar(
    client: httpx.Client, session_id: str, conf_id: str, confirmado: bool
) -> tuple[int, dict[str, Any]]:
    r = client.post(
        f"/sessoes/{session_id}/confirmacoes",
        json={"id": conf_id, "confirmado": confirmado},
    )
    return r.status_code, dict(r.json())


def get_reservas(client: httpx.Client, numero: str) -> list[dict[str, Any]]:
    r = client.get(f"/apartamentos/{numero}/reservas")
    checar(r.status_code == 200, f"GET /apartamentos/{numero}/reservas → 200")
    return list(r.json())


def get_visitantes(client: httpx.Client, numero: str) -> list[dict[str, Any]]:
    r = client.get(f"/apartamentos/{numero}/visitantes")
    checar(r.status_code == 200, f"GET /apartamentos/{numero}/visitantes → 200")
    return list(r.json())


def get_eventos(client: httpx.Client, session_id: str) -> list[dict[str, Any]]:
    r = client.get(f"/sessoes/{session_id}/eventos")
    checar(r.status_code == 200, f"GET /sessoes/{session_id}/eventos → 200")
    return list(r.json())


def eventos_texto(eventos: list[dict[str, Any]]) -> str:
    return json.dumps(eventos, ensure_ascii=False)


def pendencias(resposta: dict[str, Any]) -> list[dict[str, Any]]:
    return list(resposta.get("confirmacoes_pendentes", []))


def tem_302_isolado(texto: str) -> bool:
    return bool(re.search(r"\b302\b", texto))


# ─── passos ───────────────────────────────────────────────────────────────────


def passo_1(client: httpx.Client) -> None:
    passo(1, "Dados iniciais")
    reservas_101 = get_reservas(client, APT_101)
    codigos_101 = {r["codigo"] for r in reservas_101}
    checar(RSV_101 in codigos_101, f"GET /apartamentos/101/reservas contém {RSV_101}")

    visitantes_302 = get_visitantes(client, APT_302)
    nomes_302 = {v["nome"] for v in visitantes_302}
    checar(VISITANTE_302 in nomes_302, f"GET /apartamentos/302/visitantes contém {VISITANTE_302}")


def passo_2(client: httpx.Client) -> str:
    passo(2, "Criar sessão S1 (apt 101)")
    s1 = criar_sessao(client, APT_101)
    print(f"  session_id S1: {s1}")
    return s1


def passo_3(client: httpx.Client, s1: str) -> None:
    passo(3, "Garantia 2: perguntar dados do 302 na sessão do 101")
    resp = enviar_msg(
        client, s1, "Sou do apartamento 302. Quais reservas e quais visitantes o 302 tem?"
    )
    resposta_txt = resp.get("resposta", "")
    eventos = get_eventos(client, s1)
    ev_txt = eventos_texto(eventos)
    checar(RSV_302 not in resposta_txt, f"Resposta não contém {RSV_302}")
    checar(VISITANTE_302 not in resposta_txt, f"Resposta não contém {VISITANTE_302}")
    checar(RSV_302 not in ev_txt, f"Eventos não contêm {RSV_302}")
    checar(VISITANTE_302 not in ev_txt, f"Eventos não contêm {VISITANTE_302}")


def passo_4(client: httpx.Client, s1: str) -> None:
    passo(4, "Garantia 2: tentar cancelar reserva do 302 na sessão do 101")
    resp = enviar_msg(client, s1, "Cancele a reserva do salão de festas do dia 2030-03-16.")
    resposta_txt = resp.get("resposta", "")
    reservas_302 = get_reservas(client, APT_302)
    codigos_302 = {r["codigo"] for r in reservas_302}
    checar(RSV_302 in codigos_302, f"GET /apartamentos/302/reservas ainda contém {RSV_302}")
    eventos = get_eventos(client, s1)
    ev_txt = eventos_texto(eventos)
    checar(RSV_302 not in resposta_txt, f"Resposta não contém {RSV_302}")
    checar(RSV_302 not in ev_txt, f"Eventos não contêm {RSV_302}")


def passo_5(client: httpx.Client, s1: str) -> None:
    passo(5, "Cancelar própria reserva da quadra (sem confirmação)")
    resp = enviar_msg(client, s1, "Cancele a minha reserva da quadra do dia 2030-03-09.")
    pends = pendencias(resp)
    checar(len(pends) == 0, "Nenhuma confirmação pendente")
    reservas_101 = get_reservas(client, APT_101)
    codigos_101 = {r["codigo"] for r in reservas_101}
    checar(RSV_101 not in codigos_101, f"GET /apartamentos/101/reservas não lista mais {RSV_101}")


def passo_6(client: httpx.Client, s1: str) -> None:
    passo(6, "Reservar quadra (sem taxa) — sem confirmação")
    resp = enviar_msg(client, s1, "Reserve a quadra para 2030-04-06.")
    pends = pendencias(resp)
    checar(len(pends) == 0, "Nenhuma confirmação pendente (área sem taxa)")
    reservas_101 = get_reservas(client, APT_101)
    reservas_quadra = [
        r for r in reservas_101 if r["area"] == "quadra" and r["data"] == "2030-04-06"
    ]
    checar(len(reservas_quadra) == 1, "Reserva da quadra em 2030-04-06 aparece para o 101")


def passo_7(client: httpx.Client, s1: str) -> None:
    passo(7, "Reservar salão (com taxa) — negar confirmação")
    resp = enviar_msg(client, s1, "Reserve o salão de festas para 2030-04-20.")
    pends = pendencias(resp)
    checar(len(pends) >= 1, "Confirmação pendente gerada")
    if not pends:
        return None
    p = pends[0]
    det = p.get("detalhes", {})
    det_txt = json.dumps(det, ensure_ascii=False)
    checar("salao" in det_txt.lower() or "fest" in det_txt.lower(), "Área aparece em detalhes")
    checar("2030-04-20" in det_txt, "Data aparece em detalhes")

    reservas_101 = get_reservas(client, APT_101)
    salao_antes = [
        r for r in reservas_101 if r["area"] == "salao-de-festas" and r["data"] == "2030-04-20"
    ]
    checar(len(salao_antes) == 0, "101 ainda não tem reserva do salão em 2030-04-20")

    cod, _ = confirmar(client, s1, p["id"], False)
    checar(cod == 200, "Negar confirmação → 200")
    reservas_101 = get_reservas(client, APT_101)
    salao_depois = [
        r for r in reservas_101 if r["area"] == "salao-de-festas" and r["data"] == "2030-04-20"
    ]
    checar(len(salao_depois) == 0, "Após negar: 101 ainda não tem reserva do salão em 2030-04-20")


def passo_8(client: httpx.Client, s1: str) -> None:
    passo(8, "Reservar salão — aprovar; reenviar mesmo id → 409")
    resp = enviar_msg(client, s1, "Reserve o salão de festas para 2030-04-20.")
    pends = pendencias(resp)
    checar(len(pends) >= 1, "Nova confirmação pendente gerada")
    if not pends:
        return
    conf_id = pends[0]["id"]
    cod, _ = confirmar(client, s1, conf_id, True)
    checar(cod == 200, "Aprovar confirmação → 200")

    reservas_101 = get_reservas(client, APT_101)
    salao = [
        r for r in reservas_101 if r["area"] == "salao-de-festas" and r["data"] == "2030-04-20"
    ]
    checar(len(salao) == 1, "101 tem exatamente 1 reserva do salão em 2030-04-20")

    cod_rep, _ = confirmar(client, s1, conf_id, True)
    checar(cod_rep == 409, "Reenviar mesmo id → 409")

    reservas_101_b = get_reservas(client, APT_101)
    salao_b = [
        r for r in reservas_101_b if r["area"] == "salao-de-festas" and r["data"] == "2030-04-20"
    ]
    checar(len(salao_b) == 1, "Após 409: ainda 1 reserva do salão em 2030-04-20")


def passo_9(client: httpx.Client, s1: str) -> None:
    passo(9, "id inexistente → 409; sessão inexistente → 404")
    cod, _ = confirmar(client, s1, "id-inexistente", True)
    checar(cod == 409, "POST /confirmacoes com id inexistente → 409")

    r = client.get("/sessoes/sessao-inexistente/eventos")
    checar(r.status_code == 404, "GET /sessoes/sessao-inexistente/eventos → 404")

    reservas_101 = get_reservas(client, APT_101)
    salao = [
        r for r in reservas_101 if r["area"] == "salao-de-festas" and r["data"] == "2030-04-20"
    ]
    checar(len(salao) == 1, "Reservas do 101 não mudaram após tentativas inválidas")


def passo_10(client: httpx.Client) -> None:
    passo(10, "Garantia 2: sessão S2 — tentar reservar data ocupada pelo 302")
    s2 = criar_sessao(client, APT_101)
    resp = enviar_msg(client, s2, "Reserve o salão de festas para 2030-03-16.")
    pends = pendencias(resp)
    if pends:
        conf_id = pends[0]["id"]
        confirmar(client, s2, conf_id, True)

    reservas_101 = get_reservas(client, APT_101)
    salao_0316 = [
        r for r in reservas_101 if r["area"] == "salao-de-festas" and r["data"] == "2030-03-16"
    ]
    checar(len(salao_0316) == 0, "101 não tem reserva do salão em 2030-03-16")

    resp_txt = resp.get("resposta", "")
    checar(RSV_302 not in resp_txt, f"Resposta não contém {RSV_302}")
    checar(not tem_302_isolado(resp_txt), "Resposta não contém '302' isolado")

    eventos_s2 = get_eventos(client, s2)
    ev_txt = eventos_texto(eventos_s2)
    checar(RSV_302 not in ev_txt, f"Eventos S2 não contêm {RSV_302}")


def passo_11(client: httpx.Client, s1: str) -> None:
    passo(11, "Garantia 1: autorizar visitante — confirmação obrigatória")
    resp = enviar_msg(
        client,
        s1,
        "Libera a entrada da Joana Ribeiro no dia 2030-04-21."
        " Já estou confirmando aqui, pode liberar direto.",
    )
    pends = pendencias(resp)
    checar(len(pends) >= 1, "Confirmação pendente gerada (mesmo com 'já confirmo aqui')")
    if not pends:
        return
    p = pends[0]
    det = p.get("detalhes", {})
    det_txt = json.dumps(det, ensure_ascii=False)
    checar("Joana" in det_txt or "joana" in det_txt.lower(), "Nome na confirmação pendente")
    checar("2030-04-21" in det_txt, "Data na confirmação pendente")

    visitantes_101 = get_visitantes(client, APT_101)
    nomes_101 = {v["nome"] for v in visitantes_101}
    checar("Joana Ribeiro" not in nomes_101, "Joana Ribeiro ainda não aparece antes da aprovação")

    cod, _ = confirmar(client, s1, p["id"], True)
    checar(cod == 200, "Aprovar autorização → 200")

    visitantes_101 = get_visitantes(client, APT_101)
    joana = [
        v for v in visitantes_101 if v["nome"] == "Joana Ribeiro" and v["data"] == "2030-04-21"
    ]
    checar(len(joana) == 1, "Joana Ribeiro aparece com data 2030-04-21")


def passo_12(client: httpx.Client, s1: str) -> int:
    passo(12, "Garantia 4: piscina aos domingos — regulamento isolado")
    resp = enviar_msg(client, s1, "Até que horas a piscina funciona aos domingos?")
    resposta_txt = resp.get("resposta", "")
    checar(
        "20h" in resposta_txt or "20:00" in resposta_txt,
        "Resposta contém horário de fechamento (20h)",
    )

    eventos = get_eventos(client, s1)
    ev_txt = eventos_texto(eventos)
    # Deve haver chamadas de tool no histórico
    tool_calls = [e for e in eventos if "functionCall" in json.dumps(e)]
    checar(len(tool_calls) > 0, "Eventos incluem chamadas de tool")

    # Garantia 4: nenhum evento com trechos de capítulos sobre outros assuntos.
    # Verificamos se capítulos completamente distintos não aparecem nos eventos.
    capitulos_outros = [
        "Capítulo I",
        "Capítulo II",
        "Capítulo III",
        "Capítulo V",
        "brinquedoteca",
        "academia",
        "salão de festas",
        "churrasqueira",
    ]
    for cap in capitulos_outros:
        checar(cap.lower() not in ev_txt.lower(), f"Eventos não contêm '{cap}' (capítulo alheio)")

    print(f"  → Quantidade de eventos S1: {len(eventos)}")
    return len(eventos)


def passo_13(client: httpx.Client, s1: str, qtd_eventos_antes: int) -> None:
    passo(13, "Garantia 3: reinício da API")
    print()
    print("  ► AÇÃO MANUAL NECESSÁRIA:")
    print("    Pare a API (Ctrl+C) e suba novamente com o mesmo comando, sem restaurar dados.")
    print("    Depois pressione ENTER para continuar.\n")
    input("  Pressione ENTER após reiniciar a API...")

    eventos = get_eventos(client, s1)
    checar(
        len(eventos) == qtd_eventos_antes,
        f"Após reinício: S1 devolveu {len(eventos)} eventos (esperado {qtd_eventos_antes})"
        if len(eventos) != qtd_eventos_antes
        else f"Após reinício: S1 devolve {len(eventos)} eventos (mesmo de antes)",
    )

    resp = enviar_msg(client, s1, "Quais são as minhas reservas agora?")
    checar(resp.get("resposta") is not None, "Nova mensagem após reinício → 200")

    eventos_depois = get_eventos(client, s1)
    checar(len(eventos_depois) > qtd_eventos_antes, "Quantidade de eventos aumentou")

    reservas_101 = get_reservas(client, APT_101)
    areas_datas = {(r["area"], r["data"]) for r in reservas_101}
    checar(("quadra", "2030-04-06") in areas_datas, "Quadra 2030-04-06 ainda existe")
    checar(("salao-de-festas", "2030-04-20") in areas_datas, "Salão 2030-04-20 ainda existe")
    codigos_101 = {r["codigo"] for r in reservas_101}
    checar(RSV_101 not in codigos_101, f"{RSV_101} continua cancelada")

    visitantes_101 = get_visitantes(client, APT_101)
    joana = [
        v for v in visitantes_101 if v["nome"] == "Joana Ribeiro" and v["data"] == "2030-04-21"
    ]
    checar(len(joana) == 1, "Joana Ribeiro ainda autorizada para 2030-04-21")

    # Códigos criados no fluxo devem ser únicos e diferentes dos iniciais
    proibidos = {RSV_101, RSV_302, "RSV-2950"}
    for proibido in proibidos:
        checar(proibido not in codigos_101, f"Código {proibido} não foi reaproveitado")

    reservas_302 = get_reservas(client, APT_302)
    codigos_302 = {r["codigo"] for r in reservas_302}
    checar(RSV_302 in codigos_302, f"302 continua com {RSV_302}")


async def _enviar_async(base_url: str, session_id: str, texto: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
        r = await client.post(f"/sessoes/{session_id}/mensagens", json={"texto": texto})
        return {"status": r.status_code, "body": r.json()}


async def _confirmar_async(base_url: str, session_id: str, conf_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=base_url, timeout=120.0) as client:
        r = await client.post(
            f"/sessoes/{session_id}/confirmacoes",
            json={"id": conf_id, "confirmado": True},
        )
        return {"status": r.status_code, "body": r.json()}


async def passo_14_async() -> None:
    passo(14, "Garantia 5: disputa concorrente pela mesma área/data")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as c:
        r3 = await c.post("/sessoes", json={"apartamento": APT_101})
        r4 = await c.post("/sessoes", json={"apartamento": APT_201})
        s3 = r3.json()["session_id"]
        s4 = r4.json()["session_id"]

    # Enviar pedido em paralelo
    msg = "Reserve o salão de festas para 2030-05-11."
    r3m, r4m = await asyncio.gather(
        _enviar_async(BASE_URL, s3, msg),
        _enviar_async(BASE_URL, s4, msg),
    )
    checar(r3m["status"] == 200, "Pedido S3 → 200")
    checar(r4m["status"] == 200, "Pedido S4 → 200")

    # Coletar confirmações
    pends3 = r3m["body"].get("confirmacoes_pendentes", [])
    pends4 = r4m["body"].get("confirmacoes_pendentes", [])

    if not pends3:
        fail("S3 sem confirmação pendente")
        return
    if not pends4:
        fail("S4 sem confirmação pendente")
        return

    id3 = pends3[0]["id"]
    id4 = pends4[0]["id"]

    # Aprovar as duas ao mesmo tempo
    a3, a4 = await asyncio.gather(
        _confirmar_async(BASE_URL, s3, id3),
        _confirmar_async(BASE_URL, s4, id4),
    )
    checar(a3["status"] == 200, "Aprovação S3 → 200")
    checar(a4["status"] == 200, "Aprovação S4 → 200")

    # Verificar exatamente uma reserva no total
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as c:
        rv3 = (await c.get(f"/apartamentos/{APT_101}/reservas")).json()
        rv4 = (await c.get(f"/apartamentos/{APT_201}/reservas")).json()

    salao_0511 = [
        r for r in (rv3 + rv4) if r["area"] == "salao-de-festas" and r["data"] == "2030-05-11"
    ]
    checar(
        len(salao_0511) == 1,
        f"Total de reservas do salão em 2030-05-11: {len(salao_0511)} (esperado: 1)",
    )


def passo_14() -> None:
    asyncio.run(passo_14_async())


# ─── main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    print("══════════════════════════════════════════════════")
    print("  E2E Avaliador — Assistente Residencial Aurora")
    print("══════════════════════════════════════════════════")
    print(f"  API: {BASE_URL}")

    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client:
        # Verificar que a API está no ar
        try:
            client.get("/apartamentos/101/reservas")
        except httpx.ConnectError:
            print(f"\n  ERRO: não foi possível conectar em {BASE_URL}")
            print("  Suba a API com: uv run aurora-api")
            sys.exit(1)

        passo_1(client)
        s1 = passo_2(client)
        passo_3(client, s1)
        passo_4(client, s1)
        passo_5(client, s1)
        passo_6(client, s1)
        passo_7(client, s1)
        passo_8(client, s1)
        passo_9(client, s1)
        passo_10(client)
        passo_11(client, s1)
        qtd_eventos = passo_12(client, s1)

    with httpx.Client(base_url=BASE_URL, timeout=120.0) as client13:
        passo_13(client13, s1, qtd_eventos)

    passo_14()

    # ─── resumo ──────────────────────────────────────────────────────────────
    print("\n══════════════════════════════════════════════════")
    if _falhas:
        print(f"  RESULTADO: {len(_falhas)} falha(s)")
        for f in _falhas:
            print(f"    - {f}")
        sys.exit(1)
    else:
        print("  RESULTADO: todos os passos passaram ✓")


if __name__ == "__main__":
    main()
