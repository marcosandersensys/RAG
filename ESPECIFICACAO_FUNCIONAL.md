# Especificação Funcional — RAG Status

**Sistema:** RAG Status — Gestão Executiva de Clientes/Contratos (SysManager)
**Produção:** https://rag-status.vercel.app
**Última atualização deste documento:** 2026-07-21

---

## 1. Visão Geral e Contexto de Negócio

O RAG Status é a alternativa da SysManager para o acompanhamento executivo de
clientes/contratos enquanto o Microsoft Project Operations não está
funcional em produção. Substitui o controle anterior (planilha/SharePoint)
por uma aplicação web dedicada, com:

- Status RAG (🟢 Verde / 🟡 Âmbar / 🔴 Vermelho) por cliente, medido em **7
  dimensões de análise**.
- Gestão obrigatória de **Riscos e Problemas** vinculados a qualquer
  dimensão não-verde.
- Hierarquia organizacional real (**BU Director → Account Manager → Delivery
  Manager**), com suporte a múltiplos DMs por cliente.
- Controle de acesso por papel, para que cada gestor veja e atualize apenas
  os clientes sob sua responsabilidade.
- Trilha de auditoria completa de todas as alterações do sistema.
- Cadência de atualização **dinâmica** (sempre que houver mudança relevante,
  não amarrada a um dia fixo da semana).

Os critérios de classificação (o que qualifica cada dimensão como G/A/R)
ainda são parcialmente subjetivos por natureza do negócio, e devem evoluir
com o tempo — o sistema foi desenhado para que essa régua (aba "Critérios")
seja editável sem depender de alteração de código.

---

## 2. Perfis de Usuário e Permissões

| Papel | Quem | O que vê | O que pode fazer |
|---|---|---|---|
| **Admin** | M. Andersen (dono do sistema) | Todos os clientes | Tudo — inclui módulo Admin completo (Pessoas, Clientes, Critérios, Auditoria) |
| **BU Director com acesso full** | Homero Tavares, Carlos Sapateiro, Marisa Albuquerque | Todos os clientes (por terem `acesso_full`) | Tudo — mesmo nível do Admin, incluindo módulo Admin completo, **mantendo** sua identidade de BU Director (continuam aparecendo como diretores nas telas de Painel/Organização) |
| **BU Director (padrão)** | qualquer diretor sem `acesso_full` | Apenas clientes da sua própria BU | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao módulo Admin |
| **AM (Account Manager)** | ex: L. Nunes, R. Pires, P. Vilaça | Apenas clientes em que é o AM designado | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao Admin |
| **DM (Delivery Manager)** | ex: A. Pollis, C. Dana, D. Leal | Apenas clientes em que é um dos DMs designados | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao Admin |

Todo controle de acesso é reforçado no servidor (não apenas escondendo botões
na tela) — uma tentativa de acessar ou alterar um cliente fora do escopo
retorna erro 403, mesmo que feita diretamente contra a API.

### 2.1 Login
- Login = e-mail corporativo SysManager (`nome.sobrenome@sysmanager.com.br`).
- Senha inicial para todos: `SysManager@2026`.
- **Troca de senha obrigatória** no primeiro acesso (modal não pode ser
  fechado sem definir uma nova senha).
- Política de senha: mínimo 10 caracteres, com maiúscula, minúscula, número e
  caractere especial.
- Sessão válida por 7 dias; expira automaticamente após esse período.
- Qualquer pessoa (inclusive não-admin) pode trocar a própria senha a
  qualquer momento pelo link "Trocar senha" no topo da tela.
- Um Admin/acesso-full pode resetar a senha de qualquer pessoa para o padrão
  (isso também invalida imediatamente qualquer sessão ativa daquela pessoa).

---

## 3. Hierarquia Organizacional

```
BU Director  ──▶  Account Manager (AM)  ──▶  Delivery Manager(s) (DM)
```

- Cada cliente tem **um** BU Director e **um** AM designados.
- Cada cliente pode ter **um ou mais** DMs simultâneos (ex: contas grandes
  como Petrobras têm até 3 DMs atuando ao mesmo tempo).
