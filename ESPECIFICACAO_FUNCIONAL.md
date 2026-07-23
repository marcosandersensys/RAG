# Especificação Funcional — RAG Status

**Sistema:** RAG Status — Gestão Executiva de Clientes/Contratos (SysManager)
**Produção:** https://rag-status.vercel.app
**Última atualização deste documento:** 2026-07-23

---

## 1. Visão Geral e Contexto de Negócio

O RAG Status é a alternativa da SysManager para o acompanhamento executivo de
clientes/contratos enquanto o Microsoft Project Operations não está
funcional em produção. Substitui o controle anterior (planilha/SharePoint)
por uma aplicação web dedicada, com:

- Status RAG (🟢 Verde / 🟡 Âmbar / 🔴 Vermelho) por cliente, medido em **8
  dimensões de análise (pilares)**, agrupadas em **4 categorias** para fins
  de exibição.
- Um **modelo de pontuação ponderado**, calculado automaticamente a partir
  dos 8 pilares, que produz um **Score Consolidado (0–100)** e um **RAG
  Geral** único por cliente — a visão executiva de "semáforo único" do
  cliente, sem precisar olhar pilar a pilar.
- Gestão obrigatória de **Riscos e Problemas** vinculados a qualquer
  dimensão não-verde.
- Hierarquia organizacional real (**BU Director → Account Manager → Delivery
  Manager**), com suporte a múltiplos DMs por cliente.
- Controle de acesso por papel, para que cada gestor veja e atualize apenas
  os clientes sob sua responsabilidade.
- Trilha de auditoria completa de todas as alterações do sistema, incluindo
  o status anterior em toda mudança de status RAG.
- Um **resumo executivo diário por email**, enviado automaticamente todos os
  dias, com tudo que mudou no sistema nas últimas 24 horas.
- Cadência de atualização **dinâmica** (sempre que houver mudança relevante,
  não amarrada a um dia fixo da semana).

Os critérios de classificação (o que qualifica cada pilar como G/A/R) ainda
são parcialmente subjetivos por natureza do negócio, e devem evoluir com o
tempo — o sistema foi desenhado para que essa régua (aba "Critérios") seja
editável sem depender de alteração de código. O mesmo vale para os pesos e
faixas de corte do modelo de pontuação (§5): são parâmetros de negócio,
não constantes fixas do produto.

---

## 2. Perfis de Usuário e Permissões

| Papel | Quem | O que vê | O que pode fazer |
|---|---|---|---|
| **Admin** | M. Andersen (dono do sistema) | Todos os clientes | Tudo — inclui módulo Admin completo (Pessoas, Clientes, Critérios, Auditoria) |
| **BU Director com acesso full** | Homero Tavares, Carlos Sapateiro, Marisa Albuquerque | Todos os clientes (por terem `acesso_full`) | Tudo — mesmo nível do Admin, incluindo módulo Admin completo, **mantendo** sua identidade de BU Director (continuam aparecendo como diretores nas telas de Painel/Organização) |
| **BU Director (padrão)** | qualquer diretor sem `acesso_full` | Apenas clientes da sua própria BU | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao módulo Admin |
| **AM (Account Manager)** | ex: L. Nunes, R. Pires, P. Vilaça | Apenas clientes em que é o AM designado | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao Admin |
| **DM (Delivery Manager)** | ex: A. Pollis, C. Dana, D. Leal | Apenas clientes em que é um dos DMs designados | Atualizar status/riscos dos clientes visíveis; **sem** acesso ao Admin |

**Acesso full** é uma permissão independente do papel organizacional: uma
pessoa pode ser BU Director (continua aparecendo como tal em toda a
hierarquia, no Painel e na aba Organização) e, adicionalmente, ter o
sinalizador "Acesso full ao Admin" ligado, que a eleva ao mesmo nível de um
Administrador — enxerga todos os clientes (não só os da sua própria BU) e
acessa todas as sub-abas de Admin (Pessoas, Clientes, Critérios, Auditoria).
Hoje os 3 BU Directors têm esse sinalizador ativo. O papel exibido na tela
continua sendo "BU Director" — acesso full não é um papel à parte, é um
adicional de permissão sobre o papel existente.

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
- Todo login é registrado (para fins do resumo executivo diário, §10) com
  data/hora, pessoa e papel.

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

