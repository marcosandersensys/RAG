"""One-off migration: add login credentials to existing pessoas + create the
admin user (M. Andersen). Run once against production after deploying the
auth-enabled api/index.py (which adds the email/senha_hash/precisa_trocar_senha
columns via its schema migration on first request).

Usage:
    DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/migrate_auth.py
"""
import hashlib
import os
import secrets
import sys

import psycopg2
import psycopg2.extras

SENHA_PADRAO = "SysManager@2026"

# nome (exatamente como já está cadastrado em `pessoas`) -> email SysManager
EMAILS = {
    "A. Duarte": "adriana.duarte@sysmanager.com.br",
    "A. Furtado": "andre.furtado@sysmanager.com.br",
    "A. Pollis": "andre.pollis@sysmanager.com.br",
    "C. Dana": "claudia.dana@sysmanager.com.br",
    "C. Sapateiro": "carlos.sapateiro@sysmanager.com.br",
    "D. Gonzaga": "daniel.gonzaga@sysmanager.com.br",
    "D. Leal": "danielle.leal@sysmanager.com.br",
    "D. Lopes": "daniel.lopes@sysmanager.com.br",
    "D. Mazoni": "dante.mazoni@sysmanager.com.br",
    "E. Balaciano": "ezequial.balaciano@sysmanager.com.br",
    "H. Tavares": "homero.tavares@sysmanager.com.br",
    "K. Sueiro": "keila.sueiro@sysmanager.com.br",
    "L. Nunes": "luciano.nunes@sysmanager.com.br",
    "L. Vieira": "leonardo.vieira@sysmanager.com.br",
    "M. Albuquerque": "marisa.albuquerque@sysmanager.com.br",
    "M. Fagundes": "marcelo.fagundes@sysmanager.com.br",
    "M. Grilo": "marco.grillo@sysmanager.com.br",
    "M. Thomaz": "marcelo.freitas@sysmanager.com.br",
    "P. Vilaça": "patricia.vilaca@sysmanager.com.br",
    "R. Pires": "rodrigo.pires@sysmanager.com.br",
    "T. Apolinário": "tiago.faria@sysmanager.com.br",
}

ADMIN_NOME = "M. Andersen"
ADMIN_EMAIL = "marcos.andersen@sysmanager.com.br"


def _hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + h.hex()


def main():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    senha_hash = _hash_senha(SENHA_PADRAO)
    atualizados, nao_encontrados = 0, []

    for nome, email in EMAILS.items():
        cur.execute(
            """UPDATE pessoas SET email=%s, senha_hash=%s, precisa_trocar_senha=1
               WHERE nome=%s RETURNING id""",
            (email.lower(), senha_hash, nome),
        )
        row = cur.fetchone()
        if row:
            atualizados += 1
        else:
            nao_encontrados.append(nome)

    cur.execute("SELECT id FROM pessoas WHERE email=%s", (ADMIN_EMAIL.lower(),))
    existente = cur.fetchone()
    if existente:
        cur.execute(
            """UPDATE pessoas SET nome=%s, papel='admin', ativo=1,
               senha_hash=%s, precisa_trocar_senha=1 WHERE email=%s""",
            (ADMIN_NOME, senha_hash, ADMIN_EMAIL.lower()),
        )
        admin_acao = "atualizado"
    else:
        cur.execute(
            """INSERT INTO pessoas (nome, papel, ativo, email, senha_hash, precisa_trocar_senha)
               VALUES (%s, 'admin', 1, %s, %s, 1)""",
            (ADMIN_NOME, ADMIN_EMAIL.lower(), senha_hash),
        )
        admin_acao = "criado"

    conn.commit()
    cur.close()
    conn.close()

    print(f"Pessoas atualizadas com email/senha: {atualizados}/{len(EMAILS)}")
    if nao_encontrados:
        print(f"AVISO — nomes não encontrados no banco: {nao_encontrados}")
    print(f"Admin (M. Andersen): {admin_acao}")
    print(f"Senha inicial para todos: {SENHA_PADRAO!r} (troca obrigatória no primeiro login)")


if __name__ == "__main__":
    main()
