from typing import Any

from pydantic import BaseModel


class NovaSessao(BaseModel):
    apartamento: str


class SessaoCriada(BaseModel):
    session_id: str


class Mensagem(BaseModel):
    texto: str


class RespostaConfirmacao(BaseModel):
    id: str
    confirmado: bool


class Pendencia(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]


class RespostaConversa(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[Pendencia]


class ReservaApi(BaseModel):
    codigo: str
    area: str
    data: str


class VisitanteApi(BaseModel):
    nome: str
    data: str
