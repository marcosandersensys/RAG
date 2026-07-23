# Documentação Técnica — RAG Status

**Sistema:** RAG Status — Gestão Executiva de Clientes/Contratos (SysManager)
**Repositório:** https://github.com/marcosandersensys/RAG
**Produção:** https://rag-status.vercel.app
**Última atualização deste documento:** 2026-07-23

---

## 1. Visão Geral

RAG Status é uma aplicação web para acompanhamento executivo semanal do status
RAG (Red/Amber/Green) dos clientes/contratos da SysManager, organizada por 8
pilares de análise agrupados em 4 categorias (Financeiro, Execução, Pessoas,
Relacionamento), com gestão obrigatória de Riscos/Problemas associados a
qualquer status não-verde, hierarquia organizacional (BU Director → AM → DM),
controle de acesso por papel, e trilha de auditoria de todas as alterações.

Além do status por pilar, o sistema calcula automaticamente — a cada leitura,
sem persistir o resultado — um **Score consolidado (0-100)** e um **RAG Geral**
por cliente, através de um modelo de pontuação ponderado (ver §4.9), e envia
diariamente um **resumo executivo por email** (Resend) com as alterações das
últimas 24h (ver §5.1).

É uma aplicação full-stack simples e auto-contida: backend Python (FastAPI)
como função serverless na Vercel, frontend estático (HTML/CSS/JS puro, sem
framework), banco Postgres gerenciado (Neon), sem ORM.

---

## 2. Stack Tecnológico

| Camada | Tecnologia | Versão/observação |
|---|---|---|
| Linguagem backend | Python | 3.9+ (runtime da Vercel para `@vercel/python`) |
| Framework backend | FastAPI | ver `requirements.txt` (sem pin de versão — última estável) |
| Driver de banco | psycopg2-binary | sem ORM; SQL puro |
| Banco de dados | PostgreSQL | gerenciado via **Neon** (serverless Postgres), região `sa-east-1` (São Paulo) |
| Frontend | HTML5 + CSS3 + JavaScript (ES2017+, vanilla) | sem framework (sem React/Vue/etc.), sem bundler/build step |
| Exportação Excel | SheetJS (`xlsx.full.min.js`) | via CDN (`cdnjs.cloudflare.com`), client-side |
| Exportação PDF | `window.print()` + CSS `@media print` | sem lib — usa o diálogo de impressão do navegador |
| Email transacional | Resend (API HTTP `https://api.resend.com/emails`) | chamado via stdlib `urllib.request` — **nenhum SDK/pacote pip novo** foi adicionado |
| Agendamento | Vercel Cron Jobs | 1 cron configurado em `vercel.json` (resumo diário, ver §5.1) |
| Hospedagem | Vercel | Functions (Python serverless) + Static Hosting, região `gru1` (São Paulo) |
| Controle de versão | Git / GitHub | repo `marcosandersensys/RAG`, branch `main` |
| CI/CD | Integração Git nativa da Vercel | todo push em `main` dispara build + deploy automático em produção |
| Fontes | Google Fonts — Sora (headings) + Montserrat (body) | SysManager Design System v2 |
| Autenticação | Sessão própria via token opaco (não é JWT) | tabela `sessoes` no Postgres, hash de senha PBKDF2-HMAC-SHA256 (stdlib `hashlib`, sem bcrypt/libs externas) |

### `requirements.txt`
```
fastapi
psycopg2-binary
```
Nenhuma outra dependência de terceiros — autenticação, hashing, geração de
token e **o envio de email do resumo diário** usam exclusivamente a biblioteca
padrão do Python (`hashlib`, `hmac`, `secrets`, `urllib.request`, `json`),
decisão deliberada para evitar problemas de empacotamento nativo no runtime
serverless da Vercel. Mesmo a integração com o Resend (serviço de terceiros)
foi implementada como uma chamada HTTP crua via `urllib`, em vez do SDK oficial
`resend` (que traria uma dependência nova).

---

## 3. Arquitetura

```
┌─────────────────────────┐        HTTPS        ┌──────────────────────────┐
│  Navegador (SPA estática) │ ───────────────────▶ │  Vercel Edge / Functions │
│  frontend/*.html,js,css  │ ◀─────────────────── │  api/index.py (FastAPI) │
└─────────────────────────┘                       └──────────┬───────────────┘
                                                              │ psycopg2 (DATABASE_URL)
                                                              ▼
                                                   ┌──────────────────────────┐
                                                   │  Neon Postgres (sa-east-1)│
                                                   └──────────────────────────┘
                            ┌──────────────────────────┐
Vercel Cron (09:00 UTC) ───▶│ GET /api/cron/resumo-diario│──▶ Resend API (HTTP) ──▶ email
                            └──────────────────────────┘
```

- **Sem servidor dedicado**: o backend roda como função serverless
  (`api/index.py`), instanciada sob demanda pela Vercel a cada requisição/cold
  start.
- **Sem estado em memória entre requisições**: cada chamada abre sua própria
  conexão Postgres (`get_conn()`) e a fecha ao final — não há connection
  pooling própria da aplicação (o Neon já opera com pooler `-pooler` na
  connection string).
- **Frontend 100% estático**: servido diretamente pela Vercel a partir de
  `frontend/`, sem servidor Node por trás. Toda comunicação com o backend é
  via `fetch()` para `/api/*`.
- **Roteamento** definido em `vercel.json`: `/api/*` → função Python,
  qualquer outra rota → arquivos estáticos de `frontend/`.
- **Agendamento (cron)**: a Vercel invoca `GET /api/cron/resumo-diario` uma
  vez ao dia, autenticando-se com um bearer token estático (`CRON_SECRET`) —
  ver §5.1.
- **Deploy**: a Vercel está conectada via Git ao repositório GitHub; qualquer
  push em `main` dispara build e deploy automático em produção (sem staging
  configurado).

