"""Garantia 2: o apartamento da sessão.

A chave é gravada uma única vez, na criação da sessão (`POST /sessoes`), e lida
daqui pelas tools. Nenhuma tool tem parâmetro de apartamento, então não existe
caminho pelo qual o modelo informe um — nem validando, nem sem validar.
"""

from google.adk.tools.tool_context import ToolContext

CHAVE_APARTAMENTO = "apartamento"


class SessaoSemApartamento(RuntimeError):
    """A sessão foi criada sem apartamento no state. É defeito de quem a criou, não do morador."""


def apartamento_da_sessao(tool_context: ToolContext) -> str:
    apartamento = tool_context.state.get(CHAVE_APARTAMENTO)
    if not isinstance(apartamento, str) or not apartamento:
        raise SessaoSemApartamento(f"state['{CHAVE_APARTAMENTO}'] ausente ou inválido")
    return apartamento
