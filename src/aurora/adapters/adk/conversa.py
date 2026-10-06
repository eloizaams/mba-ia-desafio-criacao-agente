"""Movimentos de conversa que a API e os testes compartilham.

Centraliza o loop do Runner e a extração de resposta e pendências, para que não
existam duas implementações divergentes.
"""

from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.genai import types

from aurora.adapters.adk.confirmacoes import (
    PendenciaConfirmacao,
    pendentes,
    resposta_de_confirmacao,
)
from aurora.adapters.adk.sessoes import USUARIO, buscar_sessao


@dataclass(frozen=True)
class Turno:
    resposta: str
    pendencias: list[PendenciaConfirmacao] = field(default_factory=list)


async def enviar(runner: Runner, sessao_id: str, texto: str) -> Turno:
    mensagem = types.Content(role="user", parts=[types.Part(text=texto)])
    resposta = await _executar(runner, sessao_id, mensagem)
    return resposta


async def confirmar(runner: Runner, sessao_id: str, id_pendencia: str, confirmado: bool) -> Turno:
    mensagem = resposta_de_confirmacao(id_pendencia, confirmado)
    return await _executar(runner, sessao_id, mensagem)


async def _executar(runner: Runner, sessao_id: str, mensagem: types.Content) -> Turno:
    partes: list[str] = []
    async for evento in runner.run_async(
        user_id=USUARIO, session_id=sessao_id, new_message=mensagem
    ):
        if not evento.is_final_response():
            continue
        if evento.author == "user":
            continue
        for parte in (evento.content and evento.content.parts) or []:
            if parte.thought:
                continue
            if parte.text:
                partes.append(parte.text)

    sessao = await buscar_sessao(runner, sessao_id)
    pendencias_atuais = pendentes(sessao.events) if sessao else []
    return Turno(resposta="".join(partes), pendencias=pendencias_atuais)
