"""Seeds the Postgres (Neon) database with the real org chart (BU Directors ->
AMs -> DMs -> clients) and the macro criteria table. Safe to run once; skips
if data already exists.

Run with DATABASE_URL pointed at your Neon database, e.g.:

    DATABASE_URL="postgres://user:pass@host/dbname?sslmode=require" python3 scripts/seed.py

Self-contained (no import from api/index.py) so it has no dependency on how
the Vercel deploy packages that file.
"""
import os
import sys
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

PILARES = ["prazo", "escopo", "rh", "contrato", "faturamento"]


class _ConnWrapper:
    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        pg_sql = sql.replace("?", "%s")
        pg_params = [int(p) if isinstance(p, bool) else p for p in (params or [])]
        cur.execute(pg_sql, pg_params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS pessoas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    papel TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    pilar TEXT NOT NULL,
    linha TEXT NOT NULL,
    status TEXT NOT NULL,
    descricao TEXT NOT NULL,
    ordem INTEGER NOT NULL DEFAULT 0
);
"""


def get_conn():
    dsn = os.environ["DATABASE_URL"]
    pg_conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    return _ConnWrapper(pg_conn)


def init_db():
    conn = get_conn()
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def current_week_monday(ref=None) -> str:
    ref = ref or datetime.now()
    monday = ref - timedelta(days=ref.weekday())
    return monday.strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

# (nome, papel: 'bu_director' | 'am' | 'dm')
PESSOAS_SEED = [
    ("M. Albuquerque", "bu_director"),
    ("H. Tavares", "bu_director"),
    ("C. Sapateiro", "bu_director"),
    ("L. Nunes", "am"),
    ("R. Pires", "am"),
    ("A. Furtado", "am"),
    ("D. Lopes", "am"),
    ("D. Mazoni", "am"),
    ("P. Vilaça", "am"),
    ("L. Vieira", "am"),
    ("T. Apolinário", "am"),
    ("A. Pollis", "dm"),
    ("E. Balaciano", "dm"),
    ("C. Dana", "dm"),
    ("D. Leal", "dm"),
    ("A. Duarte", "dm"),
    ("M. Fagundes", "dm"),
    ("M. Thomaz", "dm"),
    ("M. Grilo", "dm"),
    ("D. Gonzaga", "dm"),
    ("K. Sueiro", "dm"),
]

# (nome, industry_code, tipo_linha, bu_director, am, [dms])
# AM/BU Director values reference names in PESSOAS_SEED (BU Directors sometimes act as their
# own AM directly, e.g. H. Tavares for Anatel/Petrobras, C. Sapateiro for Sys LLC).
CLIENTES_SEED = [
    ("Elera", "E&U", "Sustentação", "M. Albuquerque", "L. Nunes", ["A. Pollis"]),
    ("Equatorial", "E&U", "Sustentação", "M. Albuquerque", "L. Nunes", ["A. Pollis"]),
    ("Light", "E&U", "Sustentação", "M. Albuquerque", "L. Nunes", ["E. Balaciano"]),
    ("Globo", "CME", "Sustentação", "M. Albuquerque", "R. Pires", ["C. Dana"]),
    ("LG", "CME", "Projeto", "M. Albuquerque", "R. Pires", ["C. Dana"]),
    ("Sony", "CME", "Projeto", "M. Albuquerque", "R. Pires", ["C. Dana"]),

    ("Anatel", "GOV", "Projeto", "H. Tavares", "H. Tavares", ["D. Leal"]),
    ("CNI", "GOV", "Projeto", "H. Tavares", "H. Tavares", ["D. Leal"]),
    ("Exército", "GOV", "Projeto", "H. Tavares", "H. Tavares", ["D. Leal"]),
    ("PGDF", "GOV", "Projeto", "H. Tavares", "H. Tavares", ["D. Leal"]),
    ("SEEC-DF", "GOV", "Projeto", "H. Tavares", "H. Tavares", ["D. Leal"]),
    ("Eneva", "O&G", "Sustentação", "H. Tavares", "A. Furtado", ["A. Duarte"]),
    ("Grupo CBO", "O&G", "Sustentação", "H. Tavares", "A. Furtado", ["A. Duarte"]),
    ("Telecall", "OTH", "Projeto", "H. Tavares", "A. Furtado", ["A. Duarte"]),
    ("Vibra", "O&G", "Sustentação", "H. Tavares", "D. Lopes", ["A. Duarte"]),
    ("Sys SAS", "OTH", "Projeto", "H. Tavares", "D. Mazoni", ["M. Fagundes"]),
    ("Petrobras", "O&G", "Sustentação", "H. Tavares", "H. Tavares", ["M. Fagundes", "M. Thomaz", "M. Grilo"]),

    ("Sys LLC", "OTH", "Projeto", "C. Sapateiro", "C. Sapateiro", ["D. Gonzaga"]),
    ("Bosch", "OTH", "Projeto", "C. Sapateiro", "P. Vilaça", ["D. Gonzaga"]),
    ("Nubank", "BFSI", "Sustentação", "C. Sapateiro", "P. Vilaça", ["D. Gonzaga"]),
    ("Vórtx", "BFSI", "Sustentação", "C. Sapateiro", "P. Vilaça", ["D. Gonzaga"]),
    ("Fapes", "BFSI", "Sustentação", "C. Sapateiro", "P. Vilaça", ["K. Sueiro"]),
    ("FGV", "OTH", "Projeto", "C. Sapateiro", "P. Vilaça", ["K. Sueiro"]),
    ("Petros", "BFSI", "Sustentação", "C. Sapateiro", "P. Vilaça", ["K. Sueiro"]),
]

# Non-green starting status per client (pillar -> status). Everything else defaults to G.
STATUS_OVERRIDES = {
    "Eneva": {"faturamento": "R"},
    "Grupo CBO": {"contrato": "R", "faturamento": "R"},
    "FGV": {"escopo": "A"},
}

CRITERIOS_SEED = [
    ("prazo", "Projeto", "G", "On track", 1),
    ("prazo", "Projeto", "A", "Desvio recuperável", 2),
    ("prazo", "Projeto", "R", "Atraso crítico", 3),
    ("prazo", "Sustentação", "G", "Dentro do SLA", 4),
    ("prazo", "Sustentação", "A", "Risco financeiro", 5),
    ("prazo", "Sustentação", "R", "Operação abaixo do mínimo, prejuízo", 6),
    ("faturamento", "Todas", "G", "Sem impedimentos", 7),
    ("faturamento", "Todas", "A", "Atraso <10 dias", 8),
    ("faturamento", "Todas", "R", "Atraso >10 dias", 9),
    ("escopo", "Projeto, Sustentação", "G", "Sem mudanças", 10),
    ("escopo", "Projeto, Sustentação", "A", "Mudanças leves", 11),
    ("escopo", "Projeto, Sustentação", "R", "Mudanças severas, prejuízo", 12),
    ("escopo", "Alocação", "G", "Execução total", 13),
    ("escopo", "Alocação", "A", "≥80% da função", 14),
    ("escopo", "Alocação", "R", "Desvio grave", 15),
    ("rh", "Todas", "G", "Estável", 16),
    ("rh", "Todas", "A", "Ruídos contornáveis", 17),
    ("rh", "Todas", "R", "Impacto financeiro, perda crítica", 18),
    ("contrato", "Todas", "G", ">90 dias; saldo ok", 19),
    ("contrato", "Todas", "A", "≤90 dias; saldo limitado", 20),
    ("contrato", "Todas", "R", "≤30 dias; saldo insuficiente", 21),
]


def seed():
    init_db()
    conn = get_conn()

    ja_populado = conn.execute("SELECT COUNT(*) c FROM clientes").fetchone()["c"] > 0
    if ja_populado:
        print("Banco já populado, pulando seed.")
        conn.close()
        return

    pessoa_ids = {}
    for nome, papel in PESSOAS_SEED:
        cur = conn.execute("INSERT INTO pessoas (nome, papel) VALUES (?, ?) RETURNING id", (nome, papel))
        pessoa_ids[nome] = cur.fetchone()["id"]

    semana = current_week_monday()
    ts = now_iso()

    for nome, industry_code, tipo_linha, bu_director, am, dms in CLIENTES_SEED:
        cur = conn.execute(
            """INSERT INTO clientes (nome, industry_code, tipo_linha, bu_director_id, am_id)
               VALUES (?, ?, ?, ?, ?) RETURNING id""",
            (nome, industry_code, tipo_linha, pessoa_ids[bu_director], pessoa_ids[am]),
        )
        cliente_id = cur.fetchone()["id"]

        for dm_nome in dms:
            conn.execute(
                "INSERT INTO cliente_dms (cliente_id, dm_id) VALUES (?, ?)",
                (cliente_id, pessoa_ids[dm_nome]),
            )

        overrides = STATUS_OVERRIDES.get(nome, {})
        for pilar in PILARES:
            status = overrides.get(pilar, "G")
            conn.execute(
                """INSERT INTO status_history
                   (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cliente_id, pilar, status, semana, "Estado inicial", "Importação inicial", ts),
            )

            if status != "G":
                tipo = "problema" if status == "R" else "risco"
                severidade = "alta" if status == "R" else "media"
                conn.execute(
                    """INSERT INTO riscos_issues
                       (cliente_id, pilar, tipo, titulo, descricao, severidade, responsavel,
                        plano_mitigacao, data_alvo, status, criado_em, atualizado_em)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (cliente_id, pilar, tipo,
                     f"{pilar.capitalize()} fora do verde — estado inicial",
                     "Registro criado automaticamente na importação inicial. Detalhar causa raiz e plano de ação.",
                     severidade, am, "", None, "aberto", ts, ts),
                )

    for pilar, linha, status, descricao, ordem in CRITERIOS_SEED:
        conn.execute(
            "INSERT INTO criterios (pilar, linha, status, descricao, ordem) VALUES (?, ?, ?, ?, ?)",
            (pilar, linha, status, descricao, ordem),
        )

    conn.commit()
    conn.close()
    print(f"Seed concluído: {len(PESSOAS_SEED)} pessoas, {len(CLIENTES_SEED)} clientes, {len(CRITERIOS_SEED)} critérios.")


if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("Defina a variável de ambiente DATABASE_URL antes de rodar este script.")
        sys.exit(1)
    seed()
