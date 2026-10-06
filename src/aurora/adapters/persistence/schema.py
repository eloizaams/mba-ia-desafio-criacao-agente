import sqlite3

DDL = """
CREATE TABLE IF NOT EXISTS areas (
    id    TEXT PRIMARY KEY,
    nome  TEXT NOT NULL,
    taxa  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apartamentos (
    numero   TEXT PRIMARY KEY,
    morador  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservas (
    codigo       TEXT PRIMARY KEY,
    apartamento  TEXT NOT NULL REFERENCES apartamentos(numero),
    area         TEXT NOT NULL REFERENCES areas(id),
    data         TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('ativa', 'cancelada'))
);

-- Regra 1: no máximo uma reserva ativa por área e data. Vale no instante do INSERT.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reserva_ativa_area_data
    ON reservas (area, data) WHERE status = 'ativa';

CREATE TABLE IF NOT EXISTS visitantes (
    -- Sem AUTOINCREMENT: o restore apaga e recarrega, e os ids voltam a começar do 1.
    id           INTEGER PRIMARY KEY,
    apartamento  TEXT NOT NULL REFERENCES apartamentos(numero),
    nome         TEXT NOT NULL,
    data         TEXT NOT NULL
);
"""


def criar_schema(conexao: sqlite3.Connection) -> None:
    conexao.executescript(DDL)
