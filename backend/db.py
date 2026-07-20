"""SQLite schema and connection helpers for the RAG Status app."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "rag_status.db"

PILARES = ["prazo", "escopo", "rh", "contrato", "faturamento"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS pessoas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    papel TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    industry_code TEXT NOT NULL,
    tipo_linha TEXT NOT NULL DEFAULT 'Projeto',
    bu_director_id INTEGER REFERENCES pessoas(id),
    am_id INTEGER REFERENCES pessoas(id),
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cliente_dms (
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    dm_id INTEGER NOT NULL REFERENCES pessoas(id),
    PRIMARY KEY (cliente_id, dm_id)
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    pilar TEXT NOT NULL,
    status TEXT NOT NULL,
    semana TEXT NOT NULL,
    comentario TEXT,
    atualizado_por TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_status_history_cliente_pilar
    ON status_history(cliente_id, pilar, atualizado_em);

CREATE TABLE IF NOT EXISTS riscos_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    pilar TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'risco',
    titulo TEXT NOT NULL,
    descricao TEXT,
    severidade TEXT NOT NULL DEFAULT 'media',
    responsavel TEXT,
    plano_mitigacao TEXT,
    data_alvo TEXT,
    status TEXT NOT NULL DEFAULT 'aberto',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_riscos_cliente_pilar
    ON riscos_issues(cliente_id, pilar, status);

CREATE TABLE IF NOT EXISTS criterios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilar TEXT NOT NULL,
    linha TEXT NOT NULL,
    status TEXT NOT NULL,
    descricao TEXT NOT NULL,
    ordem INTEGER NOT NULL DEFAULT 0
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def current_week_monday(ref: Optional[datetime] = None) -> str:
    ref = ref or datetime.now()
    monday = ref - timedelta(days=ref.weekday())
    return monday.strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
