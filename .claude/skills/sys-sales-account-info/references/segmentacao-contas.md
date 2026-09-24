# Estrutura de Segmentação de Clientes e Potenciais Clientes

> **Versão:** 1.1  
> **Data:** 24/09/2026  
> **Autor:** SysManager — CBO Office  
> **Escopo:** Clientes e prospects das verticais E&U, O&G, BFSI e GOV  
> **Referência:** Gartner — *Market Definitions and Methodology: Vertical Industries* (framework de 12 indústrias primárias / 39 secundárias)

---

## 1. Princípio Fundamental

Como provedor de serviços de tecnologia, a SysManager se beneficia de um **modelo de segmentação bidimensional**: setor vertical combinado com tipo de propriedade. Esse modelo captura *quem são os compradores* e *como eles compram* — o que é fundamental para personalizar a abordagem de entrada no mercado, o posicionamento da solução e o engajamento de vendas.

Esse modelo é alinhado à taxonomia Gartner (*Market Definitions and Methodology: Vertical Industries*), que estabelece uma estrutura de **12 indústrias primárias (Nível 1)** e **39 indústrias secundárias (Nível 2)** para garantir análise de mercado consistente e categorização de clientes comparável com benchmarks globais.

A segmentação opera em **duas dimensões independentes e obrigatórias**:

- **Industry (Setor Vertical)** — o que a empresa *faz* (core business, workflows específicos e requisitos regulatórios — independente de quem a controla)
- **Ownership (Tipo de Propriedade)** — quem *controla* a empresa, o que determina fundamentalmente o comportamento de compra e os requisitos de aquisição

> ⚠️ **Regra de ouro:** Ownership nunca sobrescreve Industry. Uma empresa estatal que opera como banco é classificada como **BFSI + SOE**, não como GOV.

### Por que as duas dimensões são necessárias?

Cada setor vertical possui requisitos específicos de software e serviços — fluxos de trabalho, regulamentações e necessidades de automação exclusivas. Isso define **o que vender e como posicionar**.

O tipo de propriedade gera comportamentos de compra fundamentalmente diferentes — estruturas de conformidade, regras de aquisição, ciclos orçamentários e critérios de decisão distintos. Isso define **como vender e com quem engajar**.

---

## 2. Dimensão 1 — Industry / Setor Vertical

Baseada na taxonomia Gartner de indústrias verticais. Cada vertical possui workflows, requisitos regulatórios e desafios de conformidade exclusivos — que moldam diretamente os serviços a oferecer e como posicioná-los.

| Código | Indústria | Critério objetivo |
|---|---|---|
| **E&U** | Energy & Utilities | Geração, transmissão e distribuição de energia elétrica; saneamento; gás canalizado |
| **O&G** | Oil & Gas | Exploração, produção, refino e distribuição de petróleo e gás natural |
| **BFSI** | Banking, Financial Services & Insurance | Bancos, seguradoras, gestoras de investimento, fintechs, corretoras, previdência |
| **GOV** | Government & Public Sector | Administração pública direta: ministérios, secretarias, autarquias, fundações públicas sem operação comercial |

### 2.1 Perfil por Vertical — Drivers de Serviço e Posicionamento

#### Energy & Utilities (E&U)
- **Workflows distintos:** gestão de rede (grid management), integração de energias renováveis, monitoramento de ativos distribuídos
- **Regulação-chave (Brasil):** ANEEL, ONS, ANTT; equivalentes globais: FERC e NERC
- **Drivers de compra:** confiabilidade operacional, eficiência de rede, conformidade regulatória, transição energética
- **Posicionamento SysManager:** soluções para automação de operações, integração de sistemas legados e plataformas de gestão de ativos

#### Oil & Gas (O&G)
- **Workflows distintos:** integração upstream/downstream, gestão de ativos intensivos de capital, rastreabilidade de produção
- **Regulação-chave (Brasil):** ANP, legislação ambiental IBAMA, Lei das Estatais (13.303) para SOEs
- **Drivers de compra:** eficiência operacional, conformidade ambiental, redução de custos de manutenção, digitalização de campo
- **Posicionamento SysManager:** sistemas de gestão de operações, integração de dados industriais, soluções de field service

#### Banking, Financial Services & Insurance (BFSI)
- **Workflows distintos:** varia por tipo de licença, porte de ativos e segmento de clientes (varejo vs. corporate vs. investimentos)
- **Regulação-chave (Brasil):** BACEN, CVM, SUSEP, PREVIC; Resolução CMN, open finance, LGPD
- **Drivers de compra:** conformidade regulatória, segurança e prevenção a fraudes, experiência digital do cliente, eficiência de processos
- **Posicionamento SysManager:** modernização de core bancário, automação de processos, plataformas de dados e analytics, compliance

