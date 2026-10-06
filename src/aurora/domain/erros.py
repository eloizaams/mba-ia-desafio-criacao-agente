class DominioError(Exception):
    """Base dos erros de regra de negócio."""


class DataIndisponivel(DominioError):
    """A área já tem reserva ativa nessa data."""


class ReservaNaoEncontrada(DominioError):
    """Não há reserva ativa com esse código no apartamento informado."""