---

## 4. As 8 Dimensões de Análise (Pilares), Categorias e Critérios G/A/R

### 4.1 Ordem e agrupamento

Os 8 pilares são agrupados em **4 categorias** para fins de exibição (nos
cabeçalhos do Painel, na régua de Critérios e no Modelo de Pontuação). Ordem
de exibição em toda a aplicação (Painel, régua de Critérios, exportações,
filtros):

| Categoria | Pilares (nesta ordem) |
|---|---|
| **Financeiro** | Faturamento → Receita → Margem |
| **Execução** | Prazo → Escopo |
| **Pessoas** | RH |
| **Relacionamento** | CSAT → Contrato |

> Nota: o rótulo da categoria "Relacionamento" foi encurtado — cobre tanto o
> relacionamento com o cliente (CSAT) quanto a saúde contratual (Contrato),
> mas passou a ser exibido apenas como "Relacionamento" nos cabeçalhos, para
> caber no layout compacto do Painel.

No Painel, os pilares aparecem com **códigos curtos** (FAT, REC, GM%, PRZ,
ESC, RH, CSAT, CTR) no cabeçalho da coluna — o nome completo do pilar fica
disponível ao passar o mouse (tooltip) sobre o código, e uma **linha
divisória vertical** no início de cada categoria separa visualmente os 4
grupos de colunas.

### 4.2 Critérios G/A/R por pilar

| Pilar | Linha | 🟢 Verde | 🟡 Âmbar | 🔴 Vermelho |
|---|---|---|---|---|
| **Faturamento** | Todas | Sem impedimentos | Atraso <10 dias | Atraso >10 dias |
| **Receita** | Todas | Receita realizada ≥ meta/orçado da conta | Receita 5–15% abaixo do orçado, sem tendência de queda | Receita >15% abaixo do orçado, ou queda em 2+ meses consecutivos |
| **Margem** | Todas | Margem ≥ meta contratual | Margem 5–10 p.p. abaixo da meta | Margem >10 p.p. abaixo da meta, ou prejuízo direto |
| **Prazo** | Projeto | On track | Desvio recuperável | Atraso crítico |
| **Prazo** | Sustentação | Dentro do SLA | Risco financeiro | Operação abaixo do mínimo, prejuízo |
| **Escopo** | Projeto, Sustentação | Sem mudanças | Mudanças leves | Mudanças severas, prejuízo |
| **Escopo** | Alocação | Execução total | ≥80% da função | Desvio grave |
| **RH** | Todas | Estável | Ruídos contornáveis | Impacto financeiro, perda crítica |
| **CSAT** | Todas | NPS/CSAT ≥ meta; sem escalada formal | Reclamação pontual sem escalada a sponsor | Escalada formal ao sponsor/C-level, ou risco de não-renovação verbalizado |
| **Contrato** | Todas | >90 dias; saldo ok | ≤90 dias; saldo limitado | ≤30 dias; saldo insuficiente |

**Faturamento** mede a saúde operacional/de caixa do contrato (nota fiscal
emitida e paga em dia). **Receita** é um pilar distinto, que mede a saúde
comercial/de previsão da conta (receita efetivamente realizada frente à
meta/orçamento da conta) — inclusive com um sinal de persistência (2+ meses
consecutivos de queda) que por si só já qualifica o pilar como Vermelho,
mesmo sem um desvio percentual grande num único mês.

