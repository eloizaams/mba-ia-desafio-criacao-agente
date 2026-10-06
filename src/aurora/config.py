import os
from pathlib import Path

CAMINHO_BANCO_PADRAO = "aurora.db"


def database_path() -> Path:
    return Path(os.environ.get("AURORA_DB_PATH", CAMINHO_BANCO_PADRAO))
