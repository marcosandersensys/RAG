"""RAG Status — API de gestão executiva de clientes/contratos (Vercel deploy).

Frontend estático é servido diretamente pela Vercel (ver vercel.json); este
módulo só expõe as rotas /api/*. Banco: Postgres via DATABASE_URL.

Tudo em um único arquivo (sem `from db import ...`) porque o runtime Python
da Vercel não adiciona o diretório do próprio módulo ao sys.path, então um
`db.py` irmão dá ModuleNotFoundError em produção.
"""
import hashlib
import hmac
import os
import re
import secrets
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import psycopg2
import psycopg2.extras
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

PILARES = ["prazo", "escopo", "rh", "contrato", "faturamento"]
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


PILAR_LABELS = {
    "prazo": "Prazo",
    "escopo": "Escopo",
    "rh": "RH",
    "contrato": "Contrato",
    "faturamento": "Faturamento",
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
        """SELECT p.id, p.nome, p.papel, p.email, p.precisa_trocar_senha, p.ativo
           FROM sessoes s JOIN pessoas p ON p.id = s.pessoa_id
           WHERE s.token=? AND s.expira_em > ?""",
        (token, now_iso()),
    ).fetchone()
    conn.close()
    if not row or not row["ativo"]:
        raise HTTPException(401, "Sessão inválida ou expirada")
    return dict(row)


def _require_admin(pessoa: dict):
    if pessoa["papel"] != "admin":
        raise HTTPException(403, "Acesso restrito ao administrador")


def _clientes_visiveis_ids(conn, pessoa: dict):
    """None => acesso total (admin). Caso contrário, set de cliente_id permitidos."""
    if pessoa["papel"] == "admin":
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


class PessoaUpdate(BaseModel):
    nome: Optional[str] = None
    papel: Optional[str] = None
    ativo: Optional[bool] = None
    email: Optional[str] = None


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
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    severidade: Optional[str] = None
    responsavel: Optional[str] = None
    plano_mitigacao: Optional[str] = None
    data_alvo: Optional[str] = None
    status: Optional[str] = None


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
        },
    }


@app.get("/api/auth/me")
def auth_me(pessoa: dict = Depends(get_current_pessoa)):
    return {
        "id": pessoa["id"],
        "nome": pessoa["nome"],
        "papel": pessoa["papel"],
        "precisa_trocar_senha": bool(pessoa["precisa_trocar_senha"]),
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
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/pessoas/{pessoa_id}/resetar-senha")
def resetar_senha(pessoa_id: int, pessoa: dict = Depends(get_current_pessoa)):
    _require_admin(pessoa)
    conn = get_conn()
    alvo = conn.execute("SELECT id FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
    if not alvo:
        conn.close()
        raise HTTPException(404, "Pessoa não encontrada")
    conn.execute(
        "UPDATE pessoas SET senha_hash=?, precisa_trocar_senha=1 WHERE id=?",
        (_hash_senha(SENHA_PADRAO), pessoa_id),
    )
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
           ORDER BY atualizado_em DESC LIMIT 100""",
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
    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [cliente_id]
        conn.execute(f"UPDATE clientes SET {set_clause} WHERE id=?", values)

    if payload.dm_ids is not None:
        _set_cliente_dms(conn, cliente_id, payload.dm_ids)

    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Pessoas ----------

@app.get("/api/pessoas")
def listar_pessoas(papel: Optional[str] = None, ativo: Optional[bool] = None,
                    pessoa: dict = Depends(get_current_pessoa)):
    conn = get_conn()
    campos = "id, nome, papel, ativo"
    if pessoa["papel"] == "admin":
        campos += ", email, precisa_trocar_senha"
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
            """INSERT INTO pessoas (nome, papel, email, senha_hash, precisa_trocar_senha)
               VALUES (?, ?, ?, ?, 1) RETURNING id""",
            (payload.nome, payload.papel, email, _hash_senha(SENHA_PADRAO)),
        )
        pessoa_id = cur.fetchone()["id"]
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
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [pessoa_id]
        try:
            conn.execute(f"UPDATE pessoas SET {set_clause} WHERE id=?", values)
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

    semana = payload.semana or current_week_monday()
    ts = now_iso()
    conn.execute(
        """INSERT INTO status_history
           (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (payload.cliente_id, payload.pilar, payload.status, semana,
         payload.comentario, pessoa["nome"], ts),
    )
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
    query += " ORDER BY ri.criado_em DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
    if fields:
        fields["atualizado_em"] = now_iso()
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [risco_id]
        conn.execute(f"UPDATE riscos_issues SET {set_clause} WHERE id=?", values)
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
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [criterio_id]
        conn.execute(f"UPDATE criterios SET {set_clause} WHERE id=?", values)
        conn.commit()
    conn.close()
    return {"ok": True}


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
        "contagem_por_pilar": contagem,
    }