Essa tabela é editável (aba **Admin → Critérios**, restrita a quem tem acesso
full, agora agrupada visualmente pelas 4 categorias) e consultável por
qualquer usuário a qualquer momento pelo botão **"? Critérios"** no Painel —
tanto de forma geral (mostrando a tabela completa, mais o Modelo de
Pontuação e as regras de consolidação — ver §5) quanto por pilar específico
(o "?" ao lado de cada coluna do Painel abre a referência já filtrada para
mostrar **apenas aquele pilar**, sem o restante da lista).

Reconhecidamente, os critérios ainda têm um grau de subjetividade — a
expectativa é evoluí-los com o tempo, à medida que o time amadurece a
definição de cada dimensão.

---

## 5. Modelo de Pontuação: Score Consolidado, RAG Geral e Alertas

Esta é uma regra de negócio central do sistema: além do status G/A/R
individual de cada um dos 8 pilares, todo cliente tem um **Score
Consolidado** e um **RAG Geral** — a visão de "semáforo único" usada para
priorização executiva. Ambos são **calculados em tempo real** a partir do
status atual de cada pilar (não são armazenados nem versionados) — ou seja,
mudar o status de um único pilar recalcula instantaneamente o Score e o RAG
Geral do cliente.

### 5.1 Peso e Dono de cada pilar

Cada pilar tem um **peso** (relevância no score) e um **Dono** (a
área/equipe responsável por agir quando aquele pilar está Âmbar ou
Vermelho):

| Categoria | Pilar | Peso | Dono |
|---|---|---|---|
| Financeiro | Faturamento | 10% | Delivery \| FP&A |
| Financeiro | Receita | 15% | Delivery \| FP&A |
| Financeiro | Margem | 15% | Delivery \| FP&A |
| Execução | Prazo | 10% | Delivery |
| Execução | Escopo | 10% | Delivery |
| Pessoas | RH | 10% | Delivery \| RH |
| Relacionamento | CSAT | 20% | Account |
| Relacionamento | Contrato | 10% | Account |
| **Total** | | **100%** | |

Os pesos e donos são parâmetros de negócio (não código) e podem mudar com a
maturidade da carteira — a soma sempre deve fechar em 100%.

### 5.2 Pontuação por status

Cada pilar contribui para o score conforme seu status atual:

| Status | Pontuação |
|---|---|
| 🟢 Verde (G) | 100 |
| 🟡 Âmbar (A) | 50 |
| 🔴 Vermelho (R) | 0 |

### 5.3 Score Consolidado (0–100)

O Score Consolidado é a **média ponderada** da pontuação dos 8 pilares,
usando o peso de cada um (§5.1):

```
Score Consolidado = Σ (peso do pilar × pontuação do status do pilar)
```

Exemplo: um cliente com todos os pilares Verdes tem Score 100. Um cliente
com CSAT (peso 20%) em Âmbar e os demais Verdes tem Score = 100 − 20% × 50 =
90.

### 5.4 RAG Geral (status executivo único do cliente)

O RAG Geral é derivado do Score Consolidado, com uma regra de **override
absoluto**:

1. **Qualquer pilar em Vermelho (R) força o RAG Geral para Vermelho** —
   sem exceção, independente do Score Consolidado resultante. Um único
   pilar crítico não pode ser "diluído" pela média dos demais.
2. Se nenhum pilar estiver em Vermelho: Score ≥ **85** ⇒ RAG Geral **Verde**.
3. Se nenhum pilar estiver em Vermelho: Score entre **50** e **84,9** ⇒ RAG
   Geral **Âmbar**.
4. Caso contrário (Score < 50) ⇒ RAG Geral **Vermelho**.

As faixas de corte (85 para Verde, 50 para Âmbar) são parâmetros de negócio,
ajustáveis conforme a maturidade da carteira.

### 5.5 Alertas (sinalizações informativas, não bloqueantes)

Além do RAG Geral, o sistema calcula até 3 alertas automáticos por cliente.
Esses alertas **não alteram** o Score Consolidado nem o RAG Geral — são
sinalizações de negócio para chamar atenção a padrões que a média isolada
não deixaria evidente. Ficam visíveis ao passar o mouse sobre o badge de
RAG Geral do cliente (Painel e modal de detalhe):

