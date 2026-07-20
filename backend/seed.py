"""Seeds the database with the real org chart (BU Directors -> AMs -> DMs -> clients)
and the macro criteria table. Safe to run once; skips if data exists.
"""
from db import get_conn, init_db, current_week_monday, now_iso, PILARES

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
    cur = conn.cursor()

    if cur.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] > 0:
        print("Banco já populado, pulando seed.")
        conn.close()
        return

    pessoa_ids = {}
    for nome, papel in PESSOAS_SEED:
        cur.execute("INSERT INTO pessoas (nome, papel) VALUES (?, ?)", (nome, papel))
        pessoa_ids[nome] = cur.lastrowid

    semana = current_week_monday()
    ts = now_iso()

    for nome, industry_code, tipo_linha, bu_director, am, dms in CLIENTES_SEED:
        cur.execute(
            """INSERT INTO clientes (nome, industry_code, tipo_linha, bu_director_id, am_id)
               VALUES (?, ?, ?, ?, ?)""",
            (nome, industry_code, tipo_linha, pessoa_ids[bu_director], pessoa_ids[am]),
        )
        cliente_id = cur.lastrowid

        for dm_nome in dms:
            cur.execute(
                "INSERT INTO cliente_dms (cliente_id, dm_id) VALUES (?, ?)",
                (cliente_id, pessoa_ids[dm_nome]),
            )

        overrides = STATUS_OVERRIDES.get(nome, {})
        for pilar in PILARES:
            status = overrides.get(pilar, "G")
            cur.execute(
                """INSERT INTO status_history
                   (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cliente_id, pilar, status, semana, "Estado inicial", "Importação inicial", ts),
            )

            if status != "G":
                tipo = "problema" if status == "R" else "risco"
                severidade = "alta" if status == "R" else "media"
                cur.execute(
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
        cur.execute(
            "INSERT INTO criterios (pilar, linha, status, descricao, ordem) VALUES (?, ?, ?, ?, ?)",
            (pilar, linha, status, descricao, ordem),
        )

    conn.commit()
    conn.close()
    print(f"Seed concluído: {len(PESSOAS_SEED)} pessoas, {len(CLIENTES_SEED)} clientes, {len(CRITERIOS_SEED)} critérios.")


if __name__ == "__main__":
    seed()
