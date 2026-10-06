from datetime import date

from aurora.domain.erros import DadoInvalido

FORMATO = "AAAA-MM-DD"


def data_de_texto(texto: str) -> date:
    """Lê uma data no formato do contrato da API. Texto fora do formato é DadoInvalido."""
    try:
        return date.fromisoformat(texto.strip())
    except ValueError as erro:
        raise DadoInvalido(f"data precisa estar no formato {FORMATO}: {texto!r}") from erro