1. **Receita crítica**: se o pilar Receita está em Vermelho, dispara
   "Revisão obrigatória de Margem e Faturamento no próximo ciclo" — um
   problema de receita tende a se propagar para os pilares financeiros
   correlatos, e o alerta força essa revisão cruzada.
2. **Degradação sistêmica de categoria**: para qualquer categoria (§4.1)
   com 2 ou mais pilares em Âmbar ao mesmo tempo, dispara "Degradação
   sistêmica da categoria {nome da categoria}" — sinaliza que o problema não
   é pontual de um pilar, mas um padrão dentro da mesma área de negócio
   (ex: Faturamento **e** Receita ambos em Âmbar ao mesmo tempo, dentro da
   categoria Financeiro).
3. **Alerta cruzado pessoas + execução**: se RH está em Vermelho **e**
   Escopo está em Âmbar ou Vermelho ao mesmo tempo, dispara "Alerta cruzado:
   perda de pessoa-chave + desvio de execução" — sinaliza que a perda/saída
   de uma pessoa-chave pode estar por trás de um desvio de execução em
   curso.

### 5.6 Onde isso aparece na aplicação

- **Painel**: colunas "RAG Geral" e "Score" aparecem antes das colunas de
  pilar, para cada cliente. Um ícone **"?"** ao lado do cabeçalho "RAG
  Geral" abre uma explicação completa de como o cálculo funciona (o mesmo
  conteúdo do Modelo de Pontuação, abaixo).
- **Admin → Critérios**: abaixo da tabela editável de critérios G/A/R, uma
  tabela somente-leitura **"Modelo de Pontuação"** lista, para cada pilar:
  categoria, peso, pontuação (100/50/0 conforme legenda), contribuição
  ponderada (peso × pontuação) e Dono — seguida da legenda de pontuação por
  status e das regras de consolidação descritas em §5.4.
- **Botão global "? Critérios"** (disponível a todos no Painel): mostra
  exatamente o mesmo conteúdo completo da página Admin → Critérios —
  tabela de critérios G/A/R (agrupada pelas 4 categorias) + Modelo de
  Pontuação + regras de consolidação — não apenas um resumo parcial.
- **Modal de detalhe do cliente**: o badge de RAG Geral aparece no
  cabeçalho do modal (ao lado do nome/industry) e como uma linha "GERAL" no
  topo da linha do tempo por pilar.

---

## 6. Regras de Negócio

### 6.1 Risco/Problema obrigatório em status não-verde
Ao mover qualquer pilar de um cliente para **Âmbar** ou **Vermelho**, o
sistema **exige** que exista pelo menos um Risco ou Problema em aberto
vinculado àquele cliente+pilar. Se não houver, a tentativa de salvar é
bloqueada e o próprio formulário de status abre os campos de
Risco/Problema para preenchimento (título, descrição, severidade,
responsável, plano de mitigação, data-alvo) — a atualização de status e a
criação do risco acontecem na mesma ação.

### 6.2 Nota de encerramento obrigatória
Ao mover um Risco/Problema para o status **Encerrado**, o sistema exige uma
**nota de encerramento** descrevendo como foi resolvido — não é possível
encerrar silenciosamente sem essa explicação. A nota fica permanentemente
registrada e visível na aba "Encerrados".

### 6.3 Cadência de atualização
As atualizações de status devem ser feitas de forma **dinâmica**, sempre que
houver uma mudança relevante — não há um dia fixo de corte semanal. O
sistema registra a semana de referência (segunda-feira) de cada atualização
para fins de histórico, mas não impõe periodicidade.

### 6.4 Responsável pela mitigação
O campo "Responsável pela mitigação" de um Risco/Problema é selecionado a
partir de uma lista das pessoas ativas cadastradas no sistema (qualquer
papel — BU Director, AM ou DM), evitando divergência de nomes por digitação
livre.