- Um BU Director pode também atuar diretamente como AM de alguns de seus
  próprios clientes (ex: H. Tavares é BU Director e também AM da conta
  Petrobras).
- A aba **Organização** exibe essa estrutura de duas formas, ambas somente-
  leitura e **derivadas** dos mesmos vínculos cadastrados em Admin (não há
  dado duplicado, o que evita divergência entre as duas visões):
  - **Por Cliente**: agrupado por BU Director → cada cliente com seu AM/DM(s).
  - **Por Pessoa**: agrupado por BU Director → cada AM/DM com a lista de
    clientes que atende (uma pessoa cadastrada como AM/DM sem nenhum cliente
    vinculado aparece numa seção separada "sem cliente vinculado ainda").

Estado atual de produção: 3 BU Directors, 8 AMs, 10 DMs, 26 clientes ativos.

---

## 4. As 7 Dimensões de Análise (Pilares) e Critérios G/A/R

Ordem de exibição em toda a aplicação (Painel, exportações, filtros):

**Prazo → Faturamento → Margem → Escopo → RH → CSAT → Contrato**

| Pilar | Linha | 🟢 Verde | 🟡 Âmbar | 🔴 Vermelho |
|---|---|---|---|---|
| **Prazo** | Projeto | On track | Desvio recuperável | Atraso crítico |
| **Prazo** | Sustentação | Dentro do SLA | Risco financeiro | Operação abaixo do mínimo, prejuízo |
| **Faturamento** | Todas | Sem impedimentos | Atraso <10 dias | Atraso >10 dias |
| **Margem** | Todas | Margem ≥ meta contratual | Margem 5–10 p.p. abaixo da meta | Margem >10 p.p. abaixo da meta, ou prejuízo direto |
| **Escopo** | Projeto, Sustentação | Sem mudanças | Mudanças leves | Mudanças severas, prejuízo |
| **Escopo** | Alocação | Execução total | ≥80% da função | Desvio grave |
| **RH** | Todas | Estável | Ruídos contornáveis | Impacto financeiro, perda crítica |
| **CSAT** | Todas | NPS/CSAT ≥ meta; sem escalada formal | Reclamação pontual sem escalada a sponsor | Escalada formal ao sponsor/C-level, ou risco de não-renovação verbalizado |
| **Contrato** | Todas | >90 dias; saldo ok | ≤90 dias; saldo limitado | ≤30 dias; saldo insuficiente |

Essa tabela é editável (aba **Admin → Critérios**, restrita a quem tem acesso
full) e consultável por qualquer usuário a qualquer momento pelo botão
**"? Critérios"** no Painel — tanto de forma geral quanto por pilar específico
(o "?" ao lado de cada coluna abre a referência já rolada até aquele pilar).

Reconhecidamente, os critérios ainda têm um grau de subjetividade — a
expectativa é evoluí-los com o tempo, à medida que o time amadurece a
definição de cada dimensão.

---

## 5. Regras de Negócio

### 5.1 Risco/Problema obrigatório em status não-verde
Ao mover qualquer pilar de um cliente para **Âmbar** ou **Vermelho**, o
sistema **exige** que exista pelo menos um Risco ou Problema em aberto
vinculado àquele cliente+pilar. Se não houver, a tentativa de salvar é
bloqueada e o próprio formulário de status abre os campos de
Risco/Problema para preenchimento (título, descrição, severidade,
responsável, plano de mitigação, data-alvo) — a atualização de status e a
criação do risco acontecem na mesma ação.

### 5.2 Nota de encerramento obrigatória
Ao mover um Risco/Problema para o status **Encerrado**, o sistema exige uma
**nota de encerramento** descrevendo como foi resolvido — não é possível
encerrar silenciosamente sem essa explicação. A nota fica permanentemente
registrada e visível na aba "Encerrados".

### 5.3 Cadência de atualização
As atualizações de status devem ser feitas de forma **dinâmica**, sempre que
houver uma mudança relevante — não há um dia fixo de corte semanal. O
sistema registra a semana de referência (segunda-feira) de cada atualização
para fins de histórico, mas não impõe periodicidade.

