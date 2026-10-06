class DominioError(Exception):
    """Base dos erros de regra de negócio."""


class DataIndisponivel(DominioError):
    """A área já tem reserva ativa nessa data."""


class DadoInvalido(DominioError):
    """Entrada de domínio fora da regra, por exemplo visitante sem nome."""


class ReservaNaoEncontrada(DominioError):
    """Não há reserva ativa com esse código no apartamento informado."""


class AreaDesconhecida(DominioError):
    """Não existe área comum com esse id."""
