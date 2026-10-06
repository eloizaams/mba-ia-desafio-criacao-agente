"""Garantia 4: o regulamento é consultado, não carregado (passo 12)."""

from aurora.adapters.adk.agentes import INSTRUCAO_RAIZ, NOME_RAIZ, NOME_REGULAMENTO
from aurora.adapters.adk.sessoes import buscar_sessao, criar_sessao
from tests.support.condominio import FabricaDeRunner
from tests.support.conversa import enviar, eventos_em_texto
from tests.support.scripted_llm import ScriptedLlm

PERGUNTA = "Até que horas a piscina funciona aos domingos?"
FECHAMENTO_NO_DOMINGO = "20h"

# Trechos de capítulos que tratam de outros assuntos. Se qualquer um aparecer na sessão
# do morador, o regulamento virou contexto carregado — é o que a Garantia 4 proíbe.
TRECHOS_DE_OUTROS_CAPITULOS = ("brinquedoteca", "anilhas", "coleta seletiva", "vaga de garagem")


def _roteiro_do_regulamento(modelos: dict[str, ScriptedLlm]) -> None:
    modelos[NOME_RAIZ] = ScriptedLlm(chamar=NOME_REGULAMENTO, argumentos={"request": PERGUNTA})
    # `foco` faz o modelo responder com a frase do resultado que fala de domingos: a
    # resposta precisa sair do capítulo recuperado, não do roteiro do teste.
    modelos[NOME_REGULAMENTO] = ScriptedLlm(
        chamar="consultar_regulamento",
        argumentos={"topico": "piscina domingos"},
        foco="domingos",
    )


async def test_resposta_traz_o_horario_do_regulamento(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm]
) -> None:
    _roteiro_do_regulamento(modelos)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, PERGUNTA)

    assert FECHAMENTO_NO_DOMINGO in await eventos_em_texto(runner, sessao.id)


async def test_a_sessao_do_morador_nao_recebe_evento_do_agente_de_regulamento(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm]
) -> None:
    """`AgentTool` roda em sessão própria: só o resultado volta, nenhum evento."""
    _roteiro_do_regulamento(modelos)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, PERGUNTA)

    recarregada = await buscar_sessao(runner, sessao.id)
    assert recarregada is not None
    assert {evento.author for evento in recarregada.events} == {"user", NOME_RAIZ}


async def test_nenhum_evento_traz_capitulo_de_outro_assunto(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm]
) -> None:
    _roteiro_do_regulamento(modelos)
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, PERGUNTA)

    eventos = (await eventos_em_texto(runner, sessao.id)).lower()
    assert [trecho for trecho in TRECHOS_DE_OUTROS_CAPITULOS if trecho in eventos] == []


def test_o_agente_principal_nao_recebe_o_regulamento_nas_instrucoes() -> None:
    """Passo 15, verificado na própria instrução: ela fala da tool, não do conteúdo."""
    assert "Art." not in INSTRUCAO_RAIZ
    assert "Capítulo" not in INSTRUCAO_RAIZ
    assert "regulamento" in INSTRUCAO_RAIZ


async def test_topico_sem_capitulo_leva_a_uma_segunda_consulta_por_titulo(
    novo_runner: FabricaDeRunner, modelos: dict[str, ScriptedLlm]
) -> None:
    """Spec 002: "se nada casar, só os títulos, para uma segunda tentativa".

    O índice de títulos é o que permite ao agente acertar o capítulo sem nunca
    receber o documento inteiro.
    """
    modelos[NOME_RAIZ] = ScriptedLlm(
        chamar=NOME_REGULAMENTO, argumentos={"request": "posso ter cachorro?"}
    )
    modelos[NOME_REGULAMENTO] = ScriptedLlm(
        chamar="consultar_regulamento",
        argumentos={"topico": "cachorro"},
        campo_vazio="capitulos",
        segunda_chamada={"topico": "Capítulo VIII: Animais de estimação"},
        foco="animais",
    )
    runner = novo_runner()
    sessao = await criar_sessao(runner, "101")

    await enviar(runner, sessao.id, "Posso ter cachorro no apartamento?")

    eventos = await eventos_em_texto(runner, sessao.id)
    # Só a segunda consulta devolve capítulo: "cachorro" não casa com nenhum título e a
    # primeira volta com `capitulos` vazio. Capítulo na resposta = a retentativa rodou.
    assert '\\"capitulos\\": [{' in eventos
    assert "Capítulo VIII: Animais de estimação" in eventos
    assert [trecho for trecho in TRECHOS_DE_OUTROS_CAPITULOS if trecho in eventos.lower()] == []
