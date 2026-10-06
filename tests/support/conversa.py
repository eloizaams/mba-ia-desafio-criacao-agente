"""Atalhos para conversar com o Runner nos testes.

Usa o código de produção de `adapters/adk/conversa.py` — sem duplicar a lógica.
"""

import re

from google.adk.runners import Runner

from aurora.adapters.adk.confirmacoes import PendenciaConfirmacao, pendentes
from aurora.adapters.adk.conversa import confirmar, enviar
from aurora.adapters.adk.sessoes import buscar_sessao

__all__ = [
    "contem_numero_isolado",
    "enviar",
    "eventos_em_texto",
    "pendencias",
    "responder_confirmacao",
]


async def responder_confirmacao(
    runner: Runner, sessao_id: str, id_da_pendencia: str, confirmado: bool
) -> None:
    await confirmar(runner, sessao_id, id_da_pendencia, confirmado)


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