#### Government & Public Sector (GOV)
- **Workflows distintos:** prestação de serviços públicos, gestão de políticas, controle orçamentário, transparência e auditoria
- **Regulação-chave (Brasil):** Lei 14.133 (licitações), LGPD setor público, TCU, CGU, controles internos
- **Drivers de compra:** eficiência operacional, redução de custos, melhoria de serviços ao cidadão, conformidade e transparência
- **Posicionamento SysManager:** transformação digital de serviços públicos, modernização de sistemas legados, plataformas de gestão

### 2.2 Sub-indústrias (campo complementar no CRM)

| Industry | Sub-Industry |
|---|---|
| E&U | Geração / Transmissão / Distribuição / Saneamento / Gás Canalizado / Renováveis |
| O&G | E&P (Exploração & Produção) / Midstream / Refino / Distribuição / Trading |
| BFSI | Banco Comercial / Banco de Desenvolvimento / Seguradora / Gestora / Fintech / Previdência / Corretora |
| GOV | Federal / Estadual / Municipal / Autarquia / Agência Reguladora / Empresa Pública Adm. Direta |

---

## 3. Dimensão 2 — Ownership / Tipo de Propriedade

O tipo de propriedade gera **comportamentos de compra e requisitos de aquisição fundamentalmente diferentes**. É a dimensão que determina como engajar, quando entrar no ciclo e quais argumentos usar.

| Código | Tipo | Critério objetivo |
|---|---|---|
| **PRI** | Private | Controle acionário majoritário privado (nacional ou estrangeiro) com operação comercial |
| **SOE** | State-Owned Enterprise | Controle acionário majoritário do Estado (federal, estadual ou municipal) com operação comercial |
| **PUB** | Public Administration | Administração pública direta — orçamento público, sem fins lucrativos, sem operação comercial |
| **PPP** | Mixed / PPP | Controle compartilhado público-privado, ou concessão com forte regulação e participação estatal |

### 3.1 Perfil por Tipo de Propriedade — Comportamento de Compra e Sinais de GTM

#### PUB — Setor Público (Administração Direta)
**Inclui:** agências governamentais federais, estaduais e municipais; autarquias; fundações públicas

**Características únicas:**
- Estruturas de conformidade obrigatórias (Lei 14.133, TCU, CGU)
- Processos de aquisição formais: licitações, RFPs, compras cooperativas
- Ciclos orçamentários plurianuais — decisões vinculadas ao PPA/LOA
- Foco em missão pública, não em lucro ou diferenciação competitiva

**Sinais de entrada no mercado (GTM):**
- Engajar cedo nos ciclos orçamentários e de planejamento
- Posicionar a parceria como de longo prazo e alinhada à missão institucional
- Enfatizar conformidade, sustentabilidade de custos e eficiência operacional
- Documentar ROI comprovado com dados e casos de uso do setor público
- Monitorar editais e pregões eletrônicos como sinal de demanda

---

#### PRI — Setor Privado
**Inclui:** empresas comerciais com fins lucrativos, nacionais ou multinacionais, em qualquer setor

**Características únicas:**
- Foco em agilidade, inovação e diferenciação competitiva
- Decisão orientada por ROI concreto e time-to-value
- Ciclos de venda mais rápidos; decisão compartilhada entre líderes de negócio e TI
- Maior tolerância a risco em troca de vantagem competitiva

**Sinais de entrada no mercado (GTM):**
- Posicionar serviços em torno de agilidade, escalabilidade e vantagem competitiva
- Liderar com resultados de negócio e retorno sobre investimento mensurável
- Engajar simultaneamente o sponsor de negócio e o CTO/CIO
- Ciclos mais curtos permitem maior cadência de contato e avanço de oportunidade

---

#### SOE — Empresa Estatal com Operação Comercial
**Inclui:** empresas controladas pelo Estado que operam em mercados comerciais (Petrobras, Banco do Brasil, Cemig, Sabesp, etc.)

**Características únicas:**
- Combinam governança do setor público com pressão por performance do setor privado
- Sujeitas à Lei das Estatais (13.303/2016) — regulamento interno de licitações
- Decisão influenciada por conselho com representantes do Estado e do mercado
- Alta burocracia, mas tickets elevados e contratos de longa duração

**Sinais de entrada no mercado (GTM):**
- Tratar como híbrido: conformidade como requisito de entrada, ROI como argumento de convencimento
- Mapear a estrutura de governança (conselho, diretoria, comitê de tecnologia)
- Engajar tanto o nível técnico quanto o executivo com argumentos distintos
- Ciclos longos — construir relacionamento antes da abertura formal do processo

