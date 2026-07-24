"""DB-side mechanics for the recurring "atualizar DRE" process (see
rag-status/.claude/skills/atualizar-dre/SKILL.md for the full runbook —
this script only handles backup/scoped-delete/insert/drop-backup against
Postgres; the actual Power BI extraction is driven live by Claude via the
browser, since Microsoft SSO login can't be automated headlessly).

Tables: dre_resumo (escopo: 'total'|'licenciamento'|'servicos') and
dre_cliente (cliente_nome = valor do filtro "Cliente Agrupado" no Power BI).
Both keyed by competencia 'YYYY-MM', with valor_planejado/valor_realizado
columns (NULL where a month has no data yet).

Subcommands:
    backup                                        -> prints a suffix, e.g. dre_20260724_153000
    load --mes-inicio 2026-01 --mes-fim 2026-05 \\
         --cliente TODOS --input dados.json        -> deletes rows in scope, inserts new ones
    drop-backup --suffix dre_20260724_153000
    restore-backup --suffix dre_20260724_153000

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/dre_refresh.py backup
"""
import argparse
import json
import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

TABLES = ["dre_resumo", "dre_cliente"]


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def cmd_backup(conn, args):
    suffix = "dre_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    cur = conn.cursor()
    for t in TABLES:
        backup_name = f"{t}_backup_{suffix}"
        cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {t}")
        cur.execute(f"SELECT COUNT(*) c FROM {backup_name}")
        n = cur.fetchone()["c"]
        print(f"  {backup_name}: {n} linha(s) copiada(s)")
    conn.commit()
    print(f"\nBACKUP_SUFFIX={suffix}")


def cmd_drop_backup(conn, args):
    cur = conn.cursor()
    for t in TABLES:
        backup_name = f"{t}_backup_{args.suffix}"
        cur.execute(f"DROP TABLE IF EXISTS {backup_name}")
        print(f"  {backup_name}: removida")
    conn.commit()


def cmd_restore_backup(conn, args):
    cur = conn.cursor()
    for t in TABLES:
        backup_name = f"{t}_backup_{args.suffix}"
        cur.execute(f"SELECT to_regclass('{backup_name}') r")
        if cur.fetchone()["r"] is None:
            print(f"  {backup_name}: não encontrada, pulando.", file=sys.stderr)
            continue
        cur.execute(f"TRUNCATE {t}")
        cur.execute(f"INSERT INTO {t} SELECT * FROM {backup_name}")
        cur.execute(f"SELECT COUNT(*) c FROM {t}")
        n = cur.fetchone()["c"]
        print(f"  {t}: restaurada a partir de {backup_name} ({n} linha(s))")
    conn.commit()


def _competencias_no_escopo(mes_inicio, mes_fim):
    """['2026-01', '2026-02', ...] inclusive, mes_inicio/mes_fim = 'YYYY-MM'."""
    ini_y, ini_m = map(int, mes_inicio.split("-"))
    fim_y, fim_m = map(int, mes_fim.split("-"))
    out = []
    y, m = ini_y, ini_m
    while (y, m) <= (fim_y, fim_m):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def cmd_load(conn, args):
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    resumo_rows = data.get("resumo", [])
    cliente_rows = data.get("cliente", [])

    competencias = _competencias_no_escopo(args.mes_inicio, args.mes_fim)
    ts = now_iso()
    cur = conn.cursor()

    # --- dre_resumo: escopo dimension isn't client-specific, always full scope ---
    cur.execute(
        "DELETE FROM dre_resumo WHERE competencia = ANY(%s)",
        (competencias,),
    )
    deleted_resumo = cur.rowcount
    for r in resumo_rows:
        cur.execute(
            """INSERT INTO dre_resumo (escopo, linha_dre, competencia, valor_planejado, valor_realizado, atualizado_em)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (escopo, linha_dre, competencia) DO UPDATE SET
                   valor_planejado = EXCLUDED.valor_planejado,
                   valor_realizado = EXCLUDED.valor_realizado,
                   atualizado_em = EXCLUDED.atualizado_em""",
            (r["escopo"], r["linha_dre"], r["competencia"], r.get("valor_planejado"), r.get("valor_realizado"), ts),
        )

    # --- dre_cliente: respects --cliente scope (TODOS = every client in the payload) ---
    if args.cliente == "TODOS":
        cur.execute(
            "DELETE FROM dre_cliente WHERE competencia = ANY(%s)",
            (competencias,),
        )
    else:
        cur.execute(
            "DELETE FROM dre_cliente WHERE competencia = ANY(%s) AND cliente_nome = %s",
            (competencias, args.cliente),
        )
    deleted_cliente = cur.rowcount
    for r in cliente_rows:
        cur.execute(
            """INSERT INTO dre_cliente (cliente_nome, metrica, competencia, valor_planejado, valor_realizado, atualizado_em)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (cliente_nome, metrica, competencia) DO UPDATE SET
                   valor_planejado = EXCLUDED.valor_planejado,
                   valor_realizado = EXCLUDED.valor_realizado,
                   atualizado_em = EXCLUDED.atualizado_em""",
            (r["cliente_nome"], r["metrica"], r["competencia"], r.get("valor_planejado"), r.get("valor_realizado"), ts),
        )

    conn.commit()
    print(f"dre_resumo: {deleted_resumo} linha(s) removida(s) no escopo, {len(resumo_rows)} inserida(s)/atualizada(s)")
    print(f"dre_cliente: {deleted_cliente} linha(s) removida(s) no escopo, {len(cliente_rows)} inserida(s)/atualizada(s)")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("backup")

    p_load = sub.add_parser("load")
    p_load.add_argument("--mes-inicio", required=True, help="YYYY-MM")
    p_load.add_argument("--mes-fim", required=True, help="YYYY-MM")
    p_load.add_argument("--cliente", required=True, help="Nome do Cliente Agrupado ou 'TODOS'")
    p_load.add_argument("--input", required=True, help="Caminho do JSON com {resumo:[...], cliente:[...]}")

    p_drop = sub.add_parser("drop-backup")
    p_drop.add_argument("--suffix", required=True)

    p_restore = sub.add_parser("restore-backup")
    p_restore.add_argument("--suffix", required=True)

    args = parser.parse_args()
    conn = connect()

    {
        "backup": cmd_backup,
        "load": cmd_load,
        "drop-backup": cmd_drop_backup,
        "restore-backup": cmd_restore_backup,
    }[args.cmd](conn, args)

    conn.close()


if __name__ == "__main__":
    main()
