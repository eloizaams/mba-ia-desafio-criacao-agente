import secrets


def gerar_codigo_reserva() -> str:
    """Código aleatório no formato RSV-XXXXXX. A unicidade é garantida pelo banco, não aqui."""
    return f"RSV-{secrets.token_hex(3).upper()}"
