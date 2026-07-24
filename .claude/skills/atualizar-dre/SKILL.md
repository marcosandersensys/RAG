---
name: atualizar-dre
description: Atualiza os dados do DRE Gerencial (Power BI) armazenados no RAG Status — pede o período e o cliente (ou TODOS), extrai do Power BI ao vivo via navegador do usuário, faz backup das tabelas antes de sobrescrever, carrega os dados novos e, ao final, pergunta se o backup deve ser mantido ou apagado.
---

# Atualizar DRE (RAG Status ⇄ Power BI)

## Visão geral

Processo repetível para atualizar `dre_resumo` e `dre_cliente` (tabelas Postgres do
RAG Status, ver `api/index.py` SCHEMA) a partir do relatório Power BI "DRE Gerencial":

```
https://app.powerbi.com/groups/309057b8-9ce3-49bc-bdca-1e78b385fd5c/reports/80c2e641-9fa2-43f2-a810-c9c1830082ee/419452c1e80cd8ea3a4e?experience=power-bi
```

**Por que isso não é um script 100% automático**: o login no Power BI exige a sessão
Microsoft SSO já autenticada do usuário. O Claude nunca vê/armazena a senha — ele
dirige o navegador já logado do usuário (`mcp__claude-in-chrome__*`) e só a extração
é ao vivo; o resto (backup, delete-no-escopo, insert) é feito por
`scripts/dre_refresh.py`.

## Passo a passo

### 1. Perguntar o escopo ao usuário

Sempre pergunte, nesta ordem, antes de tocar em qualquer dado:

1. **Mês de início** — formato `MM/AAAA` (ex: `06/2026`)
2. **Mês de término** — formato `MM/AAAA` (ex: `12/2026`)
3. **Cliente específico ou TODOS** — se for um cliente, peça o nome exato do
   "Cliente Agrupado" no Power BI (não necessariamente igual ao nome no RAG Status —
   ver mapeamento de exceções abaixo)

Converta `MM/AAAA` → `AAAA-MM` (ex: `06/2026` → `2026-06`) para uso no restante do
processo — é o formato de `competencia` nas tabelas e no CLI do script.

### 2. Backup

```bash
DATABASE_URL="postgres://...neon.tech/neondb?sslmode=require" python3 scripts/dre_refresh.py backup
```

Anote o `BACKUP_SUFFIX` impresso (ex: `dre_20260724_153000`) — precisa dele nos
passos 5 e 7.

### 3. Extrair do Power BI (ao vivo, via navegador)

Reaproveite o padrão validado nesta mesma sessão (screenshot → clicar na coordenada
visível do checkbox → aguardar → `get_page_text` → conferir se o rótulo "Cliente
Agrupado"/"Linha de Negócio"/mês no texto extraído bate com o filtro pretendido antes
de registrar o valor):

- **Filtro de Mês/Ano**: use os filtros nativos "Ano"/"Mês"/"Trimestre" do relatório
  para restringir ao período pedido — não dependa de olhar so as colunas mensais da
  tabela, porque o Power BI oculta colunas totalmente zeradas (uma coluna ausente
  pode significar "fora do filtro" OU "zerada nesse mês dentro do filtro" — ambíguo
  sem checar o filtro de Mês/Ano diretamente).
- **Escopo = TODOS**: repita a sequência de 3 capturas (Total sem filtro, Linha de
  Negócio=Licenciamento, e Serviços = Total − Licenciamento por subtração) para o
  resumo, depois uma captura por cliente (`Cliente Agrupado`, `Linha de Negócio`=Todos)
  para `dre_cliente`, com Linha de Negócio sempre "Todos".
- **Escopo = 1 cliente**: só precisa da captura desse cliente para `dre_cliente`
  (não mexe em `dre_resumo`, que é agregado da empresa toda).
- **Nunca** tente Ctrl+clique / multi-seleção nos slicers — já causou um near-miss
  abrindo um menu de contexto com "Excluir" numa sessão anterior. Sempre
  uncheck-then-check um item por vez.
- Sempre limpe (uncheck) o filtro anterior antes de aplicar o próximo, e ao final
  do processo deixe **todos os filtros em "Todos"** antes de fechar/deixar a aba.
- Reconcilie campos em branco por aritmética sempre que possível: Margem Bruta $ =
  Receita Líquida + Custo de Pessoal + Custo de Licença + Outros Custos — usado
  nesta sessão para atribuir corretamente um "Outros Custos" a um mês específico
  quando a tabela do Power BI omitiu a % (denominador zero).

**Exceções de mapeamento cliente Power BI ↔ RAG Status conhecidas até 2026-07-24**
(revalide a cada execução — a lista de clientes RAG e o "Cliente Agrupado" do Power
BI podem mudar):
- **"Petrobras"** no Power BI é um único valor combinado; no RAG Status existem 3
  contratos separados ("Petrobras - Lote B", "Lote C", "Plataforma"). Só dá pra
  obter o total combinado — grave a mesma linha `dre_cliente` sob o nome
  `"Petrobras"` e avise o usuário que não é possível quebrar por lote.
- **"LG", "SABESP", "SAMARCO"** não existem na dimensão "Cliente Agrupado" do Power
  BI (confirmado via busca no slicer) — sem dados, marque como tal no resultado, não
  insira linha nenhuma para esses.
- **"Fanvision", "OutSystems", "Red Hat"** aparecem no Power BI mas **não são**
  clientes RAG Status — ignore mesmo que apareçam no slicer.
- **"Panvision", "Google"** SÃO clientes RAG Status apesar do nome não-óbvio — não
  pule.

