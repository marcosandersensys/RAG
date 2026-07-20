# RAG Status — Gestão Executiva de Clientes/Contratos

Aplicação para acompanhamento semanal do status RAG (Green/Amber/Red) dos clientes/contratos
por pilar (Prazo, Escopo, RH, Contrato, Faturamento), com Risco & Problema obrigatoriamente
vinculado sempre que um pilar não estiver verde, hierarquia BU Director → AM → DM e visual
alinhado ao SysManager Design System v2.

## Stack

- **Backend local (dev)**: FastAPI + SQLite (`backend/app.py`, `backend/db.py`), sem ORM.
- **Backend produção (Vercel)**: FastAPI + Postgres/Neon (`api/index.py`, arquivo único — ver
  nota abaixo), deploy serverless.
- **Frontend**: HTML/CSS/JS puro (`frontend/`), servido separadamente do backend em produção.
  Visual usa os tokens do SysManager Design System v2 (Sora/Montserrat, paleta azul/magenta/roxo,
  tabelas no padrão canônico `#041830`). Exportação Excel via SheetJS (CDN); PDF via impressão do
  navegador.
- Sem autenticação por enquanto — cada atualização de status seleciona uma Pessoa cadastrada.

## Como rodar

Dependências (uma vez):

```bash
python3 -m pip install fastapi uvicorn
```

Popular o banco (primeira vez apenas — não sobrescreve se já houver dados):

```bash
cd rag-status/backend
python3 seed.py
```

Subir o servidor:

```bash
python3 -m uvicorn app:app --reload --port 8766 --app-dir rag-status/backend
```

Acessar em [http://localhost:8766](http://localhost:8766).

Também há uma entrada `rag-status` em `.claude/launch.json` para abrir direto pelo Browser pane
do Claude Code (mesmo padrão do `dre-dashboard`). Observação: o launcher interno do Browser pane
pode não conseguir importar os pacotes `pip` do usuário (sandbox) — nesse caso, suba o servidor
manualmente com o comando acima e abra a URL como página externa.

## Estrutura

```
rag-status/
  backend/           # versão LOCAL (SQLite) — uso em dev, não é o que roda na Vercel
    app.py
    db.py
    seed.py
    rag_status.db    # criado em runtime (não versionar)
  api/
    index.py         # versão PRODUÇÃO (Postgres) — entrypoint da Vercel, arquivo único
  scripts/
    seed.py          # popula o Postgres de produção (roda contra DATABASE_URL do Neon)
  frontend/
    index.html        # Painel · Riscos & Problemas · Organização · Critérios · Admin
    app.js
    styles.css
  vercel.json
  requirements.txt
```

## Deploy na Vercel (produção)

A Vercel roda funções serverless — sem disco persistente — então `api/index.py` usa Postgres
(Neon) via a variável de ambiente `DATABASE_URL`, em vez do SQLite do `backend/`.

**Passo único que só o dono da conta Vercel pode fazer**: no dashboard do projeto `rag-status`
na Vercel → aba **Storage** → **Connect Database** → escolher **Neon** (free tier). Isso injeta
`DATABASE_URL` automaticamente. Sem essa variável, toda rota `/api/*` retorna 500 (o frontend
estático continua funcionando normalmente — só a API depende do banco).

Depois de conectar o Neon, popule o banco uma vez:

```bash
DATABASE_URL="postgres://...string-do-neon...?sslmode=require" python3 scripts/seed.py
```

**Nota de packaging**: `api/index.py` é um arquivo único (sem `from db import ...`) porque o
runtime Python da Vercel não adiciona o diretório do próprio módulo ao `sys.path` — um `db.py`
irmão dá `ModuleNotFoundError` em produção mesmo funcionando localmente. Se for evoluir o backend
de produção, mantenha tudo em `api/index.py` (ou reintroduza um módulo irmão só depois de
confirmar que o runtime da Vercel resolve o import).

## Modelo de dados

- **pessoas**: BU Director / AM (Account Manager) / DM (Delivery Manager). Um BU Director pode
  atuar como AM diretamente em alguns clientes (ex: H. Tavares em Anatel/Petrobras).
- **clientes**: cada um tem um BU Director, um AM, e um ou mais DMs (`cliente_dms`, muitos-para-
  muitos — ex: Petrobras tem 3 DMs simultâneos).
- A aba **Organização** deriva as duas visões (Por Cliente / Por Pessoa) a partir desses vínculos
  — não há dado duplicado, evitando inconsistência entre as duas visualizações.

## Regras de negócio

- **Risco/Problema obrigatório**: ao mover um pilar para Âmbar ou Vermelho, a API exige que
  exista pelo menos um Risco/Problema em aberto vinculado àquele cliente+pilar. Se não houver,
  retorna `400 {"code": "RISK_REQUIRED"}` e o frontend abre o formulário de risco no mesmo modal.
- **Histórico semanal**: cada atualização de status vira uma linha em `status_history` com a
  segunda-feira da semana corrente. O "status atual" exibido no painel é sempre a última
  atualização por cliente+pilar — o histórico completo fica disponível no detalhe do cliente.
- **Critérios**: a tabela de critérios (macro, por pilar/linha) é editável diretamente na aba
  "Critérios" — clique numa célula de descrição para editar e salvar.
- **Admin**: cadastro de Pessoas (nome, papel, ativo/inativo) e Clientes (industry code, tipo de
  linha, BU Director, AM, DM(s)) — é aqui que se editam os vínculos organizacionais.

## Exportação

- **Excel**: botão "Exportar Excel" no Painel e em Riscos & Problemas — gera `.xlsx` client-side
  via SheetJS, sem round-trip ao backend.
- **PDF**: botão "Exportar PDF" no Painel — monta um relatório limpo (agrupado por BU Director)
  numa view oculta e aciona a impressão do navegador; o usuário escolhe "Salvar como PDF" no
  diálogo do sistema.

## Próximos passos sugeridos

- Autenticação por usuário/pessoa.
- Notificação/lembrete semanal para os Diretores de BU atualizarem o status.
- Exportação PDF nativa (sem depender do diálogo de impressão) se o layout precisar de mais
  controle.
