"""One-off: seed today's row in metricas_diarias immediately, without waiting
for the 6am cron (and without re-sending the digest email, which the cron
endpoint would also trigger). Lets the WoW comparison start working exactly
7 days from today instead of from whenever the cron next fires.

Idempotent — safe to run more than once (upserts on date).

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/bootstrap_metrica_hoje.py
"""
import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

PILARES = ["faturamento", "receita", "margem", "prazo", "escopo", "rh", "csat", "contrato"]
PILAR_PESO = {"faturamento": 0.10, "receita": 0.15, "margem": 0.15, "prazo": 0.10,
              "escopo": 0.10, "rh": 0.10, "csat": 0.20, "contrato": 0.10}
PONTUACAO_STATUS = {"G": 100, "A": 50, "R": 0}
SCORE_CORTE_G = 85
SCORE_CORTE_A = 50


def rag_geral(status_map):
    score = sum(PILAR_PESO[p] * PONTUACAO_STATUS[status_map.get(p, "G")] for p in PILARES)
    if any(status_map.get(p, "G") == "R" for p in PILARES):
        return "R"
    if score >= SCORE_CORTE_G:
        return "G"
    if score >= SCORE_CORTE_A:
        return "A"
    return "R"


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute("SELECT id FROM clientes WHERE ativo=1")
    clientes = cur.fetchall()

    cur.execute(
        """SELECT DISTINCT ON (cliente_id, pilar) cliente_id, pilar, status
           FROM status_history ORDER BY cliente_id, pilar, atualizado_em DESC"""
    )
    status_por_cliente = {}
    for r in cur.fetchall():
        status_por_cliente.setdefault(r["cliente_id"], {})[r["pilar"]] = r["status"]

    clientes_rag_r = 0
    clientes_rag_a = 0
    for c in clientes:
        status_map = status_por_cliente.get(c["id"], {})
        rag = rag_geral(status_map)
        if rag == "R":
            clientes_rag_r += 1
        elif rag == "A":
            clientes_rag_a += 1

    cur.execute("SELECT COUNT(*) c FROM riscos_issues WHERE status != 'fechado'")
    riscos_abertos = cur.fetchone()["c"]

    hoje_str = datetime.now().strftime("%Y-%m-%d")
    cur.execute(
        """SELECT COUNT(*) c FROM riscos_issues WHERE status != 'fechado'
           AND data_alvo IS NOT NULL AND data_alvo < %s""",
        (hoje_str,),
    )
    riscos_atrasados = cur.fetchone()["c"]

    ts = now_iso()
    cur.execute(
        """INSERT INTO metricas_diarias (data, clientes_rag_r, clientes_rag_a, riscos_abertos, riscos_atrasados, criado_em)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (data) DO UPDATE SET
               clientes_rag_r = EXCLUDED.clientes_rag_r,
               clientes_rag_a = EXCLUDED.clientes_rag_a,
               riscos_abertos = EXCLUDED.riscos_abertos,
               riscos_atrasados = EXCLUDED.riscos_atrasados,
               criado_em = EXCLUDED.criado_em""",
        (hoje_str, clientes_rag_r, clientes_rag_a, riscos_abertos, riscos_atrasados, ts),
    )
    conn.commit()

    print(f"metricas_diarias[{hoje_str}] = rag_r={clientes_rag_r} rag_a={clientes_rag_a} "
          f"riscos_abertos={riscos_abertos} riscos_atrasados={riscos_atrasados}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
