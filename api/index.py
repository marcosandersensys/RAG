"""RAG Status — API de gestão executiva de clientes/contratos (Vercel deploy).

Frontend estático é servido diretamente pela Vercel (ver vercel.json); este
módulo só expõe as rotas /api/*. Banco: Postgres via DATABASE_URL.

Tudo em um único arquivo (sem `from db import ...`) porque o runtime Python
da Vercel não adiciona o diretório do próprio módulo ao sys.path, então um
`db.py` irmão dá ModuleNotFoundError em produção.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

DIGEST_EMAIL_TO = "marcos.andersen@sysmanager.com.br"
RESEND_API_URL = "https://api.resend.com/emails"

PILARES = ["prazo", "faturamento", "margem", "escopo", "rh", "csat", "contrato"]
PAPEIS = ("bu_director", "am", "dm", "admin")

SENHA_PADRAO = "SysManager@2026"
SESSAO_DIAS = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS pessoas (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    papel TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS senha_hash TEXT;
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS precisa_trocar_senha INTEGER NOT NULL DEFAULT 1;
ALTER TABLE pessoas ADD COLUMN IF NOT EXISTS acesso_full INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS idx_pessoas_email ON pessoas(email);

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

ALTER TABLE riscos_issues ADD COLUMN IF NOT EXISTS nota_fechamento TEXT;

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

CREATE TABLE IF NOT EXISTS sessoes (
    token TEXT PRIMARY KEY,
    pessoa_id INTEGER NOT NULL REFERENCES pessoas(id),
    criado_em TEXT NOT NULL,
    expira_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessoes_expira ON sessoes(expira_em);

CREATE TABLE IF NOT EXISTS auditoria (
    id SERIAL PRIMARY KEY,
    entidade TEXT NOT NULL,
    entidade_id INTEGER,
    acao TEXT NOT NULL,
    pessoa_id INTEGER REFERENCES pessoas(id),
    pessoa_nome TEXT NOT NULL,
    detalhes TEXT,
    criado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auditoria_criado_em ON auditoria(criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_entidade ON auditoria(entidade, entidade_id);
"""


class _ConnWrapper:
    """Shim so call sites written against sqlite3's `conn.execute(...)`
    convenience API work unchanged against psycopg2."""

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

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


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


def hoje_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


PILAR_LABELS = {
    "prazo": "Prazo",
    "faturamento": "Faturamento",
    "margem": "Margem",
    "escopo": "Escopo",
    "rh": "RH",
    "csat": "CSAT",
    "contrato": "Contrato",
}


# ---------- Senhas ----------