Para cada mês/valor faltante em `Jun/26+` (ou qualquer mês futuro sem dado ainda no
Power BI): grave `valor_planejado=NULL, valor_realizado=NULL` (deixar em branco —
decisão já validada com o usuário na primeira execução deste processo).

Para `Jan-Mai/2026` (primeira carga): `valor_planejado = valor_realizado` (decisão
já validada — meses já fechados, sem orçado separado disponível ainda).
**A partir da 2ª execução deste processo**, se o usuário tiver um valor de
Planejado diferente do Realizado para algum mês, pergunte explicitamente — não
assuma mais a igualdade por padrão.

### 4. Montar o JSON de carga

Formato esperado por `scripts/dre_refresh.py load --input <arquivo>.json`:

```json
{
  "resumo": [
    {"escopo": "total", "linha_dre": "Receita Bruta", "competencia": "2026-06", "valor_planejado": null, "valor_realizado": null},
    {"escopo": "licenciamento", "linha_dre": "Receita Bruta", "competencia": "2026-06", "valor_planejado": null, "valor_realizado": null},
    {"escopo": "servicos", "linha_dre": "Receita Bruta", "competencia": "2026-06", "valor_planejado": null, "valor_realizado": null}
  ],
  "cliente": [
    {"cliente_nome": "Nubank", "metrica": "Receita Bruta", "competencia": "2026-06", "valor_planejado": null, "valor_realizado": null}
  ]
}
```

`linha_dre`/`metrica` usam o nome exato da linha do DRE (ex: `"Receita Bruta"`,
`"Receita Líquida"`, `"Custo de Pessoal"`, `"Custo de Licença"`, `"Outros Custos"`,
`"Margem Bruta $"`, `"Margem Bruta %"`, e para `dre_resumo` também as linhas
adicionais do DRE completo: `"Imposto sobre Receita"`, `"Despesas de Pessoal"`,
`"Despesa Gerais"`, `"Despesa com Ocupação"`, `"Serviços de Terceiros"`, `"Ações de
Marketing"`, `"EBITDA $"`, `"Resultado Financeiro"`, `"Resultado Antes do
Imposto"`, `"Imposto Sobre o Resultado"`, `"Lucro Líquido $"`).

`dre_cliente` usa só as 7 métricas: Receita Bruta, Receita Líquida, Custo de
Pessoal, Custo de Licença, Outros Custos, Margem Bruta $, Margem Bruta %.

Se o escopo pedido for **um cliente específico**, o array `resumo` fica vazio
(`[]`) — não mexa no resumo agregado da empresa por engano.

### 5. Carregar

```bash
DATABASE_URL="..." python3 scripts/dre_refresh.py load \
    --mes-inicio 2026-06 --mes-fim 2026-12 \
    --cliente TODOS \
    --input /tmp/dre_carga.json
```

Isso **apaga** só as linhas dentro do escopo (competência × cliente) antes de
inserir — não toca em nada fora do período/cliente pedido.

### 6. Exibir o resultado

Mostre ao usuário um resumo do que foi carregado: quantas linhas em
`dre_resumo`/`dre_cliente`, período coberto, cliente(s) coberto(s), e qualquer
exceção encontrada (cliente sem dado no Power BI, Petrobras combinado, etc — reuse
a lista de exceções conhecidas acima e atualize-a se encontrar uma nova).

### 7. Perguntar sobre o backup

Pergunte explicitamente: **"Posso apagar o backup (`{BACKUP_SUFFIX}`), ou prefere
manter por enquanto?"**

- Se apagar:
  ```bash
  DATABASE_URL="..." python3 scripts/dre_refresh.py drop-backup --suffix {BACKUP_SUFFIX}
  ```
- Se manter: não faça nada — as tabelas de backup ficam no banco até uma execução
  futura pedir para apagá-las, ou até o usuário pedir explicitamente
  `restore-backup --suffix {BACKUP_SUFFIX}` caso algo dê errado.

## Tratamento de erros

| Situação | Ação |
|---|---|
| Screenshot trava/timeout no navegador | Abrir uma aba nova (`tabs_create_mcp`) e renavegar para a URL do relatório — resolveu no passado. |
| Clique num item errado do slicer (posição mudou após um toggle) | Sempre re-screenshot antes de clicar em vez de reusar coordenadas antigas; conferir o rótulo no `get_page_text` antes de gravar o valor. |
| Menu de contexto abrir (ex: "Excluir") por engano | Não clique em nada do menu — Escape / clicar fora imediatamente, avisar o usuário. |
| `get_page_text` retorna dado igual ao de outro filtro (stale read) | Re-chamar `get_page_text` mais uma vez — resolve na maioria dos casos. |
| Cliente não encontrado no slicer via busca | Confirmar com o usuário se o nome está correto/se o cliente realmente tem contrato ativo esse período antes de marcar como "sem dados". |
| `scripts/dre_refresh.py load` falhar no meio | As tabelas de backup ainda existem — rode `restore-backup` com o suffix do passo 2 antes de tentar de novo. |

## Checklist de conclusão

- [ ] Backup criado (suffix anotado)
- [ ] Extração cobriu exatamente o período e cliente(s) pedidos — nada a mais, nada a menos
- [ ] JSON de carga montado com Jan-Mai (ou período correspondente) Planejado=Realizado quando aplicável, ou perguntado ao usuário para períodos além da 1ª execução
- [ ] `dre_refresh.py load` rodado com sucesso
- [ ] Resultado exibido ao usuário (contagens, período, exceções)
- [ ] Usuário perguntado sobre manter/apagar o backup, e ação executada
- [ ] Todos os filtros do Power BI voltaram para "Todos" antes de encerrar
