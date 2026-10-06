"""Criação e leitura de sessão.

Aqui o apartamento entra no `state` uma única vez (Garantia 2). Depois disso,
nenhuma mensagem do morador muda essa chave: as tools só leem.

O `user_id` do ADK é fixo. O enunciado não tem autenticação, e o apartamento é do
`state`, não do usuário — com um `user_id` único a sessão é localizável só pelo
`session_id`, que é tudo o que as rotas do contrato recebem.
"""

from google.adk.runners import Runner
from google.adk.sessions.session import Session

from aurora.adapters.adk.estado import CHAVE_APARTAMENTO

USUARIO = "morador"


async def criar_sessao(runner: Runner, apartamento: str) -> Session:
    return await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id=USUARIO,
        state={CHAVE_APARTAMENTO: apartamento},
    )


async def buscar_sessao(runner: Runner, session_id: str) -> Session | None:
    """Sessão com todos os eventos, ou None se ela não existe (o 404 da Fase 5)."""
    return await runner.session_service.get_session(
        app_name=runner.app_name, user_id=USUARIO, session_id=session_id
    )