---

#### PPP — Parceria Público-Privada / Controle Misto
**Inclui:** concessões com execução privada e regulação estatal, empresas em processo de privatização, modelos híbridos (ex: Eletrobras, Sabesp pós-desestatização)

**Características únicas:**
- Exigem conciliar requisitos de conformidade pública com demanda por inovação privada
- Complexidade de governança: múltiplos stakeholders com agendas distintas
- Risco compartilhado entre os parceiros público e privado
- Contratos de concessão como marco regulatório da relação

**Sinais de entrada no mercado (GTM):**
- Demonstrar capacidade simultânea de conformidade regulatória e inovação
- Enfatizar modularidade e flexibilidade para atender a múltiplos stakeholders
- Preparar-se para requisitos complexos de gestão de fornecedores e interoperabilidade
- Identificar qual "lado" (público ou privado) tem maior poder decisório no momento

---

## 4. Regra de Precedência — Ordem de Classificação

```
1. Classificar pela INDUSTRY (o que a empresa faz)
2. Marcar o OWNERSHIP (quem controla)
3. Registrar a Sub-Industry (granularidade comercial)
4. Validar nas fontes da verdade (ver Seção 7)
```

> A industry determina a **vertical comercial** (qual time cuida, qual proposta de valor, quais referências usar).  
> O ownership determina o **processo de compra** (licitação, procurement privado, governança mista).

---

## 5. Exemplos de Classificação

| Empresa | Industry | Ownership | Justificativa |
|---|---|---|---|
| Banco do Brasil | **BFSI** | SOE | Opera como banco comercial; regulado pelo BACEN; compra core bancário, não serviços de governo |
| Caixa Econômica Federal | **BFSI** | SOE | Banco público, mas com operação comercial e regulação BACEN |
| Banco do Nordeste (BNB) | **BFSI** | SOE | Banco de desenvolvimento; regulado pelo BACEN |
| Petrobras | **O&G** | SOE | E&P, refino e distribuição de petróleo e gás; regulado pela ANP |
| Transpetro | **O&G** | SOE | Midstream (transporte e armazenamento de derivados); subsidiária da Petrobras |
| TBG / NTS | **O&G** | PRI / PPP | Midstream (gasodutos); mesmo critério de classificação que Transpetro |
| ENEVA | **E&U** | PRI | Geração térmica a gás natural; regulada pela ANEEL; E&P de gás é insumo, não produto final |
| ELERA Renováveis | **E&U** | PRI | Geração renovável 100% (solar, eólica, hidro, biomassa); subsidiária da Brookfield |
| Eletrobras | **E&U** | PPP | Geração e transmissão; pós-privatização com golden share da União |
| Sabesp | **E&U** | PPP | Saneamento; controle acionário misto pós-desestatização parcial |
| Cemig / Copel | **E&U** | SOE | Distribuidoras estaduais de energia; controle dos respectivos estados |
| Porto Seguro | **BFSI** | PRI | Seguradora privada |
| XP Inc. | **BFSI** | PRI | Gestora/corretora; listada na Nasdaq |
| Ministério da Saúde | **GOV** | PUB | Administração pública federal direta |
| ANATEL / ANEEL / ANP | **GOV** | PUB | Agências reguladoras — autarquias federais |
| Prefeitura de São Paulo | **GOV** | PUB | Administração pública municipal direta |

---

## 6. Fontes da Verdade — Como Validar a Classificação

### 6.1 Para Industry

