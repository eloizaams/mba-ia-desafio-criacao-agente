"""FastAPI da Aurora.

`criar_api` recebe o runner e os serviços prontos: a API não configura o banco
nem lê variáveis de ambiente. Isso mantém os testes isolados e o `main.py` como
único ponto de composição para a execução real.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from google.adk.runners import Runner
from google.genai.errors import ClientError, ServerError

from aurora.adapters.adk.confirmacoes import pendentes
from aurora.adapters.adk.conversa import confirmar, enviar
from aurora.adapters.adk.eventos import evento_para_json
from aurora.adapters.adk.sessoes import buscar_sessao, criar_sessao
from aurora.adapters.api.schemas import (
    Mensagem,
    NovaSessao,
    Pendencia,
    ReservaApi,
    RespostaConfirmacao,
    RespostaConversa,
    SessaoCriada,
    VisitanteApi,
)
from aurora.application.ports import ApartamentoRepository
from aurora.application.reservas import ReservasService
from aurora.application.visitantes import VisitantesService

_503_DETALHE = (
    "Modelo temporariamente indisponível. "
    "Tente novamente ou troque AURORA_MODELO_* por outro modelo."
)


def _pendencia_api(p: Any) -> Pendencia:
    return Pendencia(id=p.id, acao=p.acao, detalhes=p.detalhes)


def _resposta_conversa(turno: Any) -> RespostaConversa:
    return RespostaConversa(
        resposta=turno.resposta,
        confirmacoes_pendentes=[_pendencia_api(p) for p in turno.pendencias],
    )


def criar_api(
    runner: Runner,
    reservas: ReservasService,
    visitantes: VisitantesService,
    apartamentos: ApartamentoRepository,
) -> FastAPI:
    app = FastAPI(title="Aurora API")

    @app.exception_handler(ServerError)
    async def _server_error(_req: Request, exc: ServerError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": _503_DETALHE})

    @app.exception_handler(ClientError)
    async def _client_error(_req: Request, exc: ClientError) -> JSONResponse:
        if exc.code == 429:
            return JSONResponse(status_code=503, content={"detail": _503_DETALHE})
        raise exc

    @app.post("/sessoes", status_code=201, response_model=SessaoCriada)
    async def post_sessoes(corpo: NovaSessao) -> SessaoCriada:
        if not apartamentos.existe(corpo.apartamento):
            raise HTTPException(status_code=422, detail="Apartamento não encontrado")
        sessao = await criar_sessao(runner, corpo.apartamento)
        return SessaoCriada(session_id=sessao.id)

    @app.post("/sessoes/{session_id}/mensagens", response_model=RespostaConversa)
    async def post_mensagem(session_id: str, corpo: Mensagem) -> RespostaConversa:
        await _exigir_sessao(session_id)
        turno = await enviar(runner, session_id, corpo.texto)
        return _resposta_conversa(turno)

    @app.post("/sessoes/{session_id}/confirmacoes", response_model=RespostaConversa)
    async def post_confirmacao(session_id: str, corpo: RespostaConfirmacao) -> RespostaConversa:
        sessao = await _exigir_sessao(session_id)
        # Guarda do 409: id fora da lista levanta ValueError no Runner (DESAFIOS.md)
        if not any(p.id == corpo.id for p in pendentes(sessao.events)):
            raise HTTPException(
                status_code=409, detail="Confirmação não encontrada ou já respondida"
            )
        turno = await confirmar(runner, session_id, corpo.id, corpo.confirmado)
        return _resposta_conversa(turno)

    @app.get("/sessoes/{session_id}/eventos")
    async def get_eventos(session_id: str) -> list[dict[str, Any]]:
        sessao = await _exigir_sessao(session_id)
        return [evento_para_json(e) for e in sessao.events]

    @app.get("/apartamentos/{numero}/reservas", response_model=list[ReservaApi])
    def get_reservas(numero: str) -> list[ReservaApi]:
        return [
            ReservaApi(codigo=r.codigo, area=r.area, data=r.data.isoformat())
            for r in reservas.minhas_reservas(numero)
        ]

    @app.get("/apartamentos/{numero}/visitantes", response_model=list[VisitanteApi])
    def get_visitantes(numero: str) -> list[VisitanteApi]:
        return [
            VisitanteApi(nome=v.nome, data=v.data.isoformat())
            for v in visitantes.meus_visitantes(numero)
        ]

    async def _exigir_sessao(session_id: str) -> Any:
        sessao = await buscar_sessao(runner, session_id)
        if sessao is None:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        return sessao

    return app