def _hash_senha(senha: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + h.hex()


def _verificar_senha(senha: str, senha_hash: Optional[str]) -> bool:
    if not senha_hash or ":" not in senha_hash:
        return False
    salt_hex, hash_hex = senha_hash.split(":", 1)
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(h.hex(), hash_hex)


def _validar_senha_forte(senha: str):
    if len(senha) < 10:
        raise HTTPException(400, "A senha deve ter pelo menos 10 caracteres.")
    if not re.search(r"[A-Z]", senha):
        raise HTTPException(400, "A senha deve conter ao menos uma letra maiúscula.")
    if not re.search(r"[a-z]", senha):
        raise HTTPException(400, "A senha deve conter ao menos uma letra minúscula.")
    if not re.search(r"\d", senha):
        raise HTTPException(400, "A senha deve conter ao menos um número.")
    if not re.search(r"[^A-Za-z0-9]", senha):
        raise HTTPException(400, "A senha deve conter ao menos um caractere especial.")


def get_current_pessoa(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Não autenticado")
    token = authorization[len("Bearer "):].strip()
    conn = get_conn()
    row = conn.execute(
        """SELECT p.id, p.nome, p.papel, p.email, p.precisa_trocar_senha, p.ativo, p.acesso_full
           FROM sessoes s JOIN pessoas p ON p.id = s.pessoa_id
           WHERE s.token=? AND s.expira_em > ?""",
        (token, now_iso()),
    ).fetchone()
    conn.close()
    if not row or not row["ativo"]:
        raise HTTPException(401, "Sessão inválida ou expirada")
    return dict(row)


def _tem_acesso_full(pessoa: dict) -> bool:
    return pessoa["papel"] == "admin" or bool(pessoa.get("acesso_full"))


def _require_admin(pessoa: dict):
    if not _tem_acesso_full(pessoa):
        raise HTTPException(403, "Acesso restrito ao administrador")


def _clientes_visiveis_ids(conn, pessoa: dict):
    """None => acesso total (admin ou acesso_full). Caso contrário, set de cliente_id permitidos."""
    if _tem_acesso_full(pessoa):
        return None
    ids = set()
    if pessoa["papel"] == "bu_director":
        rows = conn.execute("SELECT id FROM clientes WHERE bu_director_id=?", (pessoa["id"],)).fetchall()
        ids.update(r["id"] for r in rows)
    elif pessoa["papel"] == "am":
        rows = conn.execute("SELECT id FROM clientes WHERE am_id=?", (pessoa["id"],)).fetchall()
        ids.update(r["id"] for r in rows)
    elif pessoa["papel"] == "dm":
        rows = conn.execute("SELECT cliente_id FROM cliente_dms WHERE dm_id=?", (pessoa["id"],)).fetchall()
        ids.update(r["cliente_id"] for r in rows)
    return ids


def _garantir_acesso_cliente(conn, pessoa: dict, cliente_id: int):
    ids = _clientes_visiveis_ids(conn, pessoa)
    if ids is not None and cliente_id not in ids:
        raise HTTPException(403, "Sem acesso a este cliente")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="RAG Status", lifespan=lifespan)


# ---------- Pydantic models ----------

class ClienteIn(BaseModel):
    nome: str
    industry_code: str
    tipo_linha: str = "Projeto"
    bu_director_id: Optional[int] = None
    am_id: Optional[int] = None
    dm_ids: Optional[List[int]] = None


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    industry_code: Optional[str] = None
    tipo_linha: Optional[str] = None
    bu_director_id: Optional[int] = None
    am_id: Optional[int] = None
    dm_ids: Optional[List[int]] = None
    ativo: Optional[bool] = None


class PessoaIn(BaseModel):
    nome: str
    papel: str
    email: Optional[str] = None
    acesso_full: bool = False


class PessoaUpdate(BaseModel):
    nome: Optional[str] = None
    papel: Optional[str] = None
    ativo: Optional[bool] = None
    email: Optional[str] = None
    acesso_full: Optional[bool] = None


class RiscoIn(BaseModel):
    cliente_id: int
    pilar: str
    tipo: str = "risco"
    titulo: str
    descricao: Optional[str] = ""
    severidade: str = "media"
    responsavel: Optional[str] = ""
    plano_mitigacao: Optional[str] = ""
    data_alvo: Optional[str] = None
    status: str = "aberto"


class RiscoUpdate(BaseModel):
    tipo: Optional[str] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    severidade: Optional[str] = None
    responsavel: Optional[str] = None
    plano_mitigacao: Optional[str] = None
    data_alvo: Optional[str] = None
    status: Optional[str] = None
    nota_fechamento: Optional[str] = None


class StatusIn(BaseModel):
    cliente_id: int
    pilar: str
    status: str
    comentario: Optional[str] = ""
    semana: Optional[str] = None
    risco: Optional[RiscoIn] = None


class CriterioUpdate(BaseModel):
    descricao: Optional[str] = None
    linha: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    senha: str


class TrocarSenhaIn(BaseModel):
    senha_atual: str
    senha_nova: str


def _validate_pilar(pilar: str):
    if pilar not in PILARES:
        raise HTTPException(400, detail=f"Pilar inválido: {pilar}")


def _validate_papel(papel: str):
    if papel not in PAPEIS:
        raise HTTPException(400, detail=f"Papel inválido: {papel}")


def _pessoa_ref(conn, pessoa_id):
    if not pessoa_id:
        return None
    row = conn.execute("SELECT id, nome, papel FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
    return dict(row) if row else None


def _cliente_relacoes(conn, cliente_id: int) -> dict:
    c = conn.execute("SELECT bu_director_id, am_id FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    dms = conn.execute(
        """SELECT p.id, p.nome FROM cliente_dms cd
           JOIN pessoas p ON p.id = cd.dm_id WHERE cd.cliente_id=? ORDER BY p.nome""",
        (cliente_id,),
    ).fetchall()
    return {
        "bu_director": _pessoa_ref(conn, c["bu_director_id"]) if c else None,
        "am": _pessoa_ref(conn, c["am_id"]) if c else None,
        "dms": [dict(d) for d in dms],
    }


def _set_cliente_dms(conn, cliente_id: int, dm_ids: List[int]):
    conn.execute("DELETE FROM cliente_dms WHERE cliente_id=?", (cliente_id,))
    for dm_id in dm_ids:
        conn.execute(
            "INSERT INTO cliente_dms (cliente_id, dm_id) VALUES (?, ?)", (cliente_id, dm_id)
        )


def _current_status_map(conn, cliente_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT sh.pilar, sh.status, sh.atualizado_por, sh.atualizado_em, sh.comentario
        FROM status_history sh
        JOIN (
            SELECT cliente_id, pilar, MAX(atualizado_em) AS max_em
            FROM status_history
            WHERE cliente_id = ?
            GROUP BY cliente_id, pilar
        ) latest
        ON sh.cliente_id = ? AND sh.pilar = latest.pilar AND sh.atualizado_em = latest.max_em
        """,
        (cliente_id, cliente_id),
    ).fetchall()
    return {r["pilar"]: dict(r) for r in rows}


# ---------- Batch helpers (avoid N+1 queries when listing all clients) ----------

def _all_current_status(conn) -> dict:
    """{cliente_id: {pilar: {status, atualizado_por, atualizado_em, comentario}}} for every client."""
    rows = conn.execute(
        """
        SELECT sh.cliente_id, sh.pilar, sh.status, sh.atualizado_por, sh.atualizado_em, sh.comentario
        FROM status_history sh
        JOIN (
            SELECT cliente_id, pilar, MAX(atualizado_em) AS max_em
            FROM status_history
            GROUP BY cliente_id, pilar
        ) latest
        ON sh.cliente_id = latest.cliente_id AND sh.pilar = latest.pilar AND sh.atualizado_em = latest.max_em
        """
    ).fetchall()
    result = defaultdict(dict)
    for r in rows:
        result[r["cliente_id"]][r["pilar"]] = dict(r)
    return result


def _all_riscos_abertos_counts(conn) -> dict:
    """{cliente_id: count} of non-closed riscos/issues for every client."""
    rows = conn.execute(
        "SELECT cliente_id, COUNT(*) c FROM riscos_issues WHERE status != 'fechado' GROUP BY cliente_id"
    ).fetchall()
    return {r["cliente_id"]: r["c"] for r in rows}


def _all_dms(conn) -> dict:
    """{cliente_id: [{"id", "nome"}, ...]} for every client."""
    rows = conn.execute(
        """SELECT cd.cliente_id, p.id, p.nome FROM cliente_dms cd
           JOIN pessoas p ON p.id = cd.dm_id ORDER BY p.nome"""
    ).fetchall()
    result = defaultdict(list)
    for r in rows:
        result[r["cliente_id"]].append({"id": r["id"], "nome": r["nome"]})
    return result


# ---------- Auditoria ----------

def _diff_campos(antigo: dict, novos: dict) -> str:
    partes = [f"{k}: {antigo.get(k)} → {v}" for k, v in novos.items() if antigo.get(k) != v]
    return "; ".join(partes) if partes else "sem alterações de campo"


def _log_auditoria(conn, pessoa: dict, entidade: str, entidade_id: Optional[int], acao: str, detalhes: str = ""):
    conn.execute(
        """INSERT INTO auditoria (entidade, entidade_id, acao, pessoa_id, pessoa_nome, detalhes, criado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (entidade, entidade_id, acao, pessoa["id"], pessoa["nome"], detalhes, now_iso()),
    )


# ---------- Auth ----------

@app.post("/api/auth/login")
def login(payload: LoginIn):
    conn = get_conn()
    email = payload.email.strip().lower()
    row = conn.execute("SELECT * FROM pessoas WHERE email=?", (email,)).fetchone()
    if not row or not row["ativo"] or not _verificar_senha(payload.senha, row["senha_hash"]):
        conn.close()
        raise HTTPException(401, "Email ou senha inválidos")
    token = secrets.token_urlsafe(32)
    criado = now_iso()
    expira = (datetime.now() + timedelta(days=SESSAO_DIAS)).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO sessoes (token, pessoa_id, criado_em, expira_em) VALUES (?, ?, ?, ?)",
        (token, row["id"], criado, expira),
    )
    conn.commit()
    conn.close()
    return {
        "token": token,
        "pessoa": {
            "id": row["id"],
            "nome": row["nome"],
            "papel": row["papel"],
            "precisa_trocar_senha": bool(row["precisa_trocar_senha"]),
            "acesso_full": bool(row["acesso_full"]),
        },
    }


@app.get("/api/auth/me")
def auth_me(pessoa: dict = Depends(get_current_pessoa)):
    return {
        "id": pessoa["id"],
        "nome": pessoa["nome"],
        "papel": pessoa["papel"],
        "precisa_trocar_senha": bool(pessoa["precisa_trocar_senha"]),
        "acesso_full": bool(pessoa.get("acesso_full")),
    }


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):].strip()
        conn = get_conn()
        conn.execute("DELETE FROM sessoes WHERE token=?", (token,))
        conn.commit()
        conn.close()
    return {"ok": True}


