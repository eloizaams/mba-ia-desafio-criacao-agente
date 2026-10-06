import os
from pathlib import Path

CAMINHO_BANCO_PADRAO = "aurora.db"
CAMINHO_REGULAMENTO_PADRAO = "dados/regulamento.md"
# Escolha da Fase 2: estável e aprovado em execução real com tool calling e confirmação
# (ver docs/ADK-CONFIRMACAO.md). Trocar de modelo é mudança de ambiente, não de código.
MODELO_PADRAO = "gemini-3.5-flash"


def database_path() -> Path:
    return Path(os.environ.get("AURORA_DB_PATH", CAMINHO_BANCO_PADRAO))


def regulamento_path() -> Path:
    return Path(os.environ.get("AURORA_REGULAMENTO_PATH", CAMINHO_REGULAMENTO_PADRAO))


def modelo_principal() -> str:
    return os.environ.get("AURORA_MODELO_PRINCIPAL") or MODELO_PADRAO


def modelo_especialista() -> str:
    return os.environ.get("AURORA_MODELO_ESPECIALISTA") or MODELO_PADRAO