### 6.5 Atraso (aging)
Um Risco/Problema é sinalizado como **Atrasado** quando sua "Data alvo" já
passou e ele ainda não foi encerrado. Itens atrasados aparecem destacados e
ordenados primeiro na lista de "Em Aberto", e contam num indicador dedicado
no Painel.

### 6.6 Rastreabilidade da transição de status
Toda atualização de status de pilar registra também o **status anterior**.
Quando um pilar muda de valor (ex: de Verde para Âmbar), a auditoria (§9)
guarda a transição completa no formato "Pilar Faturamento: G → A" — não
apenas o novo valor. Isso permite reconstruir, olhando só o log de
auditoria, a evolução exata de qualquer pilar ao longo do tempo.

---

## 7. Funcionalidades por Tela

### 7.1 Login
- Formulário de e-mail + senha.
- Modal de troca de senha obrigatória no primeiro acesso (não fecha até a
  troca ser concluída).

### 7.2 Painel (tela principal)
- Cards de resumo: total de clientes ativos, clientes com pilar vermelho,
  riscos/problemas em aberto, riscos/problemas atrasados.
- Filtros: busca por cliente/AM/DM, BU Director, Industry Code, "apenas com
  pilar não-verde".
- Tabela agrupada por BU Director, uma seção por diretor, com colunas:
  Cliente, Industry (IND), Modificado (MOD, em formato de data curta
  dd/mm/aa), **RAG Geral** (com ícone "?" explicativo), **Score**, um badge
  circular G/A/R clicável para cada um dos 8 pilares (exibidos com código
  curto e agrupados visualmente pelas 4 categorias, com divisória entre
  grupos), AM e DM.
- Clicar num badge de pilar abre o modal de **atualização de status** daquele
  pilar/cliente (com a regra de risco obrigatório do §6.1).
- Clicar no nome do cliente abre o **modal de detalhe do cliente** (mais
  largo, para acomodar os 8 mini-badges de pilar numa única linha):
  - Badge de **RAG Geral** no cabeçalho do modal, ao lado do nome/industry.
  - Snapshot atual dos 8 pilares (mini-badges com código curto e nome
    completo em tooltip).
  - **Linha do tempo por pilar**: visualização horizontal com pontos
    coloridos (G/A/R) em ordem cronológica, conectados por uma linha —
    clicar num ponto mostra data, autor e comentário daquela medição
    específica. Uma linha "GERAL" no topo mostra o badge de RAG Geral atual.
  - Equipe (BU Director/AM/DM(s)).
  - Histórico recente (lista detalhada, últimas atualizações).
  - Riscos/Problemas vinculados (clicáveis, abrem o editor de risco).
- Exportação **Excel** (todas as colunas visíveis, incluindo RAG Geral,
  Score Consolidado e os alertas) e **PDF** (relatório limpo, agrupado por
  BU Director, via diálogo de impressão do navegador).
- Botão **"? Critérios"**: abre a régua de referência completa — critérios
  G/A/R por pilar (agrupados pelas 4 categorias) **+** Modelo de Pontuação
  **+** regras de consolidação do RAG Geral (ver §5.6).

### 7.3 Riscos & Problemas
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
- **Modal de edição**: mostra e permite editar todos os campos — tipo,
  título, descrição, severidade, responsável (combo), data alvo, plano de
  mitigação — com status e nota de encerramento exibidos como contexto.
- Exportação Excel de toda a lista (aberta + encerrada), incluindo os campos
  calculados (atrasado, dias em aberto/duração, nota de encerramento).

### 7.4 Organização
Somente-leitura, com alternância **Por Cliente** / **Por Pessoa** (ver §3).

### 7.5 Admin
Visível apenas para quem tem acesso full (Admin ou `acesso_full=1`).
Quatro sub-abas:

- **Pessoas**: cadastro/edição de BU Directors, AMs, DMs e Admins — nome,
  papel, e-mail (login), ativo/inativo, e o checkbox **"Acesso full ao
  Admin"** (concede o mesmo nível de acesso do Admin sem alterar o papel
  operacional da pessoa). Ação "Resetar senha" por pessoa.
