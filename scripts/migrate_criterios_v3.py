"""One-off migration: add 'Receita' pillar to the criterios reference table
and fully renumber `ordem` so the table renders grouped by the new 4
categories: Financeiro (Faturamento, Receita, Margem), Execução/Entrega
(Prazo, Escopo), Pessoas (RH), Relacionamento & Contrato (CSAT, Contrato).

Idempotent — safe to run more than once (skips inserting Receita if it
already exists; renumbering is always recomputed and reapplied).

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/migrate_criterios_v3.py
"""
import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

# New grouped pillar order (must mirror PILARES in api/index.py)
PILARES_ORDEM = ["faturamento", "receita", "margem", "prazo", "escopo", "rh", "csat", "contrato"]

STATUS_RANK = {"G": 0, "A": 1, "R": 2}

RECEITA = [
    ("receita", "Todas", "G", "Receita realizada >= meta/orçado da conta"),
    ("receita", "Todas", "A", "Receita 5-15% abaixo do orçado, sem tendência de queda"),
    ("receita", "Todas", "R", "Receita >15% abaixo do orçado, ou queda em 2+ meses consecutivos"),
]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) c FROM criterios WHERE pilar='receita'")
    receita_inserida = 0
    if cur.fetchone()["c"] > 0:
        print("receita: já existe, pulando inserção.")
    else:
        for pilar, linha, status, descricao in RECEITA:
            cur.execute(
                "INSERT INTO criterios (pilar, linha, status, descricao, ordem) VALUES (%s, %s, %s, %s, 0)",
                (pilar, linha, status, descricao),
            )
        receita_inserida = len(RECEITA)
        print(f"receita: {receita_inserida} linha(s) inserida(s).")

    cur.execute("SELECT id, pilar, linha, status, ordem FROM criterios ORDER BY ordem")
    rows = cur.fetchall()

    # min current ordem per (pilar, linha) group — preserves relative order between
    # multiple linha variants of the same pilar (e.g. prazo/Projeto before
    # prazo/Sustentação; escopo/"Projeto, Sustentação" before escopo/Alocação)
    grupo_min_ordem = {}
    for r in rows:
        chave = (r["pilar"], r["linha"])
        grupo_min_ordem[chave] = min(grupo_min_ordem.get(chave, r["ordem"]), r["ordem"])

    def sort_key(r):
        pilar_idx = PILARES_ORDEM.index(r["pilar"]) if r["pilar"] in PILARES_ORDEM else len(PILARES_ORDEM)
        return (pilar_idx, grupo_min_ordem[(r["pilar"], r["linha"])], STATUS_RANK.get(r["status"], 99))

    rows_ordenadas = sorted(rows, key=sort_key)

    renumeradas = 0
    for nova_ordem, r in enumerate(rows_ordenadas, start=1):
        if r["ordem"] != nova_ordem:
            cur.execute("UPDATE criterios SET ordem=%s WHERE id=%s", (nova_ordem, r["id"]))
            renumeradas += 1

    cur.execute(
        """INSERT INTO auditoria (entidade, entidade_id, acao, pessoa_id, pessoa_nome, detalhes, criado_em)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            "criterio", None, "migrar", None, "Sistema (script migrate_criterios_v3)",
            f"Pilar 'receita' adicionado ({receita_inserida} linha(s) nova(s)); "
            f"ordem renumerada para 4 categorias ({renumeradas} linha(s) afetada(s)).",
            now_iso(),
        ),
    )

    conn.commit()

    cur.execute("SELECT pilar, linha, status, descricao, ordem FROM criterios ORDER BY ordem")
    print("\nEstado final:")
    for r in cur.fetchall():
        print(f"  [{r['ordem']:>2}] {r['pilar']:<12} {r['linha']:<22} {r['status']}  {r['descricao']}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
