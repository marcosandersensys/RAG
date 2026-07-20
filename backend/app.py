"""RAG Status — API de gestão executiva de clientes/contratos.

Rodar com: uvicorn app:app --reload --port 8766 --app-dir backend
(ou via a entrada 'rag-status' em .claude/launch.json)
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import get_conn, init_db, current_week_monday, now_iso, PILARES

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

PILAR_LABELS = {
    "prazo": "Prazo",
    "escopo": "Escopo",
    "rh": "RH",
    "contrato": "Contrato",
    "faturamento": "Faturamento",
}


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


class PessoaUpdate(BaseModel):
    nome: Optional[str] = None
    papel: Optional[str] = None
    ativo: Optional[bool] = None


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
    atualizado_por: str
    semana: Optional[str] = None
    risco: Optional[RiscoIn] = None


class CriterioUpdate(BaseModel):
    descricao: Optional[str] = None
    linha: Optional[str] = None


PAPEIS = ("bu_director", "am", "dm")


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


# ---------- Clientes ----------

@app.get("/api/pilares")
def listar_pilares():
    return [{"key": p, "label": PILAR_LABELS[p]} for p in PILARES]


@app.get("/api/clientes")
def listar_clientes():
    conn = get_conn()
    clientes = conn.execute(
        "SELECT * FROM clientes WHERE ativo = 1 ORDER BY nome"
    ).fetchall()

    resultado = []
    for c in clientes:
        status_map = _current_status_map(conn, c["id"])
        modificado = max(
            (v["atualizado_em"] for v in status_map.values()), default=None
        )
        riscos_abertos = conn.execute(
            "SELECT COUNT(*) c FROM riscos_issues WHERE cliente_id=? AND status!='fechado'",
            (c["id"],),
        ).fetchone()["c"]

        relacoes = _cliente_relacoes(conn, c["id"])
        resultado.append({
            "id": c["id"],
            "nome": c["nome"],
            "industry_code": c["industry_code"],
            "tipo_linha": c["tipo_linha"],
            "bu_director": relacoes["bu_director"],
            "am": relacoes["am"],
            "dms": relacoes["dms"],
            "modificado": modificado,
            "riscos_abertos": riscos_abertos,
            "pilares": {
                p: status_map.get(p, {}).get("status", "G") for p in PILARES
            },
        })
    conn.close()
    return resultado


@app.get("/api/clientes/{cliente_id}")
def detalhe_cliente(cliente_id: int):
    conn = get_conn()
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
def criar_cliente(payload: ClienteIn):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO clientes (nome, industry_code, tipo_linha, bu_director_id, am_id)
           VALUES (?, ?, ?, ?, ?)""",
        (payload.nome, payload.industry_code, payload.tipo_linha,
         payload.bu_director_id, payload.am_id),
    )
    cliente_id = cur.lastrowid

    if payload.dm_ids:
        _set_cliente_dms(conn, cliente_id, payload.dm_ids)

    am = _pessoa_ref(conn, payload.am_id)
    atualizado_por = am["nome"] if am else "Cadastro"
    ts = now_iso()
    semana = current_week_monday()
    for pilar in PILARES:
        conn.execute(
            """INSERT INTO status_history
               (cliente_id, pilar, status, semana, comentario, atualizado_por, atualizado_em)
               VALUES (?, ?, 'G', ?, 'Cliente criado', ?, ?)""",
            (cliente_id, pilar, semana, atualizado_por, ts),
        )
    conn.commit()
    conn.close()
    return {"id": cliente_id}


@app.put("/api/clientes/{cliente_id}")
def editar_cliente(cliente_id: int, payload: ClienteUpdate):
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
def listar_pessoas(papel: Optional[str] = None, ativo: Optional[bool] = None):
    conn = get_conn()
    query = "SELECT * FROM pessoas WHERE 1=1"
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
def criar_pessoa(payload: PessoaIn):
    _validate_papel(payload.papel)
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO pessoas (nome, papel) VALUES (?, ?)", (payload.nome, payload.papel)
    )
    conn.commit()
    pessoa_id = cur.lastrowid
    conn.close()
    return {"id": pessoa_id}