### 5.4 Responsável pela mitigação
O campo "Responsável pela mitigação" de um Risco/Problema é selecionado a
partir de uma lista das pessoas ativas cadastradas no sistema (qualquer
papel — BU Director, AM ou DM), evitando divergência de nomes por digitação
livre.

### 5.5 Atraso (aging)
Um Risco/Problema é sinalizado como **Atrasado** quando sua "Data alvo" já
passou e ele ainda não foi encerrado. Itens atrasados aparecem destacados e
ordenados primeiro na lista de "Em Aberto", e contam num indicador dedicado
no Painel.

---

## 6. Funcionalidades por Tela

### 6.1 Login
- Formulário de e-mail + senha.
- Modal de troca de senha obrigatória no primeiro acesso (não fecha até a
  troca ser concluída).

### 6.2 Painel (tela principal)
- Cards de resumo: total de clientes ativos, clientes com pilar vermelho,
  riscos/problemas em aberto, riscos/problemas atrasados.
- Filtros: busca por cliente/AM/DM, BU Director, Industry Code, "apenas com
  pilar não-verde".
- Tabela agrupada por BU Director, uma seção por diretor, com colunas:
  Cliente, Industry, AM, DM(s), Modificado, e um badge circular G/A/R
  clicável para cada um dos 7 pilares.
- Clicar num badge abre o modal de **atualização de status** daquele
  pilar/cliente (com a regra de risco obrigatório do §5.1).
- Clicar no nome do cliente abre o **modal de detalhe do cliente**:
  - Snapshot atual dos 7 pilares.
  - **Linha do tempo por pilar**: visualização horizontal com pontos
    coloridos (G/A/R) em ordem cronológica, conectados por uma linha —
    clicar num ponto mostra data, autor e comentário daquela medição
    específica.
  - Equipe (BU Director/AM/DM(s)).
  - Histórico recente (lista detalhada, últimas atualizações).
  - Riscos/Problemas vinculados (clicáveis, abrem o editor de risco).
- Exportação **Excel** (todas as colunas visíveis) e **PDF** (relatório
  limpo, agrupado por BU Director, via diálogo de impressão do navegador).
- Botão **"? Critérios"**: abre a régua de referência G/A/R completa.

### 6.3 Riscos & Problemas
Dividida em duas sub-abas (prática comum em ferramentas de gestão de
tickets/ITSM, para não misturar o que precisa de ação com o que já foi
resolvido):

- **Em Aberto** (contagem exibida na aba): Cliente, Pilar, Tipo, Título,
  Severidade, Responsável, Data alvo (com selo "Atrasado" quando aplicável),
  Aberto há (dias), Status (dropdown — mudar para "Fechado" aciona o modal
  de nota de encerramento obrigatória), e ação "Ver / Editar".
- **Encerrados** (contagem exibida na aba): Cliente, Pilar, Tipo, Título,
  Severidade, Responsável, Encerrado em, Duração total (dias entre criação e
  encerramento), Nota de encerramento, e ações "Ver / Editar" e **Reabrir**
  (volta o item para "Aberto", com confirmação).
- Filtros comuns às duas abas: Pilar, Severidade.
- Botão **"+ Novo Risco/Problema"**: cria um risco avulso, sem precisar
  passar por uma atualização de status.
- **Modal de edição** (substituindo um antigo `alert()` somente-leitura):
  mostra e permite editar todos os campos — tipo, título, descrição,
  severidade, responsável (combo), data alvo, plano de mitigação — com
  status e nota de encerramento exibidos como contexto.
- Exportação Excel de toda a lista (aberta + encerrada), incluindo os campos
  calculados (atrasado, dias em aberto/duração, nota de encerramento).

### 6.4 Organização
Somente-leitura, com alternância **Por Cliente** / **Por Pessoa** (ver §3).

### 6.5 Admin
Visível apenas para quem tem acesso full (Admin ou `acesso_full=1`).
Quatro sub-abas:

- **Pessoas**: cadastro/edição de BU Directors, AMs, DMs e Admins — nome,
  papel, e-mail (login), ativo/inativo, e o checkbox **"Acesso full ao
  Admin"** (concede o mesmo nível de acesso do Admin sem alterar o papel
  operacional da pessoa). Ação "Resetar senha" por pessoa.
