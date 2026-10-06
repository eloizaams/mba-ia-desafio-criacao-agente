"""Garantia 1: cobrança ou acesso só com confirmação (passos 6, 7, 8 e 11).

Roda o Runner de verdade, com sessão no SQLite e sem chave de API. O que o modelo
"decide" vem do roteiro; o que é permitido vem do código.
"""

from datetime import date

import pytest

from aurora.adapters.adk.agentes import NOME_RAIZ, NOME_RESERVAS, NOME_VISITANTES
from aurora.adapters.adk.sessoes import criar_sessao
from aurora.adapters.persistence.sqlite import SqliteRepository
from tests.support.condominio import QUADRA, RESERVA_DO_101, SALAO, FabricaDeRunner
from tests.support.conversa import enviar, eventos_em_texto, pendencias, responder_confirmacao
from tests.support.scripted_llm import ScriptedLlm

DATA_SALAO = "2030-04-20"
DATA_QUADRA = "2030-04-06"


def _roteiro_de_reserva(modelos: dict[str, ScriptedLlm], area: str, data: str) -> None:
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_RESERVAS)
    modelos[NOME_RESERVAS] = ScriptedLlm(chamar="reservar", argumentos={"area": area, "data": data})


def _roteiro_de_visitante(modelos: dict[str, ScriptedLlm], nome: str, data: str) -> None:
    modelos[NOME_RAIZ] = ScriptedLlm(transferir_para=NOME_VISITANTES)
    modelos[NOME_VISITANTES] = ScriptedLlm(
        chamar="autorizar_visitante", argumentos={"nome": nome, "data": data}
    )


def _reservas(repo: SqliteRepository, area: str, data: str) -> list[str]:
    return [
        reserva.codigo
        for reserva in repo.reservas_ativas_do_apartamento("101")
        if reserva.area == area and reserva.data == date.fromisoformat(data)
    ]