@app.put("/api/pessoas/{pessoa_id}")
def editar_pessoa(pessoa_id: int, payload: PessoaUpdate):
    if payload.papel is not None:
        _validate_papel(payload.papel)
    conn = get_conn()
    p = conn.execute("SELECT * FROM pessoas WHERE id=?", (pessoa_id,)).fetchone()
    if not p:
        conn.close()
        raise HTTPException(404, "Pessoa não encontrada")
    fields = payload.model_dump(exclude_unset=True)
    if fields:
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [pessoa_id]
        conn.execute(f"UPDATE pessoas SET {set_clause} WHERE id=?", values)
        conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Status ----------

@app.post("/api/status")
def registrar_status(payload: StatusIn):
    _validate_pilar(payload.pilar)
    if payload.status not in ("G", "A", "R"):
        raise HTTPException(400, "Status deve ser G, A ou R")

    conn = get_conn()
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
         payload.comentario, payload.atualizado_por, ts),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- Riscos & Issues ----------

@app.get("/api/riscos")
def listar_riscos(pilar: Optional[str] = None, status: Optional[str] = None,
                   severidade: Optional[str] = None, cliente_id: Optional[int] = None):
    conn = get_conn()
    query = """
        SELECT ri.*, c.nome AS cliente_nome
        FROM riscos_issues ri
        JOIN clientes c ON c.id = ri.cliente_id
        WHERE 1=1
    """
    params = []
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
def criar_risco(payload: RiscoIn):
    _validate_pilar(payload.pilar)
    conn = get_conn()
    cliente = conn.execute("SELECT id FROM clientes WHERE id=?", (payload.cliente_id,)).fetchone()
    if not cliente:
        conn.close()
        raise HTTPException(404, "Cliente não encontrado")
    ts = now_iso()
    cur = conn.execute(
        """INSERT INTO riscos_issues
           (cliente_id, pilar, tipo, titulo, descricao, severidade, responsavel,
            plano_mitigacao, data_alvo, status, criado_em, atualizado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (payload.cliente_id, payload.pilar, payload.tipo, payload.titulo, payload.descricao,
         payload.severidade, payload.responsavel, payload.plano_mitigacao, payload.data_alvo,
         payload.status, ts, ts),
    )
    conn.commit()
    risco_id = cur.lastrowid
    conn.close()
    return {"id": risco_id}


@app.put("/api/riscos/{risco_id}")
def editar_risco(risco_id: int, payload: RiscoUpdate):
    conn = get_conn()
    r = conn.execute("SELECT * FROM riscos_issues WHERE id=?", (risco_id,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Risco/Problema não encontrado")

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
def listar_criterios():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM criterios ORDER BY ordem").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.put("/api/criterios/{criterio_id}")
def editar_criterio(criterio_id: int, payload: CriterioUpdate):
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
def resumo():
    conn = get_conn()
    clientes = conn.execute("SELECT id FROM clientes WHERE ativo=1").fetchall()

    contagem = {p: {"G": 0, "A": 0, "R": 0} for p in PILARES}
    clientes_criticos = 0
    for c in clientes:
        status_map = _current_status_map(conn, c["id"])
        tem_r = False
        for p in PILARES:
            s = status_map.get(p, {}).get("status", "G")
            contagem[p][s] += 1
            if s == "R":
                tem_r = True
        if tem_r:
            clientes_criticos += 1

    riscos_abertos = conn.execute(
        "SELECT COUNT(*) c FROM riscos_issues WHERE status != 'fechado'"
    ).fetchone()["c"]

    conn.close()
    return {
        "total_clientes": len(clientes),
        "clientes_criticos": clientes_criticos,
        "riscos_abertos": riscos_abertos,
        "contagem_por_pilar": contagem,
    }


# ---------- Static frontend (mounted last so /api/* above takes priority) ----------
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
