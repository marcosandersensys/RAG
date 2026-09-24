---
name: sys-sales-account-info
description: Recebe o nome de uma conta (cliente ou prospect) e devolve a classificação de segmentação SysManager nas duas dimensões obrigatórias — Dimensão 1 Industry/Setor Vertical (Indústria, Sub-indústria, critério objetivo, drivers de serviço e posicionamento) e Dimensão 2 Ownership/Tipo de Propriedade (tipo, critério objetivo, comportamento de compra e sinais de GTM). Use sempre que o usuário pedir "info da conta", "classificar conta", "segmentar cliente/prospect", "qual a indústria/ownership de X", "perfil de compra de X", ou citar /sys-sales-account-info.
---

# Sales Account Info — Segmentação Industry × Ownership

## Visão geral

Classifica uma conta pelo **modelo bidimensional** da SysManager (CBO Office, v1.1),
alinhado à taxonomia Gartner de indústrias verticais:

- **Dimensão 1 — Industry**: o que a empresa *faz* → define **o que vender e como posicionar**
- **Dimensão 2 — Ownership**: quem *controla* a empresa → define **como vender e com quem engajar**

Fonte única da verdade para critérios, perfis e exemplos:
[`references/segmentacao-contas.md`](references/segmentacao-contas.md). **Leia esse
arquivo antes de classificar** — os textos de perfil (drivers, posicionamento,
características, sinais de GTM) devem ser copiados de lá, não reinventados.

> ⚠️ **Regra de ouro:** Ownership nunca sobrescreve Industry. Estatal que opera como
> banco = **BFSI + SOE**, não GOV.

## Entrada

- **Obrigatório:** nome da conta (ex: "Cemig", "Porto Seguro").
- **Opcional:** CNPJ, site, subsidiária específica com quem a SysManager se relaciona.

Se o nome for ambíguo (ex: "Eletrobras" holding vs. subsidiária; homônimos), pergunte
qual entidade antes de classificar — ou classifique a mais provável e declare a premissa.

## Passo a passo

### 1. Checar a tabela de exemplos (Seção 5 da referência)

Se a conta estiver listada, use a classificação de lá como ponto de partida — mas
ainda valide ownership atual (privatizações mudam o quadro).

### 2. Pesquisar evidências (fontes da verdade — Seção 6)

Use `WebSearch` / `WebFetch` para confirmar, nesta prioridade:

| Para | Fonte primária | Fallback |
|---|---|---|
| Industry | CNAE principal pelo CNPJ (Receita Federal / cnpj.info / Econodata); setor B3 para listadas | Site institucional / RI; GICS |
| Ownership | Natureza jurídica + QSA (Receita/Econodata); Formulário de Referência CVM para S.A. abertas | Lista DEST (estatais federais); portais estaduais/municipais |

Colete no mínimo: CNPJ (se BR), CNAE principal, natureza jurídica, acionista
controlador e % de controle, órgão regulador, se é listada na B3.
Sem acesso à web → classifique com conhecimento prévio e marque confiança **Baixa**.

### 3. Classificar na ordem de precedência (Seção 4)

1. **Industry** — pela atividade core (maior parcela da receita):
   - `E&U` geração/transmissão/distribuição de energia, saneamento, gás canalizado
   - `O&G` exploração, produção, refino, distribuição de petróleo e gás
   - `BFSI` bancos, seguradoras, gestoras, fintechs, corretoras, previdência
   - `GOV` administração pública direta sem operação comercial
   - `Other` se não se encaixar em nenhuma das quatro — declare a vertical Gartner
     mais próxima e sinalize que está **fora do foco** das verticais SysManager
     (nesse caso não há perfil de vertical na referência; diga isso em vez de inventar).
2. **Ownership** — pelo controle acionário **vigente hoje**:
   - `PRI` controle majoritário privado com operação comercial
   - `SOE` controle majoritário do Estado com operação comercial
   - `PUB` administração direta, orçamento público, sem operação comercial
   - `PPP` controle compartilhado / concessão com forte participação estatal / golden share
3. **Sub-Industry** — pela tabela 2.2 da referência.

### 4. Aplicar desempates (Seção 9)

- Multi-indústria → maior receita; secundária em nota.
- Privatização em curso → ownership atual; registrar data de referência.
- Holding → classificar a **subsidiária** com quem a SysManager se relaciona.
- Estrangeira sem CNPJ → equivalente do país (SEC, Companies House) + posicionamento declarado.
- Agências reguladoras (ANEEL, ANP, ANATEL…) → **GOV + PUB**, mesmo regulando E&U/O&G.

### 5. Montar a resposta no formato abaixo

## Formato de saída

```markdown
# <Nome da Conta> — Account Info

**Resumo:** <INDUSTRY> + <OWNERSHIP> · Sub-indústria: <Sub> · Confiança: <Alta|Média|Baixa>
<1 linha: o que a empresa faz e quem controla>

## Dimensão 1 — Industry / Setor Vertical

| Indústria | Sub-indústria | Critério objetivo |
|---|---|---|
| <Código — Nome> | <Sub-indústria> | <critério da referência> + evidência da conta (CNAE, setor B3, regulador) |

### Perfil por Vertical — Drivers de Serviço e Posicionamento
- **Workflows distintos:** <da referência 2.1>
- **Regulação-chave:** <da referência 2.1, destacando o regulador desta conta>
- **Drivers de compra:** <da referência 2.1>
- **Posicionamento SysManager:** <da referência 2.1>

## Dimensão 2 — Ownership / Tipo de Propriedade

| Tipo | Critério objetivo |
|---|---|
| <Código — Nome> | <critério da referência> + evidência da conta (controlador, % capital, natureza jurídica) |

### Perfil por Tipo de Propriedade — Comportamento de Compra e Sinais de GTM
**Características únicas:**
- <da referência 3.1>

**Sinais de entrada no mercado (GTM):**
- <da referência 3.1>

## Implicação comercial (Industry + Ownership)
<linha da tabela da Seção 8 para a combinação; se a combinação não estiver lá, derive
das duas dimensões e diga que é inferência>

## Campos CRM
Industry: <> · Sub_Industry: <> · Ownership: <> · CNPJ: <> · Listed_B3: <Sim|Não> ·
Regulatory_Body: <> · Classification_Source: <B3|CVM|CNAE|Manual> (<data de referência>)

## Fontes e ressalvas
- <fonte 1 com link> …
- <premissas, ambiguidades, pontos a validar>
```

## Regras de qualidade

- **Não invente dados.** CNPJ, % de controle ou CNAE não confirmados → escreva
  "não confirmado" e rebaixe a confiança.
- **Confiança:** Alta = industry e ownership confirmados em fonte primária;
  Média = uma das dimensões só por fonte secundária/RI; Baixa = sem verificação web.
- Perfis de vertical e ownership vêm **literalmente** da referência; a personalização
  para a conta vai no "Critério objetivo", na "Regulação-chave" e em "Implicação comercial".
- Seja crítico: se a conta for um caso de fronteira (ex: ENEVA E&U vs O&G; TBG/NTS
  PRI vs PPP), mostre o contraponto e a razão da escolha.
- Responda em português, direto e estruturado.
