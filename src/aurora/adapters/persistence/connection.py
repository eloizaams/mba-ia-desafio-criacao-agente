import sqlite3
from pathlib import Path

# Escritas concorrentes esperam até 5 s pelo lock do SQLite, sem "database is locked".
TIMEOUT_LOCK_S = 5.0


def open_connection(path: Path) -> sqlite3.Connection:
    """Conexão com as regras comuns do adaptador: FK ligada, WAL e espera pelo lock."""
    connection = sqlite3.connect(path, timeout=TIMEOUT_LOCK_S)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