### `vercel.json`
```json
{
  "builds": [
    { "src": "api/index.py", "use": "@vercel/python" },
    { "src": "frontend/**", "use": "@vercel/static" }
  ],
  "routes": [
    { "src": "/api/(.*)", "dest": "api/index.py" },
    { "src": "/(.*)", "dest": "/frontend/$1" }
  ],
  "regions": ["gru1"],
  "crons": [
    { "path": "/api/cron/resumo-diario", "schedule": "0 9 * * *" }
  ]
}
```
A região `gru1` (São Paulo) foi fixada deliberadamente para co-localizar a
função serverless com o banco Neon (`sa-east-1`) e reduzir latência de rede —
sem isso, medimos ~19s de carregamento do Painel (função em `iad1`/EUA
conversando com banco no Brasil); depois da correção, ~100-150ms.

O cron `0 9 * * *` roda todo dia às **09:00 UTC**, o que corresponde a
**06:00 no horário de Brasília** (UTC-3, sem horário de verão vigente no
Brasil) — o texto do próprio email gerado (`_montar_resumo_diario`) referencia
explicitamente essa janela ("janela de 24h encerrada às 06:00 (Brasília)"),
então os dois precisam ser mantidos em sincronia caso o schedule mude.
Schedules de Vercel Cron são sempre interpretados em UTC.

### Variáveis de ambiente (produção, configuradas na Vercel)
| Variável | Obrigatória? | Descrição |
|---|---|---|
| `DATABASE_URL` | Sim | Connection string do Neon Postgres (injetada pela integração Vercel↔Neon; obrigatória — sem ela toda rota `/api/*` retorna 500) |
| `CRON_SECRET` | Sim, para o cron | Token estático comparado ao header `Authorization: Bearer <token>` recebido em `GET /api/cron/resumo-diario`; sem ela (ou header divergente) a rota retorna `401 Não autorizado` |
| `RESEND_API_KEY` | Sim, para o email | Chave de API do Resend, usada como `Authorization: Bearer <key>` na chamada HTTP a `https://api.resend.com/emails`; sem ela `_enviar_email_resend` levanta `500 RESEND_API_KEY não configurada` |
| `RESEND_FROM_EMAIL` | Não | Remetente do email de resumo diário; default no código: `"RAG Status <onboarding@resend.dev>"` |

Não há outras variáveis de ambiente/secrets — sem chave de assinatura JWT,
sem API keys de terceiros além do Resend (usado exclusivamente pelo cron de
resumo diário).

---

## 4. Modelo de Dados