@app.post("/api/auth/trocar-senha")
def trocar_senha(payload: TrocarSenhaIn, pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    row = conn.execute("SELECT senha_hash FROM pessoas WHERE id=?", (pessoa["id"],)).fetchone()
    if not row or not _verificar_senha(payload.senha_atual, row["senha_hash"]):
        conn.close()
        raise HTTPException(400, "Senha atual incorreta")
    _validar_senha_forte(payload.senha_nova)
    if _verificar_senha(payload.senha_nova, row["senha_hash"]):
        conn.close()
        raise HTTPException(400, "A nova senha deve ser diferente da atual")
    novo_hash = _hash_senha(payload.senha_nova)
    conn.execute(
        "UPDATE pessoas SET senha_hash=?, precisa_trocar_senha=0 WHERE id=?",
        (novo_hash, pessoa["id"]),
    )
    _log_auditoria(conn, pessoa, "pessoa", pessoa["id"], "trocar_senha", "Senha alterada pelo próprio usuário")
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/pessoas/{pessoa_id}/resetar-senha")
def resetar_senha(pessoa_id: int, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    conn = get_conn()
    alvo = conn.execute("SELECT id, nome FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
    if not alvo:
        conn.close()
        raise HTTPException(404, "Pessoa não encontrada")
    conn.execute(
        "UPDATE pessoas SET senha_hash=?, precisa_trocar_senha=1 WHERE id=?",
        (_hash_senha(SENHA_PADRAO), pessoa_id),
    )
    conn.execute("DELETE FROM sessoes WHERE pessoa_id=?", (pessoa_id,))
    _log_auditoria(conn, pessoa, "pessoa", pessoa_id, "resetar_senha", f"Senha de '{alvo['nome']}' resetada para o padrão")
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Clientes ----------

@app.get("/api/pilares")
def listar_pilares(pessoa: dict = Depends(get_current_pessoa)):
    return [{"key": p, "label": PILAR_LABELS[p]} for p in PILARES]


@app.get("/api/clientes")
def listar_clientes(pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    ids = _clientes_visiveis_ids(conn, pessoa)
    if ids is not None and not ids:
        conn.close()
        return []

    query = """
        SELECT c.id AS cliente_id, c.nome AS cliente_nome, c.industry_code, c.tipo_linha,
               bd.id AS bud_id, bd.nome AS bud_nome, bd.papel AS bud_papel,
               amp.id AS amp_id, amp.nome AS amp_nome, amp.papel AS amp_papel
        FROM clientes c
        LEFT JOIN pessoas bd ON bd.id = c.bu_director_id
        LEFT JOIN pessoas amp ON amp.id = c.am_id
        WHERE c.ativo = 1
    """
    params = []
    if ids is not None:
        query += " AND c.id = ANY(?)"
        params.append(list(ids))
    query += " ORDER BY c.nome"

    clientes = conn.execute(query, params).fetchall()

    status_por_cliente = _all_current_status(conn)
    riscos_por_cliente = _all_riscos_abertos_counts(conn)
    dms_por_cliente = _all_dms(conn)
    conn.close()

    resultado = []
    for c in clientes:
        status_map = status_por_cliente.get(c["cliente_id"], {})
        modificado = max(
            (v["atualizado_em"] for v in status_map.values()), default=None
        )
        resultado.append({
            "id": c["cliente_id"],
            "nome": c["cliente_nome"],
            "industry_code": c["industry_code"],
            "tipo_linha": c["tipo_linha"],
            "bu_director": {"id": c["bud_id"], "nome": c["bud_nome"], "papel": c["bud_papel"]} if c["bud_id"] else None,
            "am": {"id": c["amp_id"], "nome": c["amp_nome"], "papel": c["amp_papel"]} if c["amp_id"] else None,
            "dms": dms_por_cliente.get(c["cliente_id"], []),
            "modificado": modificado,
            "riscos_abertos": riscos_por_cliente.get(c["cliente_id"], 0),
            "pilares": {
                p: status_map.get(p, {}).get("status", "G") for p in PILARES
            },
        })
    return resultado


@app.get("/api/clientes/{cliente_id}")
def detalhe_cliente(cliente_id: int, pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    _garantir_acesso_cliente(conn, pessoa, cliente_id)
    c = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(404, "Cliente não encontrado")

    status_map = _current_status_map(conn, cliente_id)

    historico = conn.execute(
        """SELECT pilar, status, semana, comentario, atualizado_por, atualizado_em
           FROM status_history WHERE cliente_id=?
           ORDER BY atualizado_em DESC LIMIT 500""",
        (cliente_id,),
    ).fetchall()

    riscos = conn.execute(
        "SELECT * FROM riscos_issues WHERE cliente_id=? ORDER BY criado_em DESC",
        (cliente_id,),
    ).fetchall()
    relacoes = _cliente_relacoes(conn, cliente_id)
    conn.close()

    return {
        "id": c["id"],
        "nome": c["nome"],
        "industry_code": c["industry_code"],
        "tipo_linha": c["tipo_linha"],
        "bu_director": relacoes["bu_director"],
        "am": relacoes["am"],
        "dms": relacoes["dms"],
        "pilares": {p: status_map.get(p, {}).get("status", "G") for p in PILARES},
        "historico": [dict(h) for h in historico],
        "riscos": [dict(r) for r in riscos],
    }


@app.post("/api/clientes")
def criar_cliente(payload: ClienteIn, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO clientes (nome, industry_code, tipo_linha, bu_director_id, am_id)
           VALUES (?, ?, ?, ?, ?) RETURNING id""",
        (payload.nome, payload.industry_code, payload.tipo_linha,
         payload.bu_director_id, payload.am_id),
    )
    cliente_id = cur.fetchone()["id"]

    if payload.dm_ids:
        _set_cliente_dms(conn, cliente_id, payload.dm_ids)

    ts = now_iso()
    semana = current_week_monday()
    for pilar in PILARES:
        conn.execute(
            """INSERT INTO status_history
               (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
               VALUES (?, ?, 'G', ?, 'Cliente criado', ?, ?)""",
            (cliente_id, pilar, semana, pessoa["nome"], ts),
        )
    _log_auditoria(conn, pessoa, "cliente", cliente_id, "criar",
                   f"'{payload.nome}' criado (Industry: {payload.industry_code}, Tipo: {payload.tipo_linha})")
    conn.commit()
    conn.close()
    return {"id": cliente_id}


@app.put("/api/clientes/{cliente_id}")
def editar_cliente(cliente_id: int, payload: ClienteUpdate, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    conn = get_conn()
    c = conn.execute("SELECT * FROM clientes WHERE id=?", (cliente_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(404, "Cliente não encontrado")

    fields = payload.model_dump(exclude_unset=True, exclude={"dm_ids"})
    detalhes = _diff_campos(dict(c), fields)
    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [cliente_id]
        conn.execute(f"UPDATE clientes SET {set_clause} WHERE id=?", values)

    if payload.dm_ids is not None:
        _set_cliente_dms(conn, cliente_id, payload.dm_ids)
        detalhes += f"; dm_ids: {payload.dm_ids}"

    _log_auditoria(conn, pessoa, "cliente", cliente_id, "editar", f"'{c['nome']}': {detalhes}")
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Pessoas ----------

@app.get("/api/pessoas")
def listar_pessoas(papel: Optional[str] = None, ativo: Optional[bool] = None,
                    pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    campos = "id, nome, papel, ativo"
    if _tem_acesso_full(pessoa):
        campos += ", email, precisa_trocar_senha, acesso_full"
    query = f"SELECT {campos} FROM pessoas WHERE 1=1"
    params = []
    if papel:
        query += " AND papel = ?"
        params.append(papel)
    if ativo is not None:
        query += " AND ativo = ?"
        params.append(1 if ativo else 0)
    query += " ORDER BY nome"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/pessoas")
def criar_pessoa(payload: PessoaIn, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    _validate_papel(payload.papel)
    conn = get_conn()
    email = payload.email.strip().lower() if payload.email else None
    try:
        cur = conn.execute(
            """INSERT INTO pessoas (nome, papel, email, senha_hash, precisa_trocar_senha, acesso_full)
               VALUES (?, ?, ?, ?, 1, ?) RETURNING id""",
            (payload.nome, payload.papel, email, _hash_senha(SENHA_PADRAO), payload.acesso_full),
        )
        pessoa_id = cur.fetchone()["id"]
        _log_auditoria(conn, pessoa, "pessoa", pessoa_id, "criar", f"'{payload.nome}' criado(a) (papel: {payload.papel})")
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        conn.close()
        raise HTTPException(400, "Já existe uma pessoa cadastrada com este email")
    conn.close()
    return {"id": pessoa_id}


@app.put("/api/pessoas/{pessoa_id}")
def editar_pessoa(pessoa_id: int, payload: PessoaUpdate, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    if payload.papel is not None:
        _validate_papel(payload.papel)
    conn = get_conn()
    p = conn.execute("SELECT * FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
    if not p:
        conn.close()
        raise HTTPException(404, "Pessoa não encontrada")
    fields = payload.model_dump(exclude_unset=True)
    if "email" in fields and fields["email"]:
        fields["email"] = fields["email"].strip().lower()
    if fields:
        detalhes = _diff_campos(dict(p), fields)
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [pessoa_id]
        try:
            conn.execute(f"UPDATE pessoas SET {set_clause} WHERE id=?", values)
            _log_auditoria(conn, pessoa, "pessoa", pessoa_id, "editar", f"'{p['nome']}': {detalhes}")
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            conn.close()
            raise HTTPException(400, "Já existe uma pessoa cadastrada com este email")
    conn.close()
    return {"ok": True}


# ---------- Status ----------

@app.post("/api/status")
def registrar_status(payload: StatusIn, pessoa: dict = Depends(get_current_pessoa)):
    _validate_pilar(payload.pilar)
    if payload.status not in ("G", "A", "R"):
        raise HTTPException(400, "Status deve ser G, A ou R")

    conn = get_conn()
    _garantir_acesso_cliente(conn, pessoa, payload.cliente_id)
    cliente = conn.execute("SELECT id FROM clientes WHERE id=?", (payload.cliente_id,)).fetchone()
    if not cliente:
        conn.close()
        raise HTTPException(404, "Cliente não encontrado")

    if payload.status != "G":
        aberto = conn.execute(
            "SELECT COUNT(*) c FROM riscos_issues WHERE cliente_id=? AND pilar=? AND status!='fechado'",
            (payload.cliente_id, payload.pilar),
        ).fetchone()["c"]
        if aberto == 0:
            if not payload.risco:
                conn.close()
                raise HTTPException(
                    400,
                    detail={
                        "code": "RISK_REQUIRED",
                        "message": "Pilar não-verde exige um Risco ou Problema vinculado. "
                                   "Preencha os dados do risco/problema para prosseguir.",
                    },
                )
            ts = now_iso()
            conn.execute(
                """INSERT INTO riscos_issues
                   (cliente_id, pilar, tipo, titulo, descricao, severidade, responsavel,
                    plano_mitigacao, data_alvo, status, criado_em, atualizado_em)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'aberto', ?, ?)""",
                (payload.cliente_id, payload.pilar, payload.risco.tipo, payload.risco.titulo,
                 payload.risco.descricao, payload.risco.severidade, payload.risco.responsavel,
                 payload.risco.plano_mitigacao, payload.risco.data_alvo, ts, ts),
            )

    anterior = conn.execute(
        """SELECT status FROM status_history WHERE cliente_id=? AND pilar=?
           ORDER BY atualizado_em DESC LIMIT 1""",
        (payload.cliente_id, payload.pilar),
    ).fetchone()
    status_anterior = anterior["status"] if anterior else None

    semana = payload.semana or current_week_monday()
    ts = now_iso()
    conn.execute(
        """INSERT INTO status_history
           (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (payload.cliente_id, payload.pilar, payload.status, semana,
         payload.comentario, pessoa["nome"], ts),
    )
    pilar_label = PILAR_LABELS.get(payload.pilar, payload.pilar)
    if status_anterior and status_anterior != payload.status:
        detalhes = f"Pilar {pilar_label}: {status_anterior} → {payload.status}"
    else:
        detalhes = f"Pilar {pilar_label} definido como {payload.status}"
    if payload.comentario:
        detalhes += f" — {payload.comentario}"
    _log_auditoria(conn, pessoa, "status", payload.cliente_id, "editar", detalhes)
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Riscos & Issues ----------

@app.get("/api/riscos")
def listar_riscos(pilar: Optional[str] = None, status: Optional[str] = None,
                   severidade: Optional[str] = None, cliente_id: Optional[int] = None,
                   pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    ids = _clientes_visiveis_ids(conn, pessoa)
    if ids is not None and not ids:
        conn.close()
        return []

    query = """
        SELECT ri.*, c.nome AS cliente_nome
        FROM riscos_issues ri
        JOIN clientes c ON c.id = ri.cliente_id
        WHERE 1=1
    """
    params = []
    if ids is not None:
        query += " AND ri.cliente_id = ANY(?)"
        params.append(list(ids))
    if pilar:
        query += " AND ri.pilar = ?"
        params.append(pilar)
    if status:
        query += " AND ri.status = ?"
        params.append(status)
    if severidade:
        query += " AND ri.severidade = ?"
        params.append(severidade)
    if cliente_id:
        query += " AND ri.cliente_id = ?"
        params.append(cliente_id)
    query += """
        ORDER BY
            (ri.status != 'fechado' AND ri.data_alvo IS NOT NULL AND ri.data_alvo < ?) DESC,
            ri.criado_em DESC
    """
    params.append(hoje_str())

    rows = conn.execute(query, params).fetchall()
    conn.close()

    hoje = hoje_str()
    resultado = []
    for r in rows:
        d = dict(r)
        d["atrasado"] = bool(d["status"] != "fechado" and d["data_alvo"] and d["data_alvo"] < hoje)
        if d["criado_em"]:
            dias = (datetime.now() - datetime.fromisoformat(d["criado_em"])).days
            d["dias_aberto"] = max(dias, 0)
        else:
            d["dias_aberto"] = None
        resultado.append(d)
    return resultado


@app.post("/api/riscos")
def criar_risco(payload: RiscoIn, pessoa: dict = Depends(get_current_pessoa)):
    _validate_pilar(payload.pilar)
    conn = get_conn()
    _garantir_acesso_cliente(conn, pessoa, payload.cliente_id)
    cliente = conn.execute("SELECT id FROM clientes WHERE id=?", (payload.cliente_id,)).fetchone()
    if not cliente:
        conn.close()
        raise HTTPException(404, "Cliente não encontrado")
    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO riscos_issues
           (cliente_id, pilar, tipo, titulo, descricao, severidade, responsavel,
            plano_mitigacao, data_alvo, status, criado_em, atualizado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
        (payload.cliente_id, payload.pilar, payload.tipo, payload.titulo, payload.descricao,
         payload.severidade, payload.responsavel, payload.plano_mitigacao, payload.data_alvo,
         payload.status, ts, ts),
    )
    risco_id = cur.fetchone()["id"]
    _log_auditoria(conn, pessoa, "risco", risco_id, "criar",
                   f"'{payload.titulo}' (pilar {PILAR_LABELS.get(payload.pilar, payload.pilar)}, severidade {payload.severidade})")
    conn.commit()
    conn.close()
    return {"id": risco_id}


@app.put("/api/riscos/{risco_id}")
def editar_risco(risco_id: int, payload: RiscoUpdate, pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    r = conn.execute("SELECT * FROM riscos_issues WHERE id=?", (risco_id,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Risco/Problema não encontrado")
    _garantir_acesso_cliente(conn, pessoa, r["cliente_id"])

    fields = payload.model_dump(exclude_unset=True)
    vira_fechado = fields.get("status") == "fechado" and r["status"] != "fechado"
    if vira_fechado:
        nota = (fields.get("nota_fechamento") or r["nota_fechamento"] or "").strip()
        if not nota:
            conn.close()
            raise HTTPException(
                400,
                detail={
                    "code": "CLOSURE_NOTE_REQUIRED",
                    "message": "Informe uma nota de encerramento explicando a resolução antes de fechar.",
                },
            )
        fields["nota_fechamento"] = nota
    if fields:
        detalhes = _diff_campos(dict(r), fields)
        fields["atualizado_em"] = now_iso()
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [risco_id]
        conn.execute(f"UPDATE riscos_issues SET {set_clause} WHERE id=?", values)
        acao = "fechar" if vira_fechado else "editar"
        _log_auditoria(conn, pessoa, "risco", risco_id, acao, f"'{r['titulo']}': {detalhes}")
        conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Critérios ----------

@app.get("/api/criterios")
def listar_criterios(pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM criterios ORDER BY ordem").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.put("/api/criterios/{criterio_id}")
def editar_criterio(criterio_id: int, payload: CriterioUpdate, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    conn = get_conn()
    c = conn.execute("SELECT * FROM criterios WHERE id=?", (criterio_id,)).fetchone()
    if not c:
        conn.close()
        raise HTTPException(404, "Critério não encontrado")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        detalhes = _diff_campos(dict(c), fields)
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [criterio_id]
        conn.execute(f"UPDATE criterios SET {set_clause} WHERE id=?", values)
        _log_auditoria(conn, pessoa, "criterio", criterio_id, "editar",
                       f"[{c['pilar']}/{c['linha']}/{c['status']}]: {detalhes}")
        conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Auditoria ----------

@app.get("/api/auditoria")
def listar_auditoria(entidade: Optional[str] = None, busca: Optional[str] = None,
                      limit: int = 200, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    limit = min(max(limit, 1), 500)
    conn = get_conn()
    query = "SELECT * FROM auditoria WHERE 1=1"
    params = []
    if entidade:
        query += " AND entidade = ?"
        params.append(entidade)
    if busca:
        termo = f"%{busca}%"
        query += " AND (pessoa_nome ILIKE ? OR detalhes ILIKE ?)"
        params.extend([termo, termo])
    query += " ORDER BY criado_em DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Dashboard resumo ----------

@app.get("/api/dashboard/resumo")
def resumo(pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    ids = _clientes_visiveis_ids(conn, pessoa)
    if ids is not None and not ids:
        conn.close()
        return {
            "total_clientes": 0,
            "clientes_criticos": 0,
            "riscos_abertos": 0,
            "riscos_atrasados": 0,
            "contagem_por_pilar": {p: {"G": 0, "A": 0, "R": 0} for p in PILARES},
        }

    query = "SELECT id FROM clientes WHERE ativo=1"
    params = []
    if ids is not None:
        query += " AND id = ANY(?)"
        params.append(list(ids))
    clientes = conn.execute(query, params).fetchall()
    status_por_cliente = _all_current_status(conn)

    riscos_query = "SELECT COUNT(*) c FROM riscos_issues WHERE status != 'fechado'"
    riscos_params = []
    if ids is not None:
        riscos_query += " AND cliente_id = ANY(?)"
        riscos_params.append(list(ids))
    riscos_abertos = conn.execute(riscos_query, riscos_params).fetchone()["c"]

    atrasados_query = (
        "SELECT COUNT(*) c FROM riscos_issues WHERE status != 'fechado' "
        "AND data_alvo IS NOT NULL AND data_alvo < ?"
    )
    atrasados_params = [hoje_str()]
    if ids is not None:
        atrasados_query += " AND cliente_id = ANY(?)"
        atrasados_params.append(list(ids))
    riscos_atrasados = conn.execute(atrasados_query, atrasados_params).fetchone()["c"]
    conn.close()

    contagem = {p: {"G": 0, "A": 0, "R": 0} for p in PILARES}
    clientes_criticos = 0
    for c in clientes:
        status_map = status_por_cliente.get(c["id"], {})
        tem_r = False
        for p in PILARES:
            s = status_map.get(p, {}).get("status", "G")
            contagem[p][s] += 1
            if s == "R":
                tem_r = True
        if tem_r:
            clientes_criticos += 1

    return {
        "total_clientes": len(clientes),
        "clientes_criticos": clientes_criticos,
        "riscos_abertos": riscos_abertos,
        "riscos_atrasados": riscos_atrasados,
        "contagem_por_pilar": contagem,
    }


# ---------- Resumo diário por email (cron) ----------

def _enviar_email_resend(assunto: str, html: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise HTTPException(500, "RESEND_API_KEY não configurada")
    remetente = os.environ.get("RESEND_FROM_EMAIL", "RAG Status <onboarding@resend.dev>")
    payload = json.dumps({
        "from": remetente,
        "to": [DIGEST_EMAIL_TO],
        "subject": assunto,
        "html": html,
    }).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")
        raise HTTPException(502, f"Falha ao enviar email via Resend ({e.code}): {detalhe}")


def _linha_html(cols: List[str]) -> str:
    tds = "".join(f'<td style="padding:6px 10px;border-bottom:1px solid #E5E7EB;font-size:13px;">{c}</td>' for c in cols)
    return f"<tr>{tds}</tr>"


def _tabela_html(headers: List[str], linhas: List[List[str]]) -> str:
    ths = "".join(f'<th style="padding:6px 10px;text-align:left;background:#041830;color:#fff;font-size:12px;">{h}</th>' for h in headers)
    corpo = "".join(_linha_html(l) for l in linhas)
    return (
        f'<table style="border-collapse:collapse;width:100%;margin:8px 0 20px;">'
        f"<thead><tr>{ths}</tr></thead><tbody>{corpo}</tbody></table>"
    )


def _montar_resumo_diario(conn, desde: str, ate: str):
    eventos_status = conn.execute(
        """SELECT a.entidade_id AS cliente_id, a.pessoa_nome, a.detalhes, a.criado_em,
                  c.nome AS cliente_nome
           FROM auditoria a
           LEFT JOIN clientes c ON c.id = a.entidade_id
           WHERE a.entidade = 'status' AND a.criado_em >= ? AND a.criado_em < ?
           ORDER BY c.nome, a.criado_em""",
        (desde, ate),
    ).fetchall()

    eventos_riscos = conn.execute(
        """SELECT a.acao, a.pessoa_nome, a.detalhes, a.criado_em,
                  r.titulo, r.pilar, r.tipo, c.nome AS cliente_nome
           FROM auditoria a
           LEFT JOIN riscos_issues r ON r.id = a.entidade_id
           LEFT JOIN clientes c ON c.id = r.cliente_id
           WHERE a.entidade = 'risco' AND a.criado_em >= ? AND a.criado_em < ?
           ORDER BY a.criado_em""",
        (desde, ate),
    ).fetchall()

    eventos_outros = conn.execute(
        """SELECT entidade, acao, pessoa_nome, detalhes, criado_em
           FROM auditoria
           WHERE entidade IN ('cliente', 'pessoa', 'criterio')
             AND NOT (entidade = 'pessoa' AND acao IN ('trocar_senha', 'resetar_senha'))
             AND criado_em >= ? AND criado_em < ?
           ORDER BY criado_em""",
        (desde, ate),
    ).fetchall()

    acessos = conn.execute(
        """SELECT p.nome, p.papel, COUNT(*) c, MIN(s.criado_em) primeiro, MAX(s.criado_em) ultimo
           FROM sessoes s JOIN pessoas p ON p.id = s.pessoa_id
           WHERE s.criado_em >= ? AND s.criado_em < ?
           GROUP BY p.nome, p.papel
           ORDER BY c DESC, p.nome""",
        (desde, ate),
    ).fetchall()

    total_eventos = len(eventos_status) + len(eventos_riscos) + len(eventos_outros)
    data_ref = ate[:10]

    partes = [
        f'<div style="font-family:Arial,Helvetica,sans-serif;color:#111;max-width:720px;">',
        f'<div style="background:#041830;color:#fff;padding:16px 20px;border-radius:8px 8px 0 0;">'
        f'<h1 style="margin:0;font-size:18px;">RAG Status — Resumo executivo diário</h1>'
        f'<p style="margin:4px 0 0;font-size:13px;color:#B8C4D0;">Referente a {data_ref} · janela de 24h encerrada às 06:00 (Brasília)</p>'
        f"</div>",
        f'<div style="border:1px solid #E5E7EB;border-top:none;padding:16px 20px;border-radius:0 0 8px 8px;">',
    ]

    if total_eventos == 0:
        partes.append('<p style="font-size:14px;">Nenhuma alteração registrada no sistema nas últimas 24 horas.</p>')
    else:
        partes.append(
            f'<p style="font-size:14px;">'
            f"{len(eventos_status)} mudança(s) de status · {len(eventos_riscos)} evento(s) de risco/problema · "
            f"{len(eventos_outros)} alteração(ões) administrativa(s)</p>"
        )

    if eventos_status:
        partes.append('<h2 style="font-size:15px;margin:16px 0 4px;">Mudanças de status</h2>')
        partes.append(_tabela_html(
            ["Cliente", "Alteração", "Por", "Quando"],
            [[e["cliente_nome"] or f'#{e["cliente_id"]}', e["detalhes"], e["pessoa_nome"], e["criado_em"][:16].replace("T", " ")]
             for e in eventos_status],
        ))

    if eventos_riscos:
        partes.append('<h2 style="font-size:15px;margin:16px 0 4px;">Riscos & problemas</h2>')
        partes.append(_tabela_html(
            ["Cliente", "Ação", "Detalhes", "Por", "Quando"],
            [[e["cliente_nome"] or "—", e["acao"], e["detalhes"], e["pessoa_nome"], e["criado_em"][:16].replace("T", " ")]
             for e in eventos_riscos],
        ))

    if eventos_outros:
        partes.append('<h2 style="font-size:15px;margin:16px 0 4px;">Outras alterações administrativas</h2>')
        partes.append(_tabela_html(
            ["Área", "Ação", "Detalhes", "Por", "Quando"],
            [[e["entidade"], e["acao"], e["detalhes"], e["pessoa_nome"], e["criado_em"][:16].replace("T", " ")]
             for e in eventos_outros],
        ))

    partes.append('<h2 style="font-size:15px;margin:16px 0 4px;">Acessos por usuário</h2>')
    if acessos:
        partes.append(_tabela_html(
            ["Pessoa", "Papel", "Logins", "Primeiro acesso", "Último acesso"],
            [[a["nome"], a["papel"], str(a["c"]), a["primeiro"][:16].replace("T", " "), a["ultimo"][:16].replace("T", " ")]
             for a in acessos],
        ))
    else:
        partes.append('<p style="font-size:13px;color:#6B7280;">Nenhum login registrado nas últimas 24 horas.</p>')

    partes.append(
        '<p style="font-size:11px;color:#9CA3AF;margin-top:20px;">'
        "Email automático gerado pelo RAG Status. Não responda a este endereço.</p>"
    )
    partes.append("</div></div>")

    assunto = f"RAG Status — Resumo diário {data_ref}" + (" (sem alterações)" if total_eventos == 0 else "")
    return assunto, "".join(partes)


@app.get("/api/cron/resumo-diario")
def cron_resumo_diario(authorization: Optional[str] = Header(None)):
    cron_secret = os.environ.get("CRON_SECRET")
    if not cron_secret or authorization != f"Bearer {cron_secret}":
        raise HTTPException(401, "Não autorizado")

    ate_dt = datetime.now()
    desde_dt = ate_dt - timedelta(hours=24)
    ate = ate_dt.isoformat(timespec="seconds")
    desde = desde_dt.isoformat(timespec="seconds")

    conn = get_conn()
    assunto, html = _montar_resumo_diario(conn, desde, ate)
    conn.close()

    _enviar_email_resend(assunto, html)
    return {"ok": True, "desde": desde, "ate": ate}
