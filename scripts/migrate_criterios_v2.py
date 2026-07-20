"""One-off migration: add 'Margem' and 'CSAT' pillars to the criterios
reference table, renumbering `ordem` so the table renders in the target
order: Prazo, Faturamento, Margem, Escopo, RH, CSAT, Contrato.

Idempotent — safe to run more than once.

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/migrate_criterios_v2.py
"""
import os
import sys

import psycopg2
import psycopg2.extras

# (pilar, linha, status) -> (descricao, ordem)
MARGEM = [
    ("margem", "Todas", "G", "Margem ≥ meta contratual", 10),
    ("margem", "Todas", "A", "Margem 5–10 p.p. abaixo da meta", 11),
    ("margem", "Todas", "R", "Margem >10 p.p. abaixo da meta, ou prejuízo direto", 12),
]

CSAT = [
    ("csat", "Todas", "G", "NPS/CSAT ≥ meta; sem escalada formal", 22),
    ("csat", "Todas", "A", "Reclamação pontual sem escalada a sponsor", 23),
    ("csat", "Todas", "R", "Escalada formal ao sponsor/C-level, ou risco de não-renovação verbalizado", 24),
]

# pilar -> new base ordem (rows within a pilar keep their relative G/A/R order)
SHIFTS = {
    "escopo": 13,
    "rh": 19,
    "contrato": 25,
}


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    for pilar, nova_base in SHIFTS.items():
        cur.execute("SELECT id, ordem FROM criterios WHERE pilar=%s ORDER BY ordem", (pilar,))
        rows = cur.fetchall()
        if not rows:
            print(f"AVISO — nenhuma linha encontrada para pilar={pilar!r}")
            continue
        if rows[0]["ordem"] == nova_base:
            print(f"{pilar}: já está na ordem alvo ({nova_base}), pulando.")
            continue
        for offset, row in enumerate(rows):
            cur.execute("UPDATE criterios SET ordem=%s WHERE id=%s", (nova_base + offset, row["id"]))
        print(f"{pilar}: {len(rows)} linha(s) renumerada(s) a partir de ordem={nova_base}.")

    for nome, linhas in (("margem", MARGEM), ("csat", CSAT)):
        cur.execute("SELECT COUNT(*) c FROM criterios WHERE pilar=%s", (nome,))
        if cur.fetchone()["c"] > 0:
            print(f"{nome}: já existe, pulando inserção.")
            continue
        for pilar, linha, status, descricao, ordem in linhas:
            cur.execute(
                "INSERT INTO criterios (pilar, linha, status, descricao, ordem) VALUES (%s, %s, %s, %s, %s)",
                (pilar, linha, status, descricao, ordem),
            )
        print(f"{nome}: {len(linhas)} linha(s) inserida(s).")

    conn.commit()
    cur.execute("SELECT pilar, linha, status, descricao, ordem FROM criterios ORDER BY ordem")
    print("\nEstado final:")
    for r in cur.fetchall():
        print(f"  [{r['ordem']:>2}] {r['pilar']:<12} {r['linha']:<22} {r['status']}  {r['descricao']}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