- **Clientes**: cadastro/edição — nome, industry code, tipo de linha
  (Projeto/Sustentação), BU Director, AM, DM(s) (múltipla seleção),
  ativo/inativo. É aqui que se editam todos os vínculos organizacionais.
- **Critérios**:
  - A régua G/A/R completa, editável célula a célula (clique para editar,
    salva automaticamente ao sair do campo), agora agrupada visualmente
    pelas 4 categorias (§4.1) com uma linha de cabeçalho de categoria antes
    de cada grupo de pilares.
  - Abaixo, o **Modelo de Pontuação** (somente-leitura): categoria, pilar,
    peso, pontuação, peso × pontuação (contribuição) e Dono — para cada um
    dos 8 pilares — seguido das regras de consolidação do RAG Geral (§5.4)
    e da legenda G=100/A=50/R=0.
- **Auditoria**: log de todas as alterações do sistema — data/hora, usuário,
  entidade afetada, ação, e detalhes (incluindo o que mudou, campo a campo,
  e — no caso de status RAG — a transição de/para explícita). Filtrável por
  entidade e por busca textual (usuário ou detalhe).

---

## 8. Fluxos de Usuário Principais

### 8.1 Primeiro acesso
1. Usuário recebe o link + e-mail/senha padrão.
2. Faz login → sistema força a troca de senha antes de liberar qualquer tela.
3. Usuário define nova senha (política forte) → entra no Painel, já vendo
   apenas os clientes sob sua responsabilidade.

### 8.2 Atualizar o status de um pilar
1. No Painel, clica no badge do pilar desejado para o cliente.
2. Escolhe o novo status (G/A/R) e adiciona um comentário.
3. Se o status não for verde e não houver risco/problema em aberto para
   aquele pilar, o formulário de risco é exibido e deve ser preenchido para
   poder salvar.
4. Ao salvar, o Painel e o histórico do cliente são atualizados
   imediatamente — incluindo o recálculo instantâneo do Score Consolidado e
   do RAG Geral do cliente; a transição de status (anterior → novo) fica
   registrada na Auditoria.

### 8.3 Encerrar um Risco/Problema
1. Na aba Riscos & Problemas → Em Aberto, muda o status para "Fechado".
2. Modal pede a nota de encerramento (obrigatória).
3. Item passa para a aba Encerrados, com duração calculada e nota visível.

### 8.4 Conceder acesso a um novo membro do time
1. Admin ou BU Director com acesso full vai em Admin → Pessoas.
2. Cadastra a pessoa (nome, papel, e-mail) → sistema já gera senha padrão e
   marca para trocar no primeiro login.
3. Em Admin → Clientes, vincula essa pessoa como AM/DM do(s) cliente(s)
   correspondente(s).

---

## 9. Auditoria

Toda alteração relevante do sistema é registrada automaticamente:
criação/edição de clientes, criação/edição de pessoas, toda atualização de
status RAG (incluindo o **status anterior**, quando existente — ex: "Pilar
Faturamento: G → A" — ou a marcação de primeira definição, quando o pilar
ainda não tinha histórico), criação/edição/encerramento de riscos e
problemas, edição de critérios, troca/reset de senha. Cada registro traz
**quem** fez, **quando**, em **qual entidade**, **qual ação**, e um resumo
legível do que mudou (`campo: valor antigo → valor novo`). Consultável em
Admin → Auditoria, com filtro por tipo de entidade e busca livre.

---

## 10. Resumo Executivo Diário por Email

Todos os dias, às **6h da manhã (horário de Brasília)**, o sistema envia
automaticamente um email de resumo executivo cobrindo as **últimas 24
horas** de atividade no sistema, para o endereço
`marcos.andersen@sysmanager.com.br`.

O email consolida, em seções separadas:

- **Mudanças de status**: cada mudança de status de pilar ocorrida no
  período, mostrando o cliente, a transição (status anterior → novo status,
  no mesmo formato usado na Auditoria), quem fez e quando.
