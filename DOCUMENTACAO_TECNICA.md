# Documentação Técnica — RAG Status

**Sistema:** RAG Status — Gestão Executiva de Clientes/Contratos (SysManager)
**Repositório:** https://github.com/marcosandersensys/RAG
**Produção:** https://rag-status.vercel.app
**Última atualização deste documento:** 2026-07-21

---

## 1. Visão Geral

RAG Status é uma aplicação web para acompanhamento executivo semanal do status
RAG (Red/Amber/Green) dos clientes/contratos da SysManager, organizada por 7
dimensões de análise, com gestão obrigatória de Riscos/Problemas associados a
qualquer status não-verde, hierarquia organizacional (BU Director → AM → DM),
controle de acesso por papel, e trilha de auditoria de todas as alterações.

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
Nenhuma outra dependência de terceiros — autenticação, hashing e geração de
token usam exclusivamente a biblioteca padrão do Python (`hashlib`, `hmac`,
`secrets`), decisão deliberada para evitar problemas de empacotamento nativo
no runtime serverless da Vercel.

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
  "regions": ["gru1"]
}
```
A região `gru1` (São Paulo) foi fixada deliberadamente para co-localizar a
função serverless com o banco Neon (`sa-east-1`) e reduzir latência de rede —
sem isso, medimos ~19s de carregamento do Painel (função em `iad1`/EUA
conversando com banco no Brasil); depois da correção, ~100-150ms.

### Variáveis de ambiente (produção, configuradas na Vercel)
| Variável | Descrição |
|---|---|
| `DATABASE_URL` | Connection string do Neon Postgres (injetada pela integração Vercel↔Neon; obrigatória — sem ela toda rota `/api/*` retorna 500) |

Não há outras variáveis de ambiente/secrets — sem chave de assinatura JWT,
sem API keys de terceiros no backend.

---

## 4. Modelo de Dados

Banco: **PostgreSQL** (Neon). Schema aplicado de forma idempotente a cada
cold start da função (`init_db()` roda `CREATE TABLE IF NOT EXISTS` e
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` no lifespan do FastAPI) — não há
ferramenta de migration (Alembic etc.); evolução de schema é feita por essas
declarações idempotentes diretamente no código-fonte (`api/index.py`, string
`SCHEMA`).

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
| `pilar` | `TEXT NOT NULL` | um dos 7 pilares (§ver Especificação Funcional) |
| `status` | `TEXT NOT NULL` | `G` \| `A` \| `R` |
| `semana` | `TEXT NOT NULL` | segunda-feira da semana de referência (`YYYY-MM-DD`) |
| `comentario` | `TEXT` | |
| `atualizado_por` | `TEXT NOT NULL` | nome da pessoa autenticada (server-side, não confiável do cliente) |
| `atualizado_em` | `TEXT NOT NULL` | timestamp ISO |
| Índice | `idx_status_history_cliente_pilar` em `(cliente_id, pilar, atualizado_em)` | |

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

Estado atual: 27 linhas (9 combinações pilar/linha × 3 status G/A/R).

### 4.7 `sessoes`
Sessões de autenticação (token opaco, não JWT).
| Coluna | Tipo |
|---|---|
| `token` | `TEXT PK` (gerado via `secrets.token_urlsafe(32)`) |
| `pessoa_id` | `INTEGER NOT NULL REFERENCES pessoas(id)` |
| `criado_em` / `expira_em` | `TEXT NOT NULL` (expiração: 7 dias — constante `SESSAO_DIAS`) |
| Índice | `idx_sessoes_expira` em `expira_em` |

### 4.8 `auditoria`
Log de toda alteração feita no sistema (ver §6.4).
| Coluna | Tipo |
|---|---|
| `id` | `SERIAL PK` |
| `entidade` | `TEXT NOT NULL` — `cliente` \| `pessoa` \| `status` \| `risco` \| `criterio` \| `sistema` |
| `entidade_id` | `INTEGER` (nullable — null para eventos de sistema/scripts) |
| `acao` | `TEXT NOT NULL` — `criar` \| `editar` \| `fechar` \| `resetar_senha` \| `trocar_senha` \| `resetar` |
| `pessoa_id` | `INTEGER REFERENCES pessoas(id)` (nullable — null para ações via script) |
| `pessoa_nome` | `TEXT NOT NULL` (preservado mesmo que a pessoa seja depois excluída/renomeada) |
| `detalhes` | `TEXT` — string legível com diff de campos alterados (`campo: antigo → novo`) |
| `criado_em` | `TEXT NOT NULL` |
| Índices | `idx_auditoria_criado_em` (DESC), `idx_auditoria_entidade` |

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

---

## 5. API — Referência de Endpoints

Todas as rotas sob `/api/*`. Autenticação via header
`Authorization: Bearer <token>`, exceto `POST /api/auth/login`. Payloads e
respostas em JSON.

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
| GET | `/api/clientes` | sessão | lista filtrada por RBAC (ver §6.2) |
| GET | `/api/clientes/{id}` | sessão + acesso ao cliente | detalhe + histórico + riscos |
| POST | `/api/clientes` | admin/acesso_full | cria cliente + status inicial G em todos os pilares |
| PUT | `/api/clientes/{id}` | admin/acesso_full | edição parcial + gestão de `dm_ids` |

### Status RAG
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/pilares` | sessão | lista os 7 pilares (`key`+`label`) |
| POST | `/api/status` | sessão + acesso ao cliente | registra novo status; exige risco se não-verde (ver §7.1) |

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
| GET | `/api/dashboard/resumo` | sessão | contagens agregadas (total clientes, críticos, riscos abertos/atrasados, contagem por pilar/status) — respeita RBAC |

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
busca textual em usuário/detalhes.

---

## 7. Frontend

### 7.1 Estrutura de arquivos
```
frontend/
  index.html   — shell da SPA: telas (login, painel, riscos, organização, admin) + modais
  app.js       — toda a lógica (fetch, renderização, RBAC de UI, exportação)
  styles.css   — design tokens + estilos
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

### 7.3 Design System (SysManager Design System v2)
- Tipografia: **Sora** (headings) + **Montserrat** (body), via Google Fonts.
- Paleta: `--sys-blue:#1059AF`, `--sys-magenta:#FC429A`, `--sys-purple:#663B8A`,
  fundo `--bg-page:#F0F2F4` (nunca branco puro), semânticas
  `--success/--warning/--destructive/--info`.
- Padrão canônico de tabela: header `#041830` com texto branco, linhas
  zebradas (`#FFFFFF`/`#FAFBFC`), badges pill (`border-radius:20px`).
- Cards: `border-radius:16px`, sombra dupla (`--shadow-card`).

### 7.4 Responsividade
- Breakpoint principal em `720px`.
- Header reflow (evita overflow horizontal da página inteira).
- Alvos de toque ampliados (~44pt) em botões/badges no breakpoint mobile.
- Primeira coluna de tabelas largas fixada (`position:sticky`) para rolagem
  horizontal sem perder o nome do cliente/pessoa de vista.

### 7.5 Exportação
- **Excel**: `SheetJS` client-side, sem round-trip ao backend — gera `.xlsx`
  a partir do `state` já carregado.
- **PDF**: monta um relatório limpo em `#print-view` (oculto por padrão) e
  aciona `window.print()`; CSS `@media print` esconde todo o resto da página.

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
| `reset_dados.py` | Limpa todos os `riscos_issues` e `status_history`, redefine todo cliente/pilar para `G`, registra o reset em `auditoria` |

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
    index.html, app.js, styles.css
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
modelos Pydantic, rotas — vive em um único arquivo. Qualquer evolução futura
do backend deve manter esse padrão (ou reintroduzir um módulo irmão somente
após confirmar que o comportamento do runtime mudou).

### 9.2 `backend/` (legado, não deployado)
Versão inicial de desenvolvimento local em SQLite (`app.py`/`db.py`/`seed.py`),
mantida apenas como referência histórica. **Não é usada em produção** — a
fonte de verdade é exclusivamente `api/index.py` (Postgres).

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