Banco: **PostgreSQL** (Neon). Schema aplicado de forma idempotente a cada
cold start da função (`init_db()` roda `CREATE TABLE IF NOT EXISTS` e
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` no lifespan do FastAPI) — não há
ferramenta de migration (Alembic etc.); evolução de schema é feita por essas
declarações idempotentes diretamente no código-fonte (`api/index.py`, string
`SCHEMA`). O Score consolidado, o RAG Geral e os alertas (§4.9) **não são
colunas de tabela** — são sempre recalculados em memória a partir do status
mais recente de cada pilar, a cada requisição.

### 4.1 `pessoas`
Pessoas do organograma (BU Directors, AMs, DMs) + administradores do sistema.

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `SERIAL PK` | |
| `nome` | `TEXT NOT NULL` | nome de exibição abreviado (ex: "H. Tavares") |
| `papel` | `TEXT NOT NULL` | `bu_director` \| `am` \| `dm` \| `admin` |
| `ativo` | `INTEGER NOT NULL DEFAULT 1` | flag booleana (0/1) |
| `email` | `TEXT` | login; índice único (`idx_pessoas_email`) |
| `senha_hash` | `TEXT` | `salt_hex:hash_hex` (ver §6) |
| `precisa_trocar_senha` | `INTEGER NOT NULL DEFAULT 1` | força troca de senha no próximo login |
| `acesso_full` | `INTEGER NOT NULL DEFAULT 0` | concede acesso total ao módulo Admin + visibilidade de todos os clientes, **sem** alterar `papel` (ver §6.3) |

### 4.2 `clientes`
| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `SERIAL PK` | |
| `nome` | `TEXT NOT NULL` | |
| `industry_code` | `TEXT NOT NULL` | ex: GOV, BFSI, O&G, OTH, E&U, CME |
| `tipo_linha` | `TEXT NOT NULL DEFAULT 'Projeto'` | `Projeto` \| `Sustentação` |
| `bu_director_id` | `INTEGER REFERENCES pessoas(id)` | |
| `am_id` | `INTEGER REFERENCES pessoas(id)` | Account Manager (único por cliente) |
| `ativo` | `INTEGER NOT NULL DEFAULT 1` | |

### 4.3 `cliente_dms` (associativa N:N)
Um cliente pode ter múltiplos Delivery Managers simultâneos.
| Coluna | Tipo |
|---|---|
| `cliente_id` | `INTEGER REFERENCES clientes(id)` |
| `dm_id` | `INTEGER REFERENCES pessoas(id)` |
| PK composta | `(cliente_id, dm_id)` |

### 4.4 `status_history`
Histórico completo de toda atualização de status por cliente+pilar (nunca é
sobrescrito — o "status atual" é sempre a linha de `atualizado_em` mais
recente por `cliente_id`+`pilar`).
| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `SERIAL PK` | |
| `cliente_id` | `INTEGER NOT NULL REFERENCES clientes(id)` | |
| `pilar` | `TEXT NOT NULL` | um dos 8 pilares (ver §4.9) |
| `status` | `TEXT NOT NULL` | `G` \| `A` \| `R` |
| `semana` | `TEXT NOT NULL` | segunda-feira da semana de referência (`YYYY-MM-DD`) |
| `comentario` | `TEXT` | |
| `atualizado_por` | `TEXT NOT NULL` | nome da pessoa autenticada (server-side, não confiável do cliente) |
| `atualizado_em` | `TEXT NOT NULL` | timestamp ISO |
| Índice | `idx_status_history_cliente_pilar` em `(cliente_id, pilar, atualizado_em)` | |

`registrar_status()` (rota `POST /api/status`) agora consulta o status
**anterior** daquele pilar (a última linha existente antes do insert) antes de
gravar o novo, para produzir uma mensagem de auditoria de transição limpa:
`"Pilar {label}: {anterior} → {novo}"` quando há mudança efetiva de valor, ou
`"Pilar {label} definido como {novo}"` quando é o primeiro registro do pilar
para aquele cliente (sem status anterior) ou o valor não mudou.

### 4.5 `riscos_issues`
| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `SERIAL PK` | |
| `cliente_id` | `INTEGER NOT NULL REFERENCES clientes(id)` | |
| `pilar` | `TEXT NOT NULL` | |
| `tipo` | `TEXT NOT NULL DEFAULT 'risco'` | `risco` \| `problema` |
| `titulo` | `TEXT NOT NULL` | |
| `descricao` | `TEXT` | |
| `severidade` | `TEXT NOT NULL DEFAULT 'media'` | `baixa` \| `media` \| `alta` \| `critica` |
| `responsavel` | `TEXT` | nome de uma `pessoa` ativa (selecionado via combo no frontend; coluna continua `TEXT` livre no banco) |
| `plano_mitigacao` | `TEXT` | |
| `data_alvo` | `TEXT` | data-alvo de resolução (`YYYY-MM-DD`) |
| `status` | `TEXT NOT NULL DEFAULT 'aberto'` | `aberto` \| `mitigando` \| `fechado` |
| `criado_em` / `atualizado_em` | `TEXT NOT NULL` | |
| `nota_fechamento` | `TEXT` | obrigatória ao transicionar para `fechado` (validado na API) |
| Índice | `idx_riscos_cliente_pilar` em `(cliente_id, pilar, status)` | |

### 4.6 `criterios`
Tabela de referência (régua G/A/R) por pilar/linha — editável via Admin.
| Coluna | Tipo |
|---|---|
| `id` | `SERIAL PK` |
| `pilar` | `TEXT NOT NULL` |
| `linha` | `TEXT NOT NULL` (ex: "Projeto", "Sustentação", "Todas", "Alocação") |
| `status` | `TEXT NOT NULL` (`G`/`A`/`R`) |
| `descricao` | `TEXT NOT NULL` |
| `ordem` | `INTEGER NOT NULL DEFAULT 0` (ordem de exibição) |

Estado após `scripts/migrate_criterios_v3.py` (ver §8): as 27 linhas
anteriores (9 combinações pilar/linha × 3 status G/A/R) ganharam +3 linhas
para o novo pilar `receita` (linha "Todas" × G/A/R), totalizando 30 linhas, e
todo o campo `ordem` foi renumerado para refletir as 4 categorias atuais
(Financeiro → Execução → Pessoas → Relacionamento), preservando a ordem
relativa entre as variantes de `linha` de um mesmo pilar.

### 4.7 `sessoes`
Sessões de autenticação (token opaco, não JWT).
| Coluna | Tipo |
|---|---|
| `token` | `TEXT PK` (gerado via `secrets.token_urlsafe(32)`) |
| `pessoa_id` | `INTEGER NOT NULL REFERENCES pessoas(id)` |
| `criado_em` / `expira_em` | `TEXT NOT NULL` (expiração: 7 dias — constante `SESSAO_DIAS`) |
| Índice | `idx_sessoes_expira` em `expira_em` |

Além de autenticação, `sessoes` agora também alimenta o **resumo diário por
email** (§5.1): `_montar_resumo_diario` faz `sessoes JOIN pessoas` para listar
quem logou nas últimas 24h (contagem de logins, primeiro/último acesso).

### 4.8 `auditoria`
Log de toda alteração feita no sistema (ver §6.4).
| Coluna | Tipo |
|---|---|
| `id` | `SERIAL PK` |
| `entidade` | `TEXT NOT NULL` — `cliente` \| `pessoa` \| `status` \| `risco` \| `criterio` \| `sistema` |
| `entidade_id` | `INTEGER` (nullable — null para eventos de sistema/scripts) |
| `acao` | `TEXT NOT NULL` — `criar` \| `editar` \| `fechar` \| `resetar_senha` \| `trocar_senha` \| `resetar` \| `migrar` |
| `pessoa_id` | `INTEGER REFERENCES pessoas(id)` (nullable — null para ações via script) |
| `pessoa_nome` | `TEXT NOT NULL` (preservado mesmo que a pessoa seja depois excluída/renomeada) |
| `detalhes` | `TEXT` — string legível com diff de campos alterados (`campo: antigo → novo`) |
| `criado_em` | `TEXT NOT NULL` |
| Índices | `idx_auditoria_criado_em` (DESC), `idx_auditoria_entidade` |

A ação `migrar` foi adicionada pelos scripts de migração de referência
(`migrate_criterios_v3.py`) para registrar alterações estruturais de
`criterios` feitas fora da aplicação. `auditoria` é também a fonte de dados
do resumo diário por email (§5.1): mudanças de status, eventos de
risco/problema e outras alterações administrativas do dia anterior são lidas
diretamente dessa tabela.

### Diagrama de relacionamentos (resumo)
```
pessoas ──┬─< clientes.bu_director_id
          ├─< clientes.am_id
          ├─< cliente_dms.dm_id >─┐
          ├─< sessoes.pessoa_id   │
          └─< auditoria.pessoa_id │
clientes ─┴────────────────────< cliente_dms.cliente_id
clientes ──< status_history.cliente_id
clientes ──< riscos_issues.cliente_id
```

### 4.9 Pilares, Categorias e Modelo de Pontuação (calculado, não persistido)

**8 pilares** (constante `PILARES` em `api/index.py`, ordem canônica — a
mesma ordem é usada em toda a UI via `PILAR_ORDEM` no frontend):

```python
PILARES = ["faturamento", "receita", "margem", "prazo", "escopo", "rh", "csat", "contrato"]
```

`receita` é um pilar novo, distinto de `faturamento`: **Receita** mede a
saúde comercial/de forecast da conta (receita realizada vs. meta/orçado),
enquanto **Faturamento** mede a saúde operacional/de caixa (emissão e
recebimento de faturas). Os dois têm réguas G/A/R e donos diferentes.

**4 categorias** agrupam os 8 pilares — constante `CATEGORIAS` em
`api/index.py`, espelhada no frontend como `PILAR_GRUPOS` em `app.js`:

| Categoria (`key`) | Label | Pilares |
|---|---|---|
| `financeiro` | **Financeiro** | Faturamento, Receita, Margem |
| `execucao` | **Execução** | Prazo, Escopo |
| `pessoas` | **Pessoas** | RH |
| `relacionamento` | **Relacionamento** | CSAT, Contrato |

O label da categoria `execucao` foi recentemente encurtado — o script
`migrate_criterios_v3.py` ainda descreve essa categoria em seu docstring como
"Execução/Entrega", mas o label vigente no código (`CATEGORIAS`/
`PILAR_GRUPOS`) é apenas **"Execução"**.

**Peso por pilar** (`PILAR_PESO`, soma = 1,00 / 100%):

| Pilar | Peso |
|---|---|
| Faturamento | 10% |
| Receita | 15% |
| Margem | 15% |
| Prazo | 10% |
| Escopo | 10% |
| RH | 10% |
| CSAT | 20% |
| Contrato | 10% |

**Dono por pilar** (`PILAR_DONO` — área responsável por aquele indicador):

| Pilar | Dono |
|---|---|
| Faturamento | Delivery \| FP&A |
| Receita | Delivery \| FP&A |
| Margem | Delivery \| FP&A |
| Prazo | Delivery |
| Escopo | Delivery |
| RH | Delivery \| RH |
| CSAT | Account |
| Contrato | Account |

**Pontuação por status** (`PONTUACAO_STATUS`): G = 100, A = 50, R = 0.

**`calcular_score(status_map)`** (função em `api/index.py`) — recebe o mapa
`{pilar: status}` de um cliente e devolve:

```python
score = sum(PILAR_PESO[p] * PONTUACAO_STATUS[status_map.get(p, "G")] for p in PILARES)
```

- **`score_consolidado`**: média ponderada 0-100 (`round(score)`).
- **`rag_geral`**: G/A/R consolidado, com regra de override —
  1. Se **qualquer** pilar estiver em `R`, `rag_geral = "R"` incondicionalmente
     (override automático, sem exceção), independentemente do score.
  2. Caso contrário: `score_consolidado >= SCORE_CORTE_G (85)` ⇒ `G`;
     `SCORE_CORTE_A (50) <= score < 85` ⇒ `A`; `score < 50` ⇒ `R`.
- **`alertas`**: lista de strings de alerta não-bloqueante, calculada por
  `_calcular_alertas(status_map)`:
  1. Se `receita == "R"` ⇒ `"Revisão obrigatória de Margem e Faturamento no próximo ciclo"`.
  2. Para cada categoria em `CATEGORIAS`: se **2 ou mais** pilares daquela
     categoria estiverem em `A` ⇒ `"Degradação sistêmica da categoria {label}"`
     (na prática só é atingível pelas categorias com 2+ pilares — Financeiro,
     Execução e Relacionamento; a categoria Pessoas tem um único pilar e nunca
     dispara essa regra).
  3. Se `rh == "R"` **e** `escopo` em `("A", "R")` ⇒
     `"Alerta cruzado: perda de pessoa-chave + desvio de execução"`.

`alertas` é informativo (exibido como `title`/tooltip nos badges do Painel e
no modal de detalhe do cliente) — não bloqueia nenhuma ação, ao contrário da
exigência de Risco/Problema vinculado a um status não-verde (§7.1).

**Endpoints que retornam `score_consolidado` / `rag_geral` / `alertas`**:
- `GET /api/clientes` — cada cliente da lista inclui os três campos (spread
  de `calcular_score(pilares_status)`).
- `GET /api/clientes/{id}` — idem, no payload de detalhe.
- `GET /api/dashboard/resumo` — não devolve os três campos diretamente, mas o
  contador `clientes_criticos` agora é calculado contando quantos clientes têm
  `calcular_score(pilares_status)["rag_geral"] == "R"` — ou seja, reflete tanto
  clientes com algum pilar vermelho quanto clientes sem pilar vermelho, mas com
  score consolidado abaixo de 50 (múltiplos pilares em `A`). O label da UI
  ("Clientes com pilar vermelho") é uma simplificação — o critério real é o
  RAG Geral, não apenas a presença literal de um pilar `R`.

---

## 5. API — Referência de Endpoints

Todas as rotas sob `/api/*`. Autenticação via header
`Authorization: Bearer <token>`, exceto `POST /api/auth/login` e
`GET /api/cron/resumo-diario` (que usa um bearer token diferente, `CRON_SECRET`
— ver §5.1). Payloads e respostas em JSON.

### Autenticação
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/auth/login` | — | `{email, senha}` → `{token, pessoa}` |
| GET | `/api/auth/me` | sessão | dados da pessoa autenticada |
| POST | `/api/auth/logout` | sessão (opcional) | invalida o token atual |
| POST | `/api/auth/trocar-senha` | sessão | `{senha_atual, senha_nova}` |

### Pessoas
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/pessoas` | sessão | lista pessoas (campos sensíveis só para acesso full) |
| POST | `/api/pessoas` | admin/acesso_full | cria pessoa (senha padrão, `precisa_trocar_senha=1`) |
| PUT | `/api/pessoas/{id}` | admin/acesso_full | edição parcial (`exclude_unset`) |
| POST | `/api/pessoas/{id}/resetar-senha` | admin/acesso_full | reseta senha ao padrão + revoga sessões ativas da pessoa |

### Clientes
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/clientes` | sessão | lista filtrada por RBAC (ver §6.2); cada item inclui `score_consolidado`, `rag_geral` e `alertas` (§4.9) |
| GET | `/api/clientes/{id}` | sessão + acesso ao cliente | detalhe + histórico + riscos + `score_consolidado`/`rag_geral`/`alertas` |
| POST | `/api/clientes` | admin/acesso_full | cria cliente + status inicial G em todos os 8 pilares |
| PUT | `/api/clientes/{id}` | admin/acesso_full | edição parcial + gestão de `dm_ids` |

### Status RAG
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/pilares` | sessão | lista os 8 pilares (`key`+`label`) |
| POST | `/api/status` | sessão + acesso ao cliente | registra novo status; exige risco se não-verde (ver §7.1); auditoria registra a transição `anterior → novo` |

### Riscos & Problemas
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/riscos` | sessão | filtros: `pilar`, `status`, `severidade`, `cliente_id`; retorna campos calculados `atrasado`/`dias_aberto` |
| POST | `/api/riscos` | sessão + acesso ao cliente | cria risco/problema avulso |
| PUT | `/api/riscos/{id}` | sessão + acesso ao cliente | edição; exige `nota_fechamento` ao transicionar para `fechado` |

### Critérios
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/criterios` | sessão | tabela de referência completa |
| PUT | `/api/criterios/{id}` | admin/acesso_full | edita descrição/linha |

### Auditoria e Dashboard
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/auditoria` | admin/acesso_full | filtros `entidade`, `busca`, `limit` (máx. 500) |
| GET | `/api/dashboard/resumo` | sessão | contagens agregadas (total clientes, críticos, riscos abertos/atrasados, contagem por pilar/status) — respeita RBAC; `clientes_criticos` usa `rag_geral` (§4.9) |

### Cron / Email
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/cron/resumo-diario` | `Authorization: Bearer <CRON_SECRET>` | monta e envia por email o resumo executivo das últimas 24h (ver §5.1) |

### 5.1 Resumo diário por email

`GET /api/cron/resumo-diario` é a rota disparada pelo Vercel Cron
(`vercel.json`, schedule `0 9 * * *` = 09:00 UTC = 06:00 Brasília, §3).

**Autenticação**: não usa sessão de usuário — compara o header
`Authorization` recebido literalmente contra `f"Bearer {CRON_SECRET}"`, onde
`CRON_SECRET` vem de `os.environ.get("CRON_SECRET")`. Se a variável não
estiver configurada, ou o header não bater exatamente, retorna
`401 Não autorizado`. Isso protege a rota de ser chamada por qualquer
requisição externa que não seja o próprio Vercel Cron (configurado para
enviar esse header automaticamente).

**Janela de dados**: `desde = agora - 24h`, `ate = agora` (hora do servidor,
UTC na função serverless).

**Montagem do email** (`_montar_resumo_diario(conn, desde, ate)`), a partir da
tabela `auditoria` e `sessoes`:
- **Mudanças de status**: linhas de `auditoria` com `entidade='status'` no
  período, juntadas com `clientes` pelo `entidade_id` — mostra cliente,
  alteração (texto já formatado como `"Pilar X: G → A"` ou similar, graças ao
  status anterior agora logado em `registrar_status`), autor e data/hora.
- **Riscos & problemas**: `auditoria` com `entidade='risco'`, juntada com
  `riscos_issues` (para pegar título/pilar/tipo) e `clientes`.
- **Outras alterações administrativas**: `auditoria` com
  `entidade IN ('cliente', 'pessoa', 'criterio')`, **excluindo**
  explicitamente `pessoa`/`trocar_senha` e `pessoa`/`resetar_senha` (para não
  poluir o resumo executivo com trocas de senha rotineiras).
- **Acessos por usuário**: `sessoes JOIN pessoas`, agrupado por
  pessoa/papel — contagem de logins no período, primeiro e último acesso.
- Se não houver nenhum evento no período, o corpo do email indica
  explicitamente "Nenhuma alteração registrada" e o assunto ganha o sufixo
  `" (sem alterações)"`.
- O HTML é montado manualmente (tabelas com estilos inline, cabeçalho `#041830`
  como no resto do produto) por `_tabela_html`/`_linha_html` — sem template
  engine.

**Envio** (`_enviar_email_resend`): faz `POST` para
`https://api.resend.com/emails` via `urllib.request` (stdlib, sem SDK),
com `Authorization: Bearer {RESEND_API_KEY}`, remetente
`RESEND_FROM_EMAIL` (default `"RAG Status <onboarding@resend.dev>"`), e
**destinatário fixo no código** — constante `DIGEST_EMAIL_TO =
"marcos.andersen@sysmanager.com.br"` (não configurável por env var; para
enviar a mais destinatários seria preciso editar `api/index.py`). Erros HTTP
do Resend são propagados como `502` com o corpo da resposta do Resend anexado
à mensagem de erro.

---

## 6. Autenticação e Segurança

### 6.1 Senhas
- Hash: **PBKDF2-HMAC-SHA256**, 200.000 iterações, salt aleatório de 16 bytes
  (`secrets.token_bytes`). Armazenado como `"{salt_hex}:{hash_hex}"` em
  `pessoas.senha_hash`. Comparação com `hmac.compare_digest` (constant-time).
- Sem dependências externas de criptografia (só `hashlib`/`hmac`/`secrets` da
  stdlib) — decisão para evitar problemas de build nativo no runtime
  serverless da Vercel.
- Política de senha forte (`_validar_senha_forte`): mínimo 10 caracteres,
  ao menos 1 maiúscula, 1 minúscula, 1 dígito, 1 caractere especial.
- Senha padrão para novas contas: `SysManager@2026`, com
  `precisa_trocar_senha=1` — o frontend força um modal não-dismissível de
  troca de senha antes de liberar o uso do app.

### 6.2 Sessões
- Token opaco (`secrets.token_urlsafe(32)`), **não é JWT** — sem payload
  auto-descritivo; validado por lookup na tabela `sessoes` a cada requisição
  (join com `pessoas`).
- Expiração: 7 dias (`SESSAO_DIAS`), checada em SQL (`expira_em > now()`).
- Sessões são explicitamente revogadas em: logout, reset de senha por admin.
- Sem refresh token — ao expirar, o usuário precisa logar novamente.

### 6.3 Controle de Acesso (RBAC)
Modelo de dois eixos, deliberadamente desacoplados:

1. **`papel`** (papel operacional): `bu_director` | `am` | `dm` | `admin`.
   Determina o escopo *padrão* de visibilidade de clientes e também alimenta
   o agrupamento visual "por BU Director" no Painel/Organização/PDF — **não
   pode ser usado como flag de permissão isolada**, pois qualquer pessoa cuja
   `papel` deixe de ser `bu_director` desaparece do agrupamento visual mesmo
   que `clientes.bu_director_id` ainda aponte para ela.
2. **`acesso_full`** (flag booleana independente): quando `true`, concede
   acesso total ao módulo Admin + visibilidade de todos os clientes,
   **sem** alterar o `papel` da pessoa. Usado para dar a BU Directors acesso
   equivalente ao de `admin` sem quebrar seu agrupamento como diretor.

Função central: `_tem_acesso_full(pessoa) = papel == "admin" OR acesso_full`.
Todo endpoint sensível usa `_require_admin()` (403 se `not _tem_acesso_full`)
e toda listagem de clientes usa `_clientes_visiveis_ids()`:

| Papel | Clientes visíveis |
|---|---|
| `admin` ou `acesso_full=1` | todos |
| `bu_director` | `clientes.bu_director_id == pessoa.id` |
| `am` | `clientes.am_id == pessoa.id` |
| `dm` | clientes onde existe linha em `cliente_dms` |

Enforcement é **sempre server-side** (a UI apenas reflete o que a API já
filtrou) — inclusive em mutações (`_garantir_acesso_cliente` valida acesso
antes de qualquer `POST`/`PUT` em status ou risco de um cliente específico).
Este modelo de dois eixos não teve mudanças de comportamento nesta revisão —
`_tem_acesso_full`, `_require_admin` e `_clientes_visiveis_ids` seguem
implementados exatamente como descrito acima.

Estado atual de produção: 1 `admin` (acesso total nativo, papel não ligado a
nenhuma BU), 3 `bu_director` com `acesso_full=1` (Homero Tavares, Carlos
Sapateiro, Marisa Albuquerque — acesso pleno ao Admin mantendo seu papel
operacional), 8 `am`, 10 `dm` (RBAC padrão).

### 6.4 Auditoria
Toda rota mutável (`criar_cliente`, `editar_cliente`, `criar_pessoa`,
`editar_pessoa`, `resetar_senha`, `trocar_senha`, `registrar_status`,
`criar_risco`, `editar_risco`, `editar_criterio`) grava uma linha em
`auditoria` via `_log_auditoria()`, incluindo um diff textual dos campos
alterados (`_diff_campos()`, formato `"campo: antigo → novo"`). Consultável
via `GET /api/auditoria` (só admin/acesso_full), com filtro por entidade e
busca textual em usuário/detalhes. Esta mesma tabela é a fonte de dados do
resumo diário por email (§5.1).

---

## 7. Frontend

### 7.1 Estrutura de arquivos
```
frontend/
  index.html   — shell da SPA: telas (login, painel, riscos, organização, admin) + modais
  app.js       — toda a lógica (fetch, renderização, RBAC de UI, exportação)
  styles.css   — design tokens + estilos
  favicon.svg  — ícone de aba do navegador (ver §7.6)
```
Sem bundler, sem transpilação, sem TypeScript — arquivos servidos como estão.

### 7.2 Padrão de arquitetura do frontend
- SPA "hash-free" baseada em `.view`/`.view.active` (troca de visibilidade via
  classe CSS, sem roteamento de URL).
- Estado global em um objeto `state` (clientes, pessoas, riscos, criterios,
  auditoria) e `session` (token + dados da pessoa autenticada, persistido em
  `localStorage`).
- Toda chamada à API passa por uma função `api()` central que injeta o header
  `Authorization`, trata `401` (limpa sessão + volta à tela de login) e
  normaliza erros.
- Renderização via template strings + `innerHTML` (sem Virtual DOM), com
  função `esc()` para escapar HTML em todo conteúdo dinâmico proveniente de
  dados (mitigação de XSS).
- Constantes de pilar (`PILAR_GRUPOS`, `PILAR_ORDEM`, `PILAR_LABELS`,
  `PILAR_LABELS_CURTO`, `PILAR_CATEGORIA`, `PILAR_PESO`, `PILAR_DONO`)
  espelham manualmente as equivalentes do backend (`CATEGORIAS`,
  `PILAR_PESO`, `PILAR_DONO` em `api/index.py`) — não há um endpoint que sirva
  esse "modelo" para o frontend consumir dinamicamente; qualquer mudança de
  pesos/donos/categorias precisa ser replicada nos dois arquivos.

### 7.3 Modelo de Pontuação e RAG Geral na UI

**Painel (`view-painel`, tabela principal)**:
- Cabeçalho em 2 linhas (`<thead>` com duas `<tr>`): a primeira linha agrupa
  os pilares por categoria (`th-categoria`, `colspan` = nº de pilares daquela
  categoria); a segunda lista cada pilar com seu rótulo abreviado
  (`PILAR_LABELS_CURTO`: FAT, REC, GM%, PRZ, ESC, RH, CSAT, CTR).
- Duas colunas novas antes dos pilares: **RAG Geral** (badge `.badge-geral`,
  estilo *outline* — contorno colorido, fundo branco, não clicável, distinto
  do badge `.badge-rag` sólido e clicável de cada pilar) e **Score**
  (`score_consolidado` numérico).
- Um `<colgroup>` com larguras fixas garante que as tabelas de todas as
  seções "por BU Director" fiquem alinhadas entre si (mesma largura de coluna
  em todas as seções, mesmo com contagens de linha diferentes).
- Botão global **"? Critérios"** na toolbar do Painel
  (`#btn-ver-criterios`) chama `abrirCriteriosReferencia()` sem argumento,
  abrindo o modal `modal-criterios-ref` com o conteúdo completo de
  Admin > Critérios: tabela de critérios G/A/R por pilar
  (`criteriosTabelaHtml()`), a tabela do Modelo de Pontuação
  (`modeloPontuacaoTabelaHtml()`) e o texto de regras de consolidação
  (`regrasConsolidacaoHtml()`).
- Botão **"?"** por pilar (no cabeçalho de cada coluna de pilar) chama
  `abrirCriteriosReferencia(pilar)`, abrindo o mesmo modal mas mostrando
  apenas os critérios daquele pilar específico.
- Botão **"?"** no cabeçalho "RAG Geral" chama `abrirRagGeralInfo()`, que
  reaproveita `modeloPontuacaoTabelaHtml()` + `regrasConsolidacaoHtml()` para
  explicar como o RAG Geral/Score são calculados.

**Admin > Critérios (`admin-criterios`)**:
- Mantém a tabela editável de critérios G/A/R por pilar/linha (inalterada).
- Nova tabela somente-leitura **"Modelo de Pontuação"**
  (`#tabela-modelo-pontuacao`), preenchida por `renderModeloPontuacao()` →
  `modeloPontuacaoLinhasHtml()`: uma linha por pilar com Categoria, Pilar,
  Peso (%), Pontuação (sempre 100 na linha de referência), Peso × Pontuação, e
  Dono (`PILAR_DONO`); mais uma linha de TOTAL (soma dos pesos = 100%).
- Abaixo da tabela, `regrasConsolidacaoHtml()` explica em texto: a ponderação
  por status (G=100%, A=50%, R=0%) e as regras de consolidação (override de
  R, cortes de score 85/50, e o aviso de que pesos/cortes são parametrizáveis
  no código-fonte).
- `renderModeloPontuacao()` é chamada em `mostrarApp()` (ou seja, já ao
  entrar na aplicação, antes mesmo do usuário abrir a aba Admin).

**Modal de detalhe do cliente (`modal-cliente`)**:
- Usa a classe `modal-wide` (max-width 900px, vs. 440px do modal padrão) para
  acomodar a linha do tempo por pilar com rótulos abreviados.
- Título do modal (`mc-titulo`) agora inclui um badge `.badge-geral` com o
  `rag_geral` do cliente, com tooltip listando os `alertas` daquele cliente.
- A linha do tempo por pilar (`renderClienteTimeline`) ganhou uma linha
  **"GERAL"** no topo, antes dos pilares individuais, mostrando o mesmo badge
  de RAG Geral do cabeçalho.
- Os rótulos de pilar na timeline e no resumo de pilares (`mc-pilares`) usam
  as mesmas abreviações do Painel (`PILAR_LABELS_CURTO`), com o nome completo
  disponível via `title`/tooltip.

### 7.4 Design System (SysManager Design System v2)
- Tipografia: **Sora** (headings) + **Montserrat** (body), via Google Fonts.
- Paleta: `--sys-blue:#1059AF`, `--sys-magenta:#FC429A`, `--sys-purple:#663B8A`,
  fundo `--bg-page:#F0F2F4` (nunca branco puro), semânticas
  `--success/--warning/--destructive/--info`.
- Padrão canônico de tabela: header `#041830` com texto branco, linhas
  zebradas (`#FFFFFF`/`#FAFBFC`), badges pill (`border-radius:20px`).
- Cards: `border-radius:16px`, sombra dupla (`--shadow-card`).
- Dois estilos de badge RAG coexistem deliberadamente: `.badge-rag` (círculo
  sólido colorido, clicável, usado por pilar) e `.badge-geral` (pílula com
  contorno colorido e fundo branco, não clicável, usado só para o RAG Geral
  consolidado do cliente) — a diferença visual reforça que o RAG Geral é
  derivado/somente-leitura, nunca editável diretamente.

### 7.5 Responsividade
- Breakpoint principal em `720px`.
- Header reflow (evita overflow horizontal da página inteira).
- Alvos de toque ampliados (~44pt) em botões/badges no breakpoint mobile.
- Primeira coluna de tabelas largas fixada (`position:sticky`) para rolagem
  horizontal sem perder o nome do cliente/pessoa de vista.

### 7.6 Favicon
`frontend/favicon.svg` foi extraído da marca (o "swirl" azul/magenta) usada no
topo do login e da topbar — um subconjunto de 2 `<path>` do SVG de marca
completo (`viewBox="0 0 142 201"`), sem o texto/wordmark. Referenciado em
`index.html` via `<link rel="icon" type="image/svg+xml" href="favicon.svg">`.

### 7.7 Exportação
- **Excel**: `SheetJS` client-side, sem round-trip ao backend — gera `.xlsx`
  a partir do `state` já carregado. A exportação do Painel
  (`btn-export-painel-excel`) já inclui colunas de `RAG Geral`, `Score
  Consolidado` e `Alertas` além dos 8 pilares.
- **PDF**: monta um relatório limpo em `#print-view` (oculto por padrão) e
  aciona `window.print()`; CSS `@media print` esconde todo o resto da página.
  A tabela impressa também reproduz o cabeçalho agrupado por categoria e as
  colunas de RAG Geral/Score.

---

## 8. Scripts de Manutenção (`scripts/`)

Scripts Python standalone, cada um conectando diretamente ao Postgres de
produção via `DATABASE_URL` (não fazem parte do deploy da aplicação — são
executados manualmente, uma vez, quando necessário). Todos reimplementam
localmente qualquer helper que precisam (hash de senha, etc.) para não
depender de imports cruzados com `api/index.py`.

| Script | Propósito |
|---|---|
| `seed.py` | Seed inicial de produção: pessoas do organograma real, 24→26 clientes, critérios base |
| `migrate_auth.py` | Idempotente: define email + senha padrão + `precisa_trocar_senha=1` para as 21 pessoas do organograma + cria/atualiza o admin (M. Andersen) |
| `migrate_criterios_v2.py` | Idempotente: insere os pilares Margem/CSAT na tabela `criterios`, renumerando `ordem` dos demais |
| `grant_acesso_full.py` | Concede `acesso_full=1` aos 3 BU Directors sem alterar `papel` |
| `migrate_criterios_v3.py` | Idempotente: insere o novo pilar `receita` (3 linhas, G/A/R para a linha "Todas") na tabela `criterios` e renumera `ordem` de todas as linhas para refletir as 4 categorias atuais (Financeiro/Execução/Pessoas/Relacionamento); registra um evento `criterio/migrar` em `auditoria` |
| `reset_dados.py` | Limpa todos os `riscos_issues` e `status_history`, redefine todo cliente/pilar (nos 8 pilares atuais) para `G`, registra o reset em `auditoria` |

Uso típico: `DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/<nome>.py`

---

## 9. Estrutura do Repositório

```
rag-status/
  api/
    index.py            # backend de produção (Vercel) — arquivo único, ver §9.1
  backend/               # versão LOCAL legada (SQLite) — referência de dev, NÃO deployada
    app.py, db.py, seed.py
  frontend/
    index.html, app.js, styles.css, favicon.svg
  scripts/               # scripts de manutenção de produção (ver §8)
  vercel.json
  requirements.txt
  .gitignore
  README.md
  DOCUMENTACAO_TECNICA.md        # este arquivo
  ESPECIFICACAO_FUNCIONAL.md
```

### 9.1 Por que `api/index.py` é um arquivo único
O runtime Python da Vercel (`@vercel/python`) **não adiciona o diretório da
própria função ao `sys.path`** — um módulo irmão (`api/db.py`, por exemplo)
resulta em `ModuleNotFoundError` em produção, mesmo funcionando perfeitamente
em ambiente local. Por isso todo o backend de produção — schema, helpers,
modelos Pydantic, rotas, modelo de pontuação e envio de email do cron —
vive em um único arquivo, hoje com mais de 1300 linhas. Qualquer evolução
futura do backend deve manter esse padrão (ou reintroduzir um módulo irmão
somente após confirmar que o comportamento do runtime mudou).

### 9.2 `backend/` (legado, não deployado)
Versão inicial de desenvolvimento local em SQLite (`app.py`/`db.py`/`seed.py`),
mantida apenas como referência histórica. **Não é usada em produção** — a
fonte de verdade é exclusivamente `api/index.py` (Postgres). Esta versão
legada não foi atualizada com o pilar Receita, o modelo de pontuação ou o
resumo diário por email — trate-a como puramente histórica.

---

## 10. Decisões Técnicas Notáveis / Histórico de Problemas Resolvidos

| Problema | Causa raiz | Solução |
|---|---|---|
| `ModuleNotFoundError` em produção | Vercel não injeta o diretório da função no `sys.path` | Consolidar tudo em `api/index.py` |
| Painel demorando ~19s para carregar | Padrão N+1 (∼4 queries por cliente × 24 clientes) + função em `iad1` vs banco em `sa-east-1` | Batch queries com `JOIN`/`GROUP BY` (`_all_current_status`, `_all_riscos_abertos_counts`, `_all_dms`) + `regions:["gru1"]` no `vercel.json` — resultado: ~100-150ms |
| Overflow horizontal da página inteira no mobile | Header (`topbar-inner`) sem `flex-wrap`, textos não quebravam linha | `flex-wrap:wrap` + stacking no breakpoint 720px |
| Modal de troca de senha obrigatória não aparecia visualmente | Tela de login com `z-index` mais alto ficava por cima do modal | `entrarNaAplicacao()` esconde a tela de login incondicionalmente antes de decidir qual modal/tela mostrar |
| BU Directors precisavam de acesso pleno ao Admin | Simplesmente setar `papel="admin"` quebraria o agrupamento visual (que filtra por `papel === "bu_director"`) | Flag `acesso_full` independente do `papel` (§6.3) |
| Passagem de parâmetros SQLite→Postgres | Placeholders `?` do sqlite3 vs `%s` do psycopg2; bool do Python não converte implicitamente para `INTEGER` no Postgres | Classe `_ConnWrapper` faz a tradução (`?`→`%s`) e conversão de bool→int nos parâmetros, minimizando reescrita de código herdado do protótipo SQLite |
| Faturamento sozinho não capturava saúde comercial da conta (apenas caixa/operacional) | Um único pilar misturava dois sinais diferentes (recebimento de fatura vs. receita vs. meta) | Pilar `receita` separado, com peso próprio (15%) e regra de alerta específica (`_calcular_alertas`) |
| Precisava de um número único (executivo) para priorizar contas, sem esconder que "qualquer vermelho é crítico" | Uma média simples de pilares mascararia um único pilar em R | `calcular_score` pondera por `PILAR_PESO`, mas `rag_geral` sempre força `R` se qualquer pilar estiver em R, antes de olhar o score |
| Nenhum canal passivo para acompanhar o sistema sem abrir o Painel todo dia | — | Cron diário (`GET /api/cron/resumo-diario`) monta e envia um resumo executivo por email via Resend, usando só `urllib` da stdlib para não adicionar dependência pip |

---

## 11. Limitações Conhecidas

- Sem ambiente de staging — todo push em `main` vai direto para produção.
- Sem testes automatizados (unitários/integração/E2E).
- Sem rate limiting nas rotas de autenticação.
- Sem rotação/expiração de sessão além do TTL fixo de 7 dias (sem refresh
  token).
- `responsavel` em `riscos_issues` continua sendo `TEXT` livre no banco
  (o frontend já restringe a escolha a pessoas cadastradas via combo, mas o
  schema não tem uma FK formal para isso).
- Sem paginação em `GET /api/clientes`/`GET /api/riscos` (aceitável no volume
  atual — 26 clientes; deve ser revisitado se a base crescer
  significativamente).
- Pesos (`PILAR_PESO`), cortes de score (`SCORE_CORTE_G`/`SCORE_CORTE_A`) e
  donos (`PILAR_DONO`) são constantes hard-coded em `api/index.py`, duplicadas
  manualmente no frontend (`app.js`) — não há endpoint que sirva esse "modelo"
  dinamicamente nem tela de Admin para editá-los; qualquer ajuste exige
  alterar os dois arquivos e redeployar.
- O destinatário do resumo diário por email (`DIGEST_EMAIL_TO`) é uma
  constante única hard-coded no código — não há lista de destinatários
  configurável nem preferências por usuário.
- O cron de resumo diário depende de duas variáveis de ambiente externas
  (`CRON_SECRET`, `RESEND_API_KEY`); se qualquer uma faltar, a rota falha
  silenciosamente do ponto de vista do usuário final (só aparece nos logs da
  função/Vercel Cron, não há alerta ativo de falha de envio).