- **Riscos & problemas**: toda criação, edição ou encerramento de
  Risco/Problema no período, com cliente, ação, detalhes, autor e horário.
- **Outras alterações administrativas**: edições de clientes, pessoas e
  critérios feitas no período (trocas/resets de senha são excluídos deste
  bloco, por não serem alterações de negócio).
- **Acessos por usuário**: contagem de logins de cada pessoa no período,
  com papel, número de acessos, e horário do primeiro e do último login do
  dia — uma visão de quem de fato está usando o sistema.

Se não houver nenhuma alteração no período, o email é enviado mesmo assim,
com uma mensagem indicando que não houve mudanças (para confirmar que a
rotina automática continua funcionando). O envio é feito por um endpoint
protegido, disparado apenas pelo agendador (cron) da própria hospedagem —
não é acessível publicamente nem disparável por usuários da aplicação.

---

## 11. Favicon e Identidade Visual

A aba do navegador exibe a marca (brand mark) da SysManager como ícone,
em vez do ícone padrão do navegador.

---

## 12. Requisitos Não-Funcionais

- **Performance**: carregamento do Painel em ~100-150ms em uso normal
  (otimizado a partir de um problema inicial de ~19s — ver Documentação
  Técnica).
- **Responsividade**: interface utilizável em desktop e mobile (iPhone),
  incluindo tabelas largas com rolagem horizontal e coluna fixa.
- **Segurança**: senhas com hash forte (nunca em texto plano), sessões com
  expiração, controle de acesso reforçado no servidor (não só na tela),
  trilha de auditoria completa.
- **Disponibilidade**: hospedado na Vercel (função serverless) + Neon
  (Postgres gerenciado) — sem infraestrutura própria para manter.
- **Idioma**: interface e dados em Português (Brasil).

---

## 13. Glossário

| Termo | Significado |
|---|---|
| **RAG** | Red/Amber/Green — semáforo de status (aqui: Vermelho/Âmbar/Verde) |
| **BU Director** | Diretor de Business Unit — responsável executivo por um conjunto de clientes |
| **AM** | Account Manager — gestor comercial/relacionamento do cliente |
| **DM** | Delivery Manager — gestor de entrega/operação do contrato |
| **Pilar** | Cada uma das 8 dimensões de análise avaliadas por cliente (Faturamento, Receita, Margem, Prazo, Escopo, RH, CSAT, Contrato) |
| **Categoria** | Agrupamento de exibição dos 8 pilares em 4 grupos: Financeiro, Execução, Pessoas, Relacionamento |
| **Faturamento** | Pilar que mede a saúde operacional/de caixa do contrato (nota fiscal emitida e paga em dia) |
| **Receita** | Pilar que mede a saúde comercial/de previsão da conta (receita realizada vs. meta/orçamento, com sinal de persistência para 2+ meses de queda) |
| **Peso** | Relevância percentual de cada pilar no cálculo do Score Consolidado (soma sempre 100%) |
| **Dono** | Área/equipe responsável por agir quando um pilar está Âmbar ou Vermelho |
| **Score Consolidado** | Nota de 0 a 100 do cliente, média ponderada da pontuação (G=100/A=50/R=0) de todos os pilares pelo seu peso |
| **RAG Geral** | Status executivo único do cliente (G/A/R), derivado do Score Consolidado com override absoluto para Vermelho caso qualquer pilar esteja em R |
| **Alerta** | Sinalização automática, informativa e não-bloqueante, sobre padrões de risco que a média isolada do Score não evidenciaria |
| **Acesso full** | Permissão que concede acesso total ao módulo Admin e a todos os clientes, independente do papel operacional da pessoa |
| **Critérios** | Régua de referência que define o que qualifica cada pilar como G/A/R |
| **Resumo executivo diário** | Email automático enviado todo dia às 6h (Brasília) com as mudanças das últimas 24 horas |