| Fonte | O que valida | Como acessar |
|---|---|---|
| **B3 / CVM** | Setor e subsetor oficial para empresas listadas | [b3.com.br](https://www.b3.com.br) → Empresas Listadas |
| **CNAE (Receita Federal)** | Código de atividade econômica principal pelo CNPJ | [cnpj.info](https://cnpj.info) ou [receita.fazenda.gov.br](https://www.receita.fazenda.gov.br) |
| **Site Institucional / RI** | Auto-declaração da empresa — confirma posicionamento de mercado | Site da empresa → Relações com Investidores |
| **GICS / Bloomberg** | Para multinacionais ou benchmarking com peers globais | Bloomberg Terminal ou MSCI GICS framework |

### 6.2 Para Ownership

| Fonte | O que valida | Como acessar |
|---|---|---|
| **CVM — Formulário de Referência** | Composição acionária oficial para S.A. abertas | [cvm.gov.br](https://www.cvm.gov.br) → Consulta a Companhias |
| **Receita Federal / Econodata** | Natureza jurídica e QSA (quadro societário) pelo CNPJ | [econodata.com.br](https://www.econodata.com.br) |
| **DEST (Planejamento Federal)** | Lista oficial de estatais federais | [dest.planejamento.gov.br](https://www.dest.planejamento.gov.br) |
| **Portais estaduais / municipais** | Estatais estaduais e municipais | Site da Secretaria de Fazenda ou Gestão do respectivo ente |

> **Fonte primária recomendada:** CNPJ via Receita Federal (natureza jurídica + CNAE principal) + B3/CVM para empresas listadas. O Econodata cobre bem essa camada como ponto de partida.

---

## 7. Campos no CRM (Modelo de Dados)

```
Account
├── Industry          → [E&U | O&G | BFSI | GOV | Other]
├── Sub_Industry      → [ver tabela 2.1]
├── Ownership         → [PRI | SOE | PUB | PPP]
├── CNPJ              → campo para lookup e validação
├── Listed_B3         → [Sim | Não]
├── Regulatory_Body   → [ANEEL | ANP | BACEN | TCU | SUSEP | ...]
└── Classification_Source → [B3 | CVM | CNAE | Manual]
```

---

## 8. Impacto Comercial por Combinação

| Industry + Ownership | Implicações para a venda |
|---|---|
| E&U + SOE | Processo via licitação (Lei 14.133 ou regulamento interno); decisão influenciada por governo estadual/federal |
| E&U + PRI | Procurement privado; decisão técnica + financeira; velocidade maior |
| O&G + SOE | Alta governança; processo formal; ticket alto; ciclo longo |
| O&G + PRI | Mais ágil; foco em ROI e eficiência operacional |
| BFSI + SOE | Banco público: licitação possível, mas há pregão eletrônico e dispensa para TI; regulação BACEN exige compliance rigoroso |
| BFSI + PRI | RFP estruturada; critérios técnicos e de segurança predominam |
| GOV + PUB | Obrigatoriamente licitação; orçamento público; ciclo orçamentário anual |
| E&U + PPP | Híbrido: pode ter procurement privado com aprovação de conselho com representantes do poder público |

---

## 9. Casos Especiais e Critérios de Desempate

### Empresa atua em mais de uma indústria?
Classificar pela **atividade que representa a maior parcela da receita** e registrar a secundária no campo `Sub_Industry` ou em nota.

### Empresa em transição de controle (ex: privatização em curso)?
Usar o ownership **atual e vigente** na data da classificação. Registrar no campo `Classification_Source` a data de referência.

### Holding com subsidiárias em múltiplos setores?
Classificar a **subsidiária com quem a SysManager se relaciona comercialmente**, não a holding.

### Empresa estrangeira sem CNPJ?
Usar o equivalente do país de origem (SEC para EUA, Companies House para UK) + posicionamento de mercado declarado.

---

## 10. Referências

- **Gartner** — *Market Definitions and Methodology: Vertical Industries* — framework de 12 indústrias primárias e 39 secundárias para análise e categorização de mercado
- **B3 / CVM** — classificação oficial de setores para empresas listadas no Brasil
- **CNAE / Receita Federal** — código de atividade econômica para validação por CNPJ
- **DEST / Planejamento Federal** — lista oficial de estatais federais brasileiras
- **MSCI GICS** — Global Industry Classification Standard, referência global para benchmarking

---

## 11. Glossário

| Termo | Definição |
|---|---|
| **Industry** | Setor de negócio baseado no core business da empresa |
| **Ownership** | Natureza do controle acionário |
| **SOE** | State-Owned Enterprise — empresa com controle estatal e operação comercial |
| **PUB** | Administração pública direta — sem fins lucrativos, financiada por orçamento público |
| **PPP** | Parceria Público-Privada ou empresa de controle misto |
| **CNAE** | Classificação Nacional de Atividades Econômicas — código da Receita Federal |
| **GICS** | Global Industry Classification Standard — framework MSCI/S&P |
| **Gartner Vertical Taxonomy** | Estrutura Gartner de 12 indústrias primárias (Nível 1) e 39 secundárias (Nível 2) para categorização padronizada de mercado |
| **GTM** | Go-to-Market — estratégia de entrada no mercado, incluindo posicionamento, canais e abordagem de vendas |
| **Time-to-value** | Tempo entre a contratação e a realização do primeiro resultado mensurável para o cliente |
| **Upstream / Downstream** | Upstream: exploração e produção de petróleo/gás; Downstream: refino, distribuição e venda ao consumidor final |
| **QSA** | Quadro de Sócios e Administradores — documento da Receita Federal |
| **Golden Share** | Ação especial que dá ao Estado poder de veto em decisões estratégicas, mesmo sem controle majoritário |
| **Midstream** | Segmento de O&G focado em transporte, armazenamento e processamento (entre E&P e distribuição final) |
