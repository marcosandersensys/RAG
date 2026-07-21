"""One-off cleanup: delete every risco/problema and reset every client's
every pillar back to G, wiping status_history for a clean baseline.

Logs a single 'sistema/resetar' entry to the auditoria table so the
action is traceable in Admin > Auditoria.

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/reset_dados.py
"""
import os
import sys
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

PILARES = ["prazo", "faturamento", "margem", "escopo", "rh", "csat", "contrato"]


def current_week_monday():
    ref = datetime.now()
    monday = ref - timedelta(days=ref.weekday())
    return monday.strftime("%Y-%m-%d")


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) c FROM riscos_issues")
    total_riscos = cur.fetchone()["c"]
    cur.execute("DELETE FROM riscos_issues")

    cur.execute("SELECT COUNT(*) c FROM status_history")
    total_status = cur.fetchone()["c"]
    cur.execute("DELETE FROM status_history")

    cur.execute("SELECT id, nome FROM clientes ORDER BY nome")
    clientes = cur.fetchall()

    ts = now_iso()
    semana = current_week_monday()
    for c in clientes:
        for pilar in PILARES:
            cur.execute(
                """INSERT INTO status_history
                   (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
                   VALUES (%s, %s, 'G', %s, %s, %s, %s)""",
                (c["id"], pilar, semana, "Reset geral do sistema", "Sistema (reset)", ts),
            )

    cur.execute(
        """INSERT INTO auditoria (entidade, entidade_id, acao, pessoa_id, pessoa_nome, detalhes, criado_em)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            "sistema", None, "resetar", None, "Sistema (reset via script)",
            f"Limpeza geral: {total_riscos} risco(s)/problema(s) removido(s); "
            f"{total_status} registro(s) de histórico removido(s); "
            f"{len(clientes)} cliente(s) × {len(PILARES)} pilares redefinidos para G.",
            ts,
        ),
    )

    conn.commit()
    cur.close()
    conn.close()

    print(f"Riscos/Problemas removidos: {total_riscos}")
    print(f"Registros de histórico removidos: {total_status}")
    print(f"Clientes redefinidos para G em todos os pilares: {len(clientes)} × {len(PILARES)} pilares")


if __name__ == "__main__":
    main()
