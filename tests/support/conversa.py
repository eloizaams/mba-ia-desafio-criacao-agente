"""Atalhos para conversar com o Runner nos testes.

A API da Fase 5 vai fazer os mesmos quatro movimentos: criar sessão, enviar
mensagem, derivar pendências e responder confirmação.
"""

import re

from google.adk.runners import Runner
from google.genai import types

from aurora.adapters.adk.confirmacoes import (
    PendenciaConfirmacao,
    pendentes,
    resposta_de_confirmacao,
)
from aurora.adapters.adk.sessoes import USUARIO, buscar_sessao


async def enviar(runner: Runner, sessao_id: str, texto: str) -> None:
    mensagem = types.Content(role="user", parts=[types.Part(text=texto)])
    async for _ in runner.run_async(user_id=USUARIO, session_id=sessao_id, new_message=mensagem):
        pass


async def responder_confirmacao(
    runner: Runner, sessao_id: str, id_da_pendencia: str, confirmado: bool
) -> None:
    mensagem = resposta_de_confirmacao(id_da_pendencia, confirmado)
    async for _ in runner.run_async(user_id=USUARIO, session_id=sessao_id, new_message=mensagem):
        pass


async def pendencias(runner: Runner, sessao_id: str) -> list[PendenciaConfirmacao]:
    sessao = await buscar_sessao(runner, sessao_id)
    assert sessao is not None
    return pendentes(sessao.events)


async def eventos_em_texto(runner: Runner, sessao_id: str) -> str:
    """Todos os eventos serializados.

    O avaliador procura código de reserva e nome de morador em `GET /eventos`, que
    devolve o conteúdo completo de cada evento — então é no JSON inteiro que os
    testes de vazamento precisam procurar, não só no texto das respostas.
    """
    sessao = await buscar_sessao(runner, sessao_id)
    assert sessao is not None
    return "\n".join(evento.model_dump_json() for evento in sessao.events)


def contem_numero_isolado(texto: str, numero: str) -> bool:
    """O "302 isolado" do passo 10: o número como dado, não dentro de outro número ou código.

    Os eventos do ADK carregam timestamps e ids em hexadecimal, onde "302" aparece por
    acaso — é o que o avaliador chama de "fora de outros números e códigos". O contexto
    hexadecimal e decimal fica de fora; `"apartamento": "302"` continua sendo encontrado.
    """
    return re.search(rf"(?<![0-9a-f.]){re.escape(numero)}(?![0-9a-f])", texto) is not None