- **Clientes**: cadastro/edição — nome, industry code, tipo de linha
  (Projeto/Sustentação), BU Director, AM, DM(s) (múltipla seleção),
  ativo/inativo. É aqui que se editam todos os vínculos organizacionais.
- **Critérios**: a régua G/A/R completa, editável célula a célula (clique
  para editar, salva automaticamente ao sair do campo).
- **Auditoria**: log de todas as alterações do sistema — data/hora, usuário,
  entidade afetada, ação, e detalhes (incluindo o que mudou, campo a campo).
  Filtrável por entidade e por busca textual (usuário ou detalhe).

---

## 7. Fluxos de Usuário Principais

### 7.1 Primeiro acesso
1. Usuário recebe o link + e-mail/senha padrão.
2. Faz login → sistema força a troca de senha antes de liberar qualquer tela.
3. Usuário define nova senha (política forte) → entra no Painel, já vendo
   apenas os clientes sob sua responsabilidade.

### 7.2 Atualizar o status de um pilar
1. No Painel, clica no badge do pilar desejado para o cliente.
2. Escolhe o novo status (G/A/R) e adiciona um comentário.
3. Se o status não for verde e não houver risco/problema em aberto para
   aquele pilar, o formulário de risco é exibido e deve ser preenchido para
   poder salvar.
4. Ao salvar, o Painel e o histórico do cliente são atualizados
   imediatamente; a ação fica registrada na Auditoria.

### 7.3 Encerrar um Risco/Problema
1. Na aba Riscos & Problemas → Em Aberto, muda o status para "Fechado".
2. Modal pede a nota de encerramento (obrigatória).
3. Item passa para a aba Encerrados, com duração calculada e nota visível.

### 7.4 Conceder acesso a um novo membro do time
1. Admin ou BU Director com acesso full vai em Admin → Pessoas.
2. Cadastra a pessoa (nome, papel, e-mail) → sistema já gera senha padrão e
   marca para trocar no primeiro login.
3. Em Admin → Clientes, vincula essa pessoa como AM/DM do(s) cliente(s)
   correspondente(s).

---

## 8. Auditoria

Toda alteração relevante do sistema é registrada automaticamente:
criação/edição de clientes, criação/edição de pessoas, toda atualização de
status RAG, criação/edição/encerramento de riscos e problemas, edição de
critérios, troca/reset de senha. Cada registro traz **quem** fez, **quando**,
em **qual entidade**, **qual ação**, e um resumo legível do que mudou
(`campo: valor antigo → valor novo`). Consultável em Admin → Auditoria, com
filtro por tipo de entidade e busca livre.

---

## 9. Requisitos Não-Funcionais

- **Performance**: carregamento do Painel em ~100-150ms em uso normal
  (otimizado a partir de um problema inicial de ~19s — ver Documentação
  Técnica §10).
- **Responsividade**: interface utilizável em desktop e mobile (iPhone),
  incluindo tabelas largas com rolagem horizontal e coluna fixa.
- **Segurança**: senhas com hash forte (nunca em texto plano), sessões com
  expiração, controle de acesso reforçado no servidor (não só na tela),
  trilha de auditoria completa.
- **Disponibilidade**: hospedado na Vercel (função serverless) + Neon
  (Postgres gerenciado) — sem infraestrutura própria para manter.
- **Idioma**: interface e dados em Português (Brasil).

---

## 10. Glossário

| Termo | Significado |
|---|---|
| **RAG** | Red/Amber/Green — semáforo de status (aqui: Vermelho/Âmbar/Verde) |
| **BU Director** | Diretor de Business Unit — responsável executivo por um conjunto de clientes |
| **AM** | Account Manager — gestor comercial/relacionamento do cliente |
| **DM** | Delivery Manager — gestor de entrega/operação do contrato |
| **Pilar** | Cada uma das 7 dimensões de análise avaliadas por cliente (Prazo, Faturamento, Margem, Escopo, RH, CSAT, Contrato) |
| **Acesso full** | Permissão que concede acesso total ao módulo Admin e a todos os clientes, independente do papel operacional da pessoa |
| **Critérios** | Régua de referência que define o que qualifica cada pilar como G/A/R |
