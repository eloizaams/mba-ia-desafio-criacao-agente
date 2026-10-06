import os
from pathlib import Path

CAMINHO_BANCO_PADRAO = "aurora.db"


def caminho_banco() -> Path:
    return Path(os.environ.get("AURORA_DB_PATH", CAMINHO_BANCO_PADRAO))