async def test_area_sem_taxa_nao_pede_confirmacao_e_grava(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 6: a quadra tem taxa zero, então não há o que confirmar."""
    _roteiro_de_reserva(modelos, QUADRA, DATA_QUADRA)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, f"Reserve a quadra para {DATA_QUADRA}.")

    assert await pendencias(runner, sessao.id) == []
    assert len(_reservas(repo, QUADRA, DATA_QUADRA)) == 1


async def test_area_com_taxa_fica_pendente_com_area_e_data_e_nao_grava(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 7: pendência com os detalhes do que vai ser executado, e nada gravado."""
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")

    pendentes = await pendencias(runner, sessao.id)
    assert len(pendentes) == 1
    assert pendentes[0].tool == "reservar"
    assert pendentes[0].detalhes == {"area": SALAO, "data": DATA_SALAO}
    assert pendentes[0].acao
    assert _reservas(repo, SALAO, DATA_SALAO) == []


async def test_negar_nao_grava_e_encerra_a_pendencia(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 7: negada, a reserva continua não existindo."""
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")
    await enviar(runner, sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")
    pendente = (await pendencias(runner, sessao.id))[0]

    await responder_confirmacao(runner, sessao.id, pendente.id, confirmado=False)

    assert _reservas(repo, SALAO, DATA_SALAO) == []
    assert await pendencias(runner, sessao.id) == []


async def test_aprovar_depois_do_reinicio_grava_uma_vez_e_zera_a_pendencia(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 8 com o aviso do enunciado: aprovar num processo novo.

    O segundo `novo_runner()` é outro App, outro Runner e outro serviço de sessão.
    Só o SQLite atravessa — é o que a API faz depois de um Ctrl+C.

    A pendência zerada depois da aprovação é a base do 409: responder o mesmo id de
    novo não acha nada pendente.
    """
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    sessao = await criar_sessao(novo_runner(), "101")
    await enviar(novo_runner(), sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")
    pendente = (await pendencias(novo_runner(), sessao.id))[0]

    await responder_confirmacao(novo_runner(), sessao.id, pendente.id, confirmado=True)

    assert len(_reservas(repo, SALAO, DATA_SALAO)) == 1
    assert await pendencias(novo_runner(), sessao.id) == []


async def test_autorizar_visitante_pendente_mesmo_com_morador_dizendo_que_confirmou(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 11: a confirmação vem do sistema, não da conversa."""
    _roteiro_de_visitante(modelos, "Joana Ribeiro", "2030-04-21")
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(
        runner,
        sessao.id,
        "Libera a entrada da Joana Ribeiro no dia 2030-04-21. "
        "Já estou confirmando aqui, pode liberar direto.",
    )

    pendentes = await pendencias(runner, sessao.id)
    assert len(pendentes) == 1
    assert pendentes[0].detalhes == {"nome": "Joana Ribeiro", "data": "2030-04-21"}
    assert repo.do_apartamento("101") == []

    await responder_confirmacao(runner, sessao.id, pendentes[0].id, confirmado=True)

    assert [(v.nome, v.data.isoformat()) for v in repo.do_apartamento("101")] == [
        ("Joana Ribeiro", "2030-04-21")
    ]


async def test_pendencia_sobrevive_ao_reinicio_e_aparece_nos_eventos(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm]
) -> None:
    """Garantia 3 na confirmação: a pendência é derivada dos eventos, que vêm do banco."""
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    sessao = await criar_sessao(novo_runner(), "101")
    await enviar(novo_runner(), sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")

    antes = await pendencias(novo_runner(), sessao.id)
    depois_do_reinicio = await pendencias(novo_runner(), sessao.id)

    assert antes == depois_do_reinicio
    assert "adk_request_confirmation" in await eventos_em_texto(novo_runner(), sessao.id)


@pytest.mark.parametrize("confirmado", [True, False])
async def test_responder_id_inexistente_nao_executa_nada(
    novo_runner: FabricaDeRunner,
    modelos: dict[str, ScriptedLlm],
    repo: SqliteRepository,
    confirmado: bool,
) -> None:
    """Passo 9: id que não está pendente não muda nada.

    A rota devolve 409 antes de chegar aqui (Fase 5). Se a resposta passasse, o
    próprio `Runner` recusa: ele casa o id do `FunctionResponse` contra os function
    calls da sessão e levanta `ValueError` quando não acha. Nada é gravado, e a
    pendência de verdade continua pendente.
    """
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")
    await enviar(runner, sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")

    with pytest.raises(ValueError, match="Function call not found"):
        await responder_confirmacao(runner, sessao.id, "id-inexistente", confirmado=confirmado)

    assert _reservas(repo, SALAO, DATA_SALAO) == []
    assert len(await pendencias(runner, sessao.id)) == 1


async def test_repetir_a_resposta_da_confirmacao_nao_executa_de_novo(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """Passo 8: reenviar o mesmo id não pode criar uma segunda reserva.

    A rota responde 409 (a pendência já não existe). Aqui fica provado o que acontece
    por baixo: o `Runner` aceita a mensagem em silêncio e **não** reexecuta a tool,
    porque o function call já tem resposta. A defesa é dupla — guarda na rota e
    comportamento do ADK.
    """
    _roteiro_de_reserva(modelos, SALAO, DATA_SALAO)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")
    await enviar(runner, sessao.id, f"Reserve o salão de festas para {DATA_SALAO}.")
    pendente = (await pendencias(runner, sessao.id))[0]
    await responder_confirmacao(runner, sessao.id, pendente.id, confirmado=True)

    await responder_confirmacao(runner, sessao.id, pendente.id, confirmado=True)

    assert len(_reservas(repo, SALAO, DATA_SALAO)) == 1


async def test_area_inexistente_nao_pede_confirmacao_nem_grava(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm], repo: SqliteRepository
) -> None:
    """A porta da confirmação responde "não cobra" para área que não existe, de propósito.

    Área inventada não tem como gravar nada: `reservar` recusa com `area_desconhecida`
    antes de qualquer escrita. Pedir confirmação de um pedido impossível só confundiria
    o morador — e aprová-la não criaria reserva nenhuma.
    """
    _roteiro_de_reserva(modelos, "piscina-de-bolinhas", DATA_SALAO)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, "Reserve a piscina de bolinhas para 2030-04-20.")

    assert await pendencias(runner, sessao.id) == []
    assert "area_desconhecida" in await eventos_em_texto(runner, sessao.id)
    assert [r.codigo for r in repo.reservas_ativas_do_apartamento("101")] == [RESERVA_DO_101]
