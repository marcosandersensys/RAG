"""One-off: grant acesso_full (full Admin module access) to the 3 BU
Directors, without touching their `papel` (which must stay 'bu_director'
so their BU sections keep rendering in Painel/Organização/PDF export).

Logs a 'pessoa/editar' entry per person to the auditoria table.

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/grant_acesso_full.py
"""
import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

NOMES = ["H. Tavares", "C. Sapateiro", "M. Albuquerque"]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    ts = now_iso()
    atualizados = []
    for nome in NOMES:
        cur.execute("SELECT id, papel, acesso_full FROM pessoas WHERE nome=%s", (nome,))
        row = cur.fetchone()
        if not row:
            print(f"AVISO — pessoa não encontrada: {nome!r}")
            continue
        if row["acesso_full"]:
            print(f"{nome}: já tinha acesso_full=1, pulando.")
            continue
        cur.execute("UPDATE pessoas SET acesso_full=1 WHERE id=%s", (row["id"],))
        cur.execute(
            """INSERT INTO auditoria (entidade, entidade_id, acao, pessoa_id, pessoa_nome, detalhes, criado_em)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                "pessoa", row["id"], "editar", None, "Sistema (script grant_acesso_full)",
                f"'{nome}': acesso_full: 0 → 1 (mantém papel={row['papel']})",
                ts,
            ),
        )
        atualizados.append(nome)

    conn.commit()
    cur.close()
    conn.close()

    print(f"acesso_full concedido a: {atualizados or 'ninguém (todos já tinham ou não encontrados)'}")


if __name__ == "__main__":
    main()
