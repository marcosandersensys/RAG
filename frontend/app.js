const PILAR_GRUPOS = [
  { label: "Financeiro", pilares: ["faturamento", "receita", "margem"] },
  { label: "Execução", pilares: ["prazo", "escopo"] },
  { label: "Pessoas", pilares: ["rh"] },
  { label: "Relacionamento", pilares: ["csat", "contrato"] },
];
const PILAR_ORDEM = PILAR_GRUPOS.flatMap(g => g.pilares);
const PILAR_LABELS = { faturamento: "Faturamento", receita: "Receita", margem: "Margem", prazo: "Prazo", escopo: "Escopo", rh: "RH", csat: "CSAT", contrato: "Contrato" };
const PILAR_LABELS_CURTO = { faturamento: "FAT", receita: "REC", margem: "GM%", prazo: "PRZ", escopo: "ESC", rh: "RH", csat: "CSAT", contrato: "CTR" };
const PILAR_CATEGORIA = Object.fromEntries(PILAR_GRUPOS.flatMap(g => g.pilares.map(p => [p, g.label])));
const PILAR_INICIO_CATEGORIA = new Set(PILAR_GRUPOS.map(g => g.pilares[0]));
const PILAR_PESO = { faturamento: 0.10, receita: 0.15, margem: 0.15, prazo: 0.10, escopo: 0.10, rh: 0.10, csat: 0.20, contrato: 0.10 };
const PILAR_DONO = {
  faturamento: "Delivery | FP&A", receita: "Delivery | FP&A", margem: "Delivery | FP&A",
  prazo: "Delivery", escopo: "Delivery",
  rh: "Delivery | RH",
  csat: "Account", contrato: "Account",
};
const PAPEL_LABELS = { bu_director: "BU Director", am: "AM", dm: "DM", admin: "Admin" };
const DIRECTOR_COLORS = ["var(--sys-magenta)", "var(--sys-blue)", "var(--sys-purple)"];

const state = {
  clientes: [],
  pessoas: [],
  riscos: [],
  criterios: [],
  auditoria: [],
  orgView: "cliente",
  adminView: "pessoas",
};

const session = {
  token: localStorage.getItem("rag-status:token") || null,
  pessoa: null,
};

// ---------- helpers ----------

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

function salvarToken(token) {
  session.token = token;
  if (token) localStorage.setItem("rag-status:token", token);
  else localStorage.removeItem("rag-status:token");
}

function limparSessao() {
  salvarToken(null);
  session.pessoa = null;
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (session.token) headers["Authorization"] = "Bearer " + session.token;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    limparSessao();
    mostrarLogin();
    throw new Error("Sessão expirada. Faça login novamente.");
  }
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch (e) { detail = null; }
    const err = new Error((detail && detail.message) || (typeof detail === "string" ? detail : `Erro ${res.status}`));
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

function fmtData(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

function fmtDataCurta(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

function fmtDataLonga(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function pessoasAtivas(papel) {
  return state.pessoas.filter(p => p.ativo && (!papel || p.papel === papel)).sort((a, b) => a.nome.localeCompare(b.nome));
}

async function popularSelectResponsavel(selectId, valorAtual) {
  if (!state.pessoas.length) state.pessoas = await api("/api/pessoas");
  const sel = document.getElementById(selectId);
  const pessoas = pessoasAtivas();
  const nomes = new Set(pessoas.map(p => p.nome));
  const opcaoExtra = valorAtual && !nomes.has(valorAtual)
    ? `<option value="${esc(valorAtual)}">${esc(valorAtual)} (não cadastrado/inativo)</option>`
    : "";
  sel.innerHTML = `<option value="">Selecione…</option>${opcaoExtra}` +
    pessoas.map(p => `<option value="${esc(p.nome)}">${esc(p.nome)} · ${PAPEL_LABELS[p.papel]}</option>`).join("");
  sel.value = valorAtual || "";
}

// ---------- tabs ----------

document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
  });
});

document.querySelector('.tab[data-view="riscos"]').addEventListener("click", loadRiscos);
document.querySelector('.tab[data-view="organizacao"]').addEventListener("click", renderOrgConteudo);
document.querySelector('.tab[data-view="admin"]').addEventListener("click", () => {
  loadAdminPessoas();
  loadAdminClientesTable();
  loadCriterios();
  loadAuditoria();
});

document.querySelectorAll('.org-toggle .subtab').forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll('.org-toggle .subtab').forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.orgView = btn.dataset.orgView;
    renderOrgConteudo();
  });
});

document.querySelectorAll('#view-admin > .subtabs .subtab').forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll('#view-admin > .subtabs .subtab').forEach(b => b.classList.remove("active"));
    document.querySelectorAll('#view-admin .subview').forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`admin-${btn.dataset.adminView}`).classList.add("active");
  });
});

// ---------- modal helpers ----------

function openModal(id) { document.getElementById(id).classList.add("open"); }
function closeModal(id) { document.getElementById(id).classList.remove("open"); }

document.querySelectorAll("[data-close-modal]").forEach(el => {
  el.addEventListener("click", () => closeModal(el.dataset.closeModal));
});
document.querySelectorAll(".modal-overlay").forEach(overlay => {
  overlay.addEventListener("click", (e) => {
    if (e.target !== overlay) return;
    if (overlay.id === "modal-trocar-senha" && overlay.dataset.forcada === "1") return;
    if (overlay.id === "modal-fechar-risco") reverterSelectFechamento();
    closeModal(overlay.id);
  });
});

// ---------- auth ----------

function mostrarLogin() {
  document.getElementById("app-shell").classList.add("hidden");
  closeModal("modal-trocar-senha");
  document.getElementById("view-login").classList.remove("hidden");
  document.getElementById("login-erro").classList.add("hidden");
  document.getElementById("login-senha").value = "";
}

function mostrarApp() {
  document.getElementById("view-login").classList.add("hidden");
  document.getElementById("app-shell").classList.remove("hidden");
  document.getElementById("topbar-user-nome").textContent = session.pessoa.nome;
  const temAcessoFull = session.pessoa.papel === "admin" || session.pessoa.acesso_full;
  document.getElementById("tab-admin").classList.toggle("hidden", !temAcessoFull);
  renderModeloPontuacao();
}

function mostrarTrocarSenha(forcada) {
  document.getElementById("ts-erro").classList.add("hidden");
  document.getElementById("ts-senha-atual").value = "";
  document.getElementById("ts-senha-nova").value = "";
  document.getElementById("ts-senha-confirmar").value = "";
  document.getElementById("ts-aviso").textContent = forcada
    ? "Este é o seu primeiro acesso (ou uma senha temporária foi definida). Defina uma nova senha para continuar."
    : "Defina uma nova senha.";
  document.getElementById("ts-fechar").classList.toggle("hidden", forcada);
  document.getElementById("ts-cancelar").classList.toggle("hidden", forcada);
  document.getElementById("modal-trocar-senha").dataset.forcada = forcada ? "1" : "0";
  openModal("modal-trocar-senha");
}

async function entrarNaAplicacao() {
  document.getElementById("view-login").classList.add("hidden");
  if (session.pessoa.precisa_trocar_senha) {
    mostrarTrocarSenha(true);
    return;
  }
  mostrarApp();
  await loadPainel();
}

async function fazerLogin() {
  const email = document.getElementById("login-email").value.trim();
  const senha = document.getElementById("login-senha").value;
  const erroEl = document.getElementById("login-erro");
  erroEl.classList.add("hidden");
  if (!email || !senha) {
    erroEl.textContent = "Informe email e senha.";
    erroEl.classList.remove("hidden");
    return;
  }
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, senha }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error((body.detail && body.detail.message) || body.detail || "Email ou senha inválidos.");
    }
    const data = await res.json();
    salvarToken(data.token);
    session.pessoa = data.pessoa;
    await entrarNaAplicacao();
  } catch (e) {
    erroEl.textContent = e.message;
    erroEl.classList.remove("hidden");
  }
}

async function submeterTrocaSenha() {
  const atual = document.getElementById("ts-senha-atual").value;
  const nova = document.getElementById("ts-senha-nova").value;
  const confirmar = document.getElementById("ts-senha-confirmar").value;
  const erroEl = document.getElementById("ts-erro");
  erroEl.classList.add("hidden");
  if (!atual || !nova) {
    erroEl.textContent = "Preencha todos os campos.";
    erroEl.classList.remove("hidden");
    return;
  }
  if (nova !== confirmar) {
    erroEl.textContent = "A confirmação não confere com a nova senha.";
    erroEl.classList.remove("hidden");
    return;
  }
  try {
    await api("/api/auth/trocar-senha", {
      method: "POST",
      body: JSON.stringify({ senha_atual: atual, senha_nova: nova }),
    });
    session.pessoa.precisa_trocar_senha = false;
    closeModal("modal-trocar-senha");
    mostrarApp();
    await loadPainel();
  } catch (e) {
    erroEl.textContent = e.message;
    erroEl.classList.remove("hidden");
  }
}

async function fazerLogout() {
  try { await api("/api/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
  limparSessao();
  mostrarLogin();
}

document.getElementById("login-entrar").addEventListener("click", fazerLogin);
["login-email", "login-senha"].forEach(id => {
  document.getElementById(id).addEventListener("keydown", (e) => { if (e.key === "Enter") fazerLogin(); });
});
document.getElementById("btn-logout").addEventListener("click", fazerLogout);
document.getElementById("btn-trocar-senha").addEventListener("click", () => mostrarTrocarSenha(false));
document.getElementById("ts-salvar").addEventListener("click", submeterTrocaSenha);

// ---------- load & render: PAINEL ----------

async function loadPainel() {
  const [clientes, resumo, pessoas] = await Promise.all([
    api("/api/clientes"),
    api("/api/dashboard/resumo"),
    api("/api/pessoas"),
  ]);
  state.clientes = clientes;
  state.pessoas = pessoas;
  renderResumoCards(resumo);
  populateFiltros(clientes);
  renderPainelSecoes();
}

function renderResumoCards(resumo) {
  const el = document.getElementById("resumo-cards");
  el.innerHTML = `
    <div class="summary-card"><div class="num">${resumo.total_clientes}</div><div class="label">Clientes ativos</div></div>
    <div class="summary-card ${resumo.clientes_criticos > 0 ? "alert" : ""}"><div class="num">${resumo.clientes_criticos}</div><div class="label">Clientes com pilar vermelho</div></div>
    <div class="summary-card ${resumo.riscos_abertos > 0 ? "alert" : ""}"><div class="num">${resumo.riscos_abertos}</div><div class="label">Riscos/Problemas em aberto</div></div>
    <div class="summary-card ${resumo.riscos_atrasados > 0 ? "alert" : ""}"><div class="num">${resumo.riscos_atrasados}</div><div class="label">Riscos/Problemas atrasados</div></div>
  `;
}

// ---------- Critérios de referência (help contextual no Painel) ----------

function criteriosTabelaHtml(criterios) {
  const grupos = new Map();
  criterios.forEach(c => {
    const key = `${c.pilar}|||${c.linha}`;
    if (!grupos.has(key)) grupos.set(key, { pilar: c.pilar, linha: c.linha, itens: {} });
    grupos.get(key).itens[c.status] = c;
  });
  const todosGrupos = [...grupos.values()];

  const linhaHtml = g => `
    <tr>
      <td><strong>${esc(PILAR_LABELS[g.pilar] || g.pilar)}</strong></td>
      <td>${esc(g.linha)}</td>
      ${["G", "A", "R"].map(s => `<td>${esc(g.itens[s] ? g.itens[s].descricao : "—")}</td>`).join("")}
    </tr>
  `;

  const linhas = PILAR_GRUPOS.map(cat => {
    const gruposCategoria = todosGrupos.filter(g => cat.pilares.includes(g.pilar));
    if (!gruposCategoria.length) return "";
    return `<tr class="criterios-categoria-row"><td colspan="5"><strong>${esc(cat.label)}</strong></td></tr>`
      + gruposCategoria.map(linhaHtml).join("");
  }).join("");

  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Pilar</th><th>Linha</th><th class="col-g">G</th><th class="col-a">A</th><th class="col-r">R</th></tr></thead>
        <tbody>${linhas}</tbody>
      </table>
    </div>
  `;
}

async function abrirCriteriosReferencia(pilarFoco) {
  document.getElementById("criterios-ref-titulo").textContent = "Critérios de Referência (G/A/R)";
  const criterios = await api("/api/criterios");
  const grupos = new Map();
  criterios.forEach(c => {
    if (!grupos.has(c.pilar)) grupos.set(c.pilar, new Map());
    const porLinha = grupos.get(c.pilar);
    if (!porLinha.has(c.linha)) porLinha.set(c.linha, {});
    porLinha.get(c.linha)[c.status] = c.descricao;
  });

  const pilarBlock = p => {
    const porLinha = grupos.get(p);
    if (!porLinha || !porLinha.size) return "";
    return `
      <div class="crit-ref-pilar" id="crit-ref-${p}">
        <h4>${esc(PILAR_LABELS[p])}</h4>
        ${[...porLinha.entries()].map(([linha, itens]) => `
          <div class="crit-ref-linha">
            <div class="crit-ref-linha-nome">${esc(linha)}</div>
            <div class="crit-ref-status"><span class="dot dot-g"></span>${esc(itens.G || "—")}</div>
            <div class="crit-ref-status"><span class="dot dot-a"></span>${esc(itens.A || "—")}</div>
            <div class="crit-ref-status"><span class="dot dot-r"></span>${esc(itens.R || "—")}</div>
          </div>
        `).join("")}
      </div>
    `;
  };

  const corpo = document.getElementById("criterios-ref-corpo");
  if (pilarFoco) {
    corpo.innerHTML = pilarBlock(pilarFoco) || `<p>Nenhum critério cadastrado para ${esc(PILAR_LABELS[pilarFoco] || pilarFoco)}.</p>`;
  } else {
    corpo.innerHTML = `<h4>Critérios (G/A/R) por Pilar</h4>${criteriosTabelaHtml(criterios)}`
      + modeloPontuacaoTabelaHtml() + regrasConsolidacaoHtml();
  }

  openModal("modal-criterios-ref");
}

document.getElementById("btn-ver-criterios").addEventListener("click", () => abrirCriteriosReferencia());

function populateFiltros(clientes) {
  const buSel = document.getElementById("filtro-bu-director");
  const industrySel = document.getElementById("filtro-industry");
  const currentBu = buSel.value;
  const currentIndustry = industrySel.value;

  const diretores = diretoresOrdenados();
  const industries = [...new Set(clientes.map(c => c.industry_code))].sort();

  buSel.innerHTML = `<option value="">BU Director (todos)</option>` +
    diretores.map(d => `<option value="${d.id}">${esc(d.nome)}</option>`).join("");
  industrySel.innerHTML = `<option value="">Industry Code (todos)</option>` +
    industries.map(i => `<option value="${esc(i)}">${esc(i)}</option>`).join("");

  buSel.value = currentBu;
  industrySel.value = currentIndustry;
}

function diretoresOrdenados() {
  return state.pessoas.filter(p => p.papel === "bu_director").sort((a, b) => a.id - b.id);
}

function directorColor(index) {
  return DIRECTOR_COLORS[index % DIRECTOR_COLORS.length];
}

function dmsLabel(dms) {
  return dms && dms.length ? dms.map(d => d.nome).join(", ") : "—";
}

function renderPainelSecoes() {
  const busca = document.getElementById("filtro-busca").value.trim().toLowerCase();
  const buDirectorId = document.getElementById("filtro-bu-director").value;
  const industry = document.getElementById("filtro-industry").value;
  const somenteNaoVerde = document.getElementById("filtro-somente-risco").value === "nao-verde";

  const linhas = state.clientes.filter(c => {
    if (buDirectorId && (!c.bu_director || String(c.bu_director.id) !== buDirectorId)) return false;
    if (industry && c.industry_code !== industry) return false;
    if (somenteNaoVerde && PILAR_ORDEM.every(p => c.pilares[p] === "G")) return false;
    if (busca) {
      const haystack = [c.nome, c.am && c.am.nome, ...(c.dms || []).map(d => d.nome)]
        .filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(busca)) return false;
    }
    return true;
  });

  const diretores = diretoresOrdenados();
  const container = document.getElementById("painel-secoes");

  if (linhas.length === 0) {
    container.innerHTML = `<div class="card"><div class="empty-state">Nenhum cliente encontrado com os filtros atuais.</div></div>`;
    return;
  }

  container.innerHTML = diretores.map((dir, idx) => {
    const clientesDoDir = linhas.filter(c => c.bu_director && c.bu_director.id === dir.id);
    if (clientesDoDir.length === 0) return "";
    const industrias = [...new Set(clientesDoDir.map(c => c.industry_code))].join(", ");

    return `
      <div class="bu-section">
        <div class="bu-section-header">
          <span class="bu-dot" style="background:${directorColor(idx)}"></span>
          <span class="bu-section-title">${esc(dir.nome)}</span>
          <span class="bu-section-meta">BU Director · ${esc(industrias)}</span>
        </div>
        <div class="card">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th rowspan="2">Cliente</th><th rowspan="2" class="col-ind">IND</th><th rowspan="2" class="col-mod">MOD</th>
                  <th rowspan="2" class="center">RAG<br>Geral <button type="button" class="th-help-rag-geral" title="Como o RAG Geral é calculado">?</button></th><th rowspan="2" class="center">Score</th>
                  ${PILAR_GRUPOS.map(g => `<th colspan="${g.pilares.length}" class="th-categoria divisor-categoria">${esc(g.label)}</th>`).join("")}
                  <th rowspan="2" class="col-am divisor-categoria">AM</th><th rowspan="2">DM</th>
                </tr>
                <tr class="th-pilar-row">
                  ${PILAR_ORDEM.map(p => `
                    <th title="${esc(PILAR_LABELS[p])}" class="${PILAR_INICIO_CATEGORIA.has(p) ? "divisor-categoria" : ""}">${PILAR_LABELS_CURTO[p]} <button type="button" class="th-help" data-pilar-help="${p}" title="Ver critérios de ${esc(PILAR_LABELS[p])}">?</button></th>
                  `).join("")}
                </tr>
              </thead>
              <tbody>
                ${clientesDoDir.map(c => `
                  <tr>
                    <td><span class="cliente-nome" data-cliente-id="${c.id}">${esc(c.nome)}</span></td>
                    <td class="col-ind"><span class="pill">${esc(c.industry_code)}</span></td>
                    <td class="col-mod">${fmtDataCurta(c.modificado)}</td>
                    <td class="center"><span class="badge-geral ${c.rag_geral.toLowerCase()}" title="${esc((c.alertas || []).join(" · "))}">${c.rag_geral}</span></td>
                    <td class="center">${c.score_consolidado}</td>
                    ${PILAR_ORDEM.map(p => `
                      <td class="center${PILAR_INICIO_CATEGORIA.has(p) ? " divisor-categoria" : ""}"><button class="badge-rag ${c.pilares[p].toLowerCase()}" data-cliente-id="${c.id}" data-pilar="${p}">${c.pilares[p]}</button></td>
                    `).join("")}
                    <td class="col-am divisor-categoria">${c.am ? esc(c.am.nome) : "—"}</td>
                    <td>${esc(dmsLabel(c.dms))}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  }).join("");

  container.querySelectorAll(".badge-rag").forEach(btn => {
    btn.addEventListener("click", () => openStatusModal(Number(btn.dataset.clienteId), btn.dataset.pilar));
  });
  container.querySelectorAll(".cliente-nome").forEach(el => {
    el.addEventListener("click", () => openClienteModal(Number(el.dataset.clienteId)));
  });
  container.querySelectorAll(".th-help").forEach(btn => {
    btn.addEventListener("click", (e) => { e.stopPropagation(); abrirCriteriosReferencia(btn.dataset.pilarHelp); });
  });
  container.querySelectorAll(".th-help-rag-geral").forEach(btn => {
    btn.addEventListener("click", (e) => { e.stopPropagation(); abrirRagGeralInfo(); });
  });
}

["filtro-busca", "filtro-bu-director", "filtro-industry", "filtro-somente-risco"].forEach(id => {
  document.getElementById(id).addEventListener("input", renderPainelSecoes);
  document.getElementById(id).addEventListener("change", renderPainelSecoes);
});

// ---------- modal: atualizar status ----------

let msSelectedStatus = null;

async function openStatusModal(clienteId, pilar) {
  const cliente = state.clientes.find(c => c.id === clienteId);
  if (!cliente) return;

  document.getElementById("ms-cliente-id").value = clienteId;
  document.getElementById("ms-pilar").value = pilar;
  document.getElementById("modal-status-titulo").textContent = `${cliente.nome} — ${PILAR_LABELS[pilar]}`;
  document.getElementById("ms-comentario").value = "";
  document.getElementById("ms-atualizado-por-hint").textContent = `Atualizado por ${session.pessoa.nome}`;
  document.getElementById("ms-erro").classList.add("hidden");
  document.getElementById("ms-r-titulo").value = "";
  document.getElementById("ms-r-descricao").value = "";
  await popularSelectResponsavel("ms-r-responsavel", "");
  document.getElementById("ms-r-plano").value = "";
  document.getElementById("ms-r-data-alvo").value = "";
  document.getElementById("ms-r-severidade").value = "media";
  document.getElementById("ms-r-tipo").value = "risco";

  msSelectedStatus = cliente.pilares[pilar];
  document.querySelectorAll("#ms-status-picker .status-opt").forEach(opt => {
    opt.classList.toggle("selected", opt.dataset.status === msSelectedStatus);
  });
  updateNovoRiscoVisibility();

  api(`/api/riscos?cliente_id=${clienteId}&pilar=${pilar}`).then(riscos => {
    const abertos = riscos.filter(r => r.status !== "fechado");
    const wrap = document.getElementById("ms-riscos-existentes");
    const lista = document.getElementById("ms-riscos-existentes-lista");
    if (abertos.length === 0) {
      wrap.classList.add("hidden");
      lista.innerHTML = "";
    } else {
      wrap.classList.remove("hidden");
      lista.innerHTML = abertos.map(r => `
        <div class="risco-existente-item">
          <span class="badge tipo-${r.tipo}">${r.tipo}</span>
          <strong>${esc(r.titulo)}</strong> — <span class="badge sev-${r.severidade}">${r.severidade}</span>
        </div>
      `).join("");
    }
  });

  openModal("modal-status");
}

document.querySelectorAll("#ms-status-picker .status-opt").forEach(opt => {
  opt.addEventListener("click", () => {
    msSelectedStatus = opt.dataset.status;
    document.querySelectorAll("#ms-status-picker .status-opt").forEach(o => o.classList.toggle("selected", o === opt));
    updateNovoRiscoVisibility();
  });
});

function updateNovoRiscoVisibility() {
  document.getElementById("ms-novo-risco").classList.toggle("hidden", msSelectedStatus === "G");
}

document.getElementById("ms-salvar").addEventListener("click", async () => {
  const clienteId = Number(document.getElementById("ms-cliente-id").value);
  const pilar = document.getElementById("ms-pilar").value;
  const erroEl = document.getElementById("ms-erro");
  erroEl.classList.add("hidden");

  if (!msSelectedStatus) { erroEl.textContent = "Selecione um status."; erroEl.classList.remove("hidden"); return; }

  const payload = {
    cliente_id: clienteId,
    pilar,
    status: msSelectedStatus,
    comentario: document.getElementById("ms-comentario").value.trim(),
  };

  if (msSelectedStatus !== "G") {
    const titulo = document.getElementById("ms-r-titulo").value.trim();
    if (titulo) {
      payload.risco = {
        cliente_id: clienteId,
        pilar,
        tipo: document.getElementById("ms-r-tipo").value,
        titulo,
        descricao: document.getElementById("ms-r-descricao").value.trim(),
        severidade: document.getElementById("ms-r-severidade").value,
        responsavel: document.getElementById("ms-r-responsavel").value.trim(),
        plano_mitigacao: document.getElementById("ms-r-plano").value.trim(),
        data_alvo: document.getElementById("ms-r-data-alvo").value || null,
      };
    }
  }

  try {
    await api("/api/status", { method: "POST", body: JSON.stringify(payload) });
    closeModal("modal-status");
    await loadPainel();
    if (document.getElementById("view-riscos").classList.contains("active")) await loadRiscos();
  } catch (e) {
    if (e.detail && e.detail.code === "RISK_REQUIRED") {
      erroEl.textContent = e.detail.message;
      erroEl.classList.remove("hidden");
      document.getElementById("ms-novo-risco").classList.remove("hidden");
    } else {
      erroEl.textContent = e.message;
      erroEl.classList.remove("hidden");
    }
  }
});

// ---------- modal: detalhe do cliente ----------

function renderClienteTimeline(historico, ragGeral) {
  const porPilar = new Map();
  PILAR_ORDEM.forEach(p => porPilar.set(p, []));
  historico.forEach(h => { if (porPilar.has(h.pilar)) porPilar.get(h.pilar).push(h); });
  // historico chega em ordem DESC (mais recente primeiro); inverte p/ ordem cronológica
  porPilar.forEach(arr => arr.reverse());

  const linhaGeral = `
    <div class="pilar-tl-row">
      <div class="pilar-tl-label" title="RAG Geral">GERAL</div>
      <div class="pilar-tl-track"><span class="badge-geral ${ragGeral.toLowerCase()}">${ragGeral}</span></div>
    </div>
  `;

  const pontos = [];
  const linhas = PILAR_ORDEM.map(p => {
    const entradas = porPilar.get(p);
    if (!entradas.length) {
      return `
        <div class="pilar-tl-row">
          <div class="pilar-tl-label" title="${esc(PILAR_LABELS[p])}">${PILAR_LABELS_CURTO[p]}</div>
          <div class="pilar-tl-track"><span class="pilar-tl-empty">Sem histórico</span></div>
        </div>
      `;
    }
    const itens = entradas.map((h, i) => {
      const idx = pontos.length;
      pontos.push(h);
      const ultimo = i === entradas.length - 1;
      return `
        <div class="pilar-tl-item">
          <button type="button" class="pilar-tl-dot ${h.status.toLowerCase()} ${ultimo ? "atual" : ""}" data-dot-idx="${idx}"></button>
          <div class="pilar-tl-date">${fmtData(h.atualizado_em)}</div>
        </div>
        ${!ultimo ? '<div class="pilar-tl-line"></div>' : ""}
      `;
    }).join("");
    return `
      <div class="pilar-tl-row">
        <div class="pilar-tl-label" title="${esc(PILAR_LABELS[p])}">${PILAR_LABELS_CURTO[p]}</div>
        <div class="pilar-tl-track">${itens}</div>
      </div>
    `;
  }).join("");

  document.getElementById("mc-timeline").innerHTML = linhaGeral + linhas;
  const detalheEl = document.getElementById("mc-timeline-detalhe");
  detalheEl.textContent = "Clique em um ponto da linha do tempo para ver os detalhes daquela medição.";

  document.querySelectorAll("#mc-timeline .pilar-tl-dot").forEach(dot => {
    dot.addEventListener("click", () => {
      document.querySelectorAll("#mc-timeline .pilar-tl-dot").forEach(d => d.classList.remove("selecionado"));
      dot.classList.add("selecionado");
      const h = pontos[Number(dot.dataset.dotIdx)];
      detalheEl.innerHTML = `
        <span class="badge-rag ${h.status.toLowerCase()}" style="width:20px;height:20px;font-size:10px;cursor:default">${h.status}</span>
        <strong>${PILAR_LABELS[h.pilar]}</strong> — ${fmtDataLonga(h.atualizado_em)} · ${esc(h.atualizado_por)}<br>
        ${esc(h.comentario || "Sem comentário registrado.")}
      `;
    });
  });
}

async function openClienteModal(clienteId) {
  const detalhe = await api(`/api/clientes/${clienteId}`);
  document.getElementById("mc-titulo").innerHTML = `
    ${esc(detalhe.nome)} · ${esc(detalhe.industry_code)}
    <span class="badge-geral ${detalhe.rag_geral.toLowerCase()}" style="margin-left:8px;vertical-align:middle" title="${esc((detalhe.alertas || []).join(" · "))}">${detalhe.rag_geral}</span>
  `;

  document.getElementById("mc-pilares").innerHTML = PILAR_ORDEM.map(p => `
    <div class="pilar-mini">
      <div class="lbl" title="${esc(PILAR_LABELS[p])}">${PILAR_LABELS_CURTO[p]}</div>
      <span class="badge-rag ${detalhe.pilares[p].toLowerCase()}">${detalhe.pilares[p]}</span>
    </div>
  `).join("");

  renderClienteTimeline(detalhe.historico, detalhe.rag_geral);

  document.getElementById("mc-equipe").innerHTML = `
    <div class="historico-item"><span><strong>BU Director</strong></span><span class="meta">${detalhe.bu_director ? esc(detalhe.bu_director.nome) : "—"}</span></div>
    <div class="historico-item"><span><strong>AM</strong></span><span class="meta">${detalhe.am ? esc(detalhe.am.nome) : "—"}</span></div>
    <div class="historico-item"><span><strong>DM(s)</strong></span><span class="meta">${esc(dmsLabel(detalhe.dms))}</span></div>
  `;

  const hist = detalhe.historico.slice(0, 30);
  document.getElementById("mc-historico").innerHTML = hist.length ? hist.map(h => `
    <div class="historico-item">
      <span><span class="badge-rag ${h.status.toLowerCase()}" style="width:18px;height:18px;font-size:9px;cursor:default">${h.status}</span>
      &nbsp;${PILAR_LABELS[h.pilar]} — ${esc(h.comentario || "sem comentário")}</span>
      <span class="meta">${esc(h.atualizado_por)} · ${fmtDataLonga(h.atualizado_em)}</span>
    </div>
  `).join("") : `<div class="empty-state">Sem histórico ainda.</div>`;

  document.getElementById("mc-riscos").innerHTML = detalhe.riscos.length ? detalhe.riscos.map(r => `
    <div class="historico-item historico-item-clicavel" data-mc-risco-id="${r.id}">
      <span><span class="badge tipo-${r.tipo}">${r.tipo}</span> ${PILAR_LABELS[r.pilar]} — <strong>${esc(r.titulo)}</strong>
      <span class="badge st-${r.status}">${r.status}</span></span>
      <span class="meta">${esc(r.responsavel || "—")}</span>
    </div>
  `).join("") : `<div class="empty-state">Nenhum risco/problema vinculado.</div>`;

  document.querySelectorAll("#mc-riscos [data-mc-risco-id]").forEach(el => {
    el.addEventListener("click", async () => {
      const riscoId = Number(el.dataset.mcRiscoId);
      if (!state.riscos.some(x => x.id === riscoId)) {
        state.riscos = await api("/api/riscos");
      }
      abrirEditarRisco(riscoId);
    });
  });

  openModal("modal-cliente");
}

// ---------- RISCOS & PROBLEMAS tab ----------

async function loadRiscos() {
  const pilar = document.getElementById("risco-filtro-pilar").value;
  const severidade = document.getElementById("risco-filtro-severidade").value;

  const params = new URLSearchParams();
  if (pilar) params.set("pilar", pilar);
  if (severidade) params.set("severidade", severidade);

  const riscos = await api(`/api/riscos?${params.toString()}`);
  state.riscos = riscos;
  renderTabelaRiscos();
}

function diasEntre(inicioIso, fimIso) {
  return Math.max(Math.round((new Date(fimIso) - new Date(inicioIso)) / 86400000), 0);
}

function renderTabelaRiscos() {
  const abertos = state.riscos.filter(r => r.status !== "fechado");
  const encerrados = state.riscos.filter(r => r.status === "fechado");

  document.getElementById("riscos-subtab-abertos").textContent = `Em Aberto (${abertos.length})`;
  document.getElementById("riscos-subtab-encerrados").textContent = `Encerrados (${encerrados.length})`;

  renderRiscosAbertos(abertos);
  renderRiscosEncerrados(encerrados);
}

function renderRiscosAbertos(abertos) {
  const tbody = document.getElementById("riscos-abertos-tbody");
  if (abertos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Nenhum risco/problema em aberto.</td></tr>`;
    return;
  }
  tbody.innerHTML = abertos.map(r => `
    <tr class="${r.atrasado ? "risco-atrasado" : ""}">
      <td>${esc(r.cliente_nome)}</td>
      <td>${PILAR_LABELS[r.pilar] || esc(r.pilar)}</td>
      <td><span class="badge tipo-${r.tipo}">${r.tipo}</span></td>
      <td>${esc(r.titulo)}</td>
      <td><span class="badge sev-${r.severidade}">${r.severidade}</span></td>
      <td>${esc(r.responsavel || "—")}</td>
      <td>${r.data_alvo ? esc(r.data_alvo) : "—"} ${r.atrasado ? '<span class="badge st-aberto">Atrasado</span>' : ""}</td>
      <td>${r.dias_aberto != null ? `${r.dias_aberto}d` : "—"}</td>
      <td>
        <select class="risco-status-select" data-risco-id="${r.id}">
          <option value="aberto" ${r.status === "aberto" ? "selected" : ""}>Aberto</option>
          <option value="mitigando" ${r.status === "mitigando" ? "selected" : ""}>Mitigando</option>
          <option value="fechado">Fechado</option>
        </select>
      </td>
      <td><button class="btn-small" data-detalhe-risco="${r.id}">Ver / Editar</button></td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".risco-status-select").forEach(sel => {
    let valorAnterior = sel.value;
    sel.addEventListener("change", async () => {
      if (sel.value === "fechado") {
        abrirFecharRisco(sel.dataset.riscoId, sel);
        return;
      }
      try {
        await api(`/api/riscos/${sel.dataset.riscoId}`, { method: "PUT", body: JSON.stringify({ status: sel.value }) });
        valorAnterior = sel.value;
        await loadRiscos();
        await loadPainel();
      } catch (e) {
        sel.value = valorAnterior;
        alert(e.message);
      }
    });
  });

  tbody.querySelectorAll("[data-detalhe-risco]").forEach(btn => {
    btn.addEventListener("click", () => abrirEditarRisco(Number(btn.dataset.detalheRisco)));
  });
}

function renderRiscosEncerrados(encerrados) {
  const tbody = document.getElementById("riscos-encerrados-tbody");
  if (encerrados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Nenhum risco/problema encerrado.</td></tr>`;
    return;
  }
  tbody.innerHTML = encerrados.map(r => `
    <tr>
      <td>${esc(r.cliente_nome)}</td>
      <td>${PILAR_LABELS[r.pilar] || esc(r.pilar)}</td>
      <td><span class="badge tipo-${r.tipo}">${r.tipo}</span></td>
      <td>${esc(r.titulo)}</td>
      <td><span class="badge sev-${r.severidade}">${r.severidade}</span></td>
      <td>${esc(r.responsavel || "—")}</td>
      <td>${fmtData(r.atualizado_em)}</td>
      <td>${diasEntre(r.criado_em, r.atualizado_em)}d</td>
      <td class="risco-nota-encerramento">${esc(r.nota_fechamento || "—")}</td>
      <td>
        <button class="btn-small" data-detalhe-risco="${r.id}">Ver / Editar</button>
        <button class="btn-small" data-reabrir-risco="${r.id}">Reabrir</button>
      </td>
    </tr>
  `).join("");

  tbody.querySelectorAll("[data-detalhe-risco]").forEach(btn => {
    btn.addEventListener("click", () => abrirEditarRisco(Number(btn.dataset.detalheRisco)));
  });

  tbody.querySelectorAll("[data-reabrir-risco]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const r = state.riscos.find(x => x.id === Number(btn.dataset.reabrirRisco));
      if (!r) return;
      if (!confirm(`Reabrir "${r.titulo}"? O status voltará para Aberto.`)) return;
      try {
        await api(`/api/riscos/${r.id}`, { method: "PUT", body: JSON.stringify({ status: "aberto" }) });
        await loadRiscos();
        await loadPainel();
      } catch (e) {
        alert("Não foi possível reabrir: " + e.message);
      }
    });
  });
}

document.querySelectorAll('#view-riscos .subtabs .subtab').forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll('#view-riscos .subtabs .subtab').forEach(b => b.classList.remove("active"));
    document.querySelectorAll('#view-riscos .subview').forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`riscos-${btn.dataset.riscosView}`).classList.add("active");
  });
});

// ---------- modal: editar risco/problema ----------

const STATUS_RISCO_LABELS = { aberto: "Aberto", mitigando: "Mitigando", fechado: "Fechado" };

async function abrirEditarRisco(riscoId) {
  const r = state.riscos.find(x => x.id === riscoId);
  if (!r) return;

  document.getElementById("er-id").value = r.id;
  document.getElementById("er-titulo-header").textContent = r.titulo;
  document.getElementById("er-cliente-pilar").textContent = `${r.cliente_nome} · ${PILAR_LABELS[r.pilar] || r.pilar}`;

  const badge = document.getElementById("er-status-badge");
  badge.className = `badge st-${r.status}`;
  badge.textContent = STATUS_RISCO_LABELS[r.status] || r.status;

  const abertoInfo = document.getElementById("er-aberto-info");
  const partesInfo = [];
  if (r.dias_aberto != null) partesInfo.push(`Aberto há ${r.dias_aberto} dia(s)`);
  if (r.atrasado) partesInfo.push("ATRASADO");
  abertoInfo.textContent = partesInfo.join(" · ");

  document.getElementById("er-tipo").value = r.tipo;
  document.getElementById("er-titulo").value = r.titulo;
  document.getElementById("er-descricao").value = r.descricao || "";
  document.getElementById("er-severidade").value = r.severidade;
  document.getElementById("er-data-alvo").value = r.data_alvo || "";
  await popularSelectResponsavel("er-responsavel", r.responsavel || "");
  document.getElementById("er-plano").value = r.plano_mitigacao || "";

  const notaWrap = document.getElementById("er-nota-fechamento-wrap");
  if (r.nota_fechamento) {
    notaWrap.classList.remove("hidden");
    document.getElementById("er-nota-fechamento").textContent = r.nota_fechamento;
  } else {
    notaWrap.classList.add("hidden");
  }

  document.getElementById("er-erro").classList.add("hidden");
  openModal("modal-editar-risco");
}

document.getElementById("er-salvar").addEventListener("click", async () => {
  const id = document.getElementById("er-id").value;
  const titulo = document.getElementById("er-titulo").value.trim();
  const erroEl = document.getElementById("er-erro");
  erroEl.classList.add("hidden");
  if (!titulo) {
    erroEl.textContent = "Informe um título.";
    erroEl.classList.remove("hidden");
    return;
  }
  const payload = {
    tipo: document.getElementById("er-tipo").value,
    titulo,
    descricao: document.getElementById("er-descricao").value.trim(),
    severidade: document.getElementById("er-severidade").value,
    responsavel: document.getElementById("er-responsavel").value.trim(),
    plano_mitigacao: document.getElementById("er-plano").value.trim(),
    data_alvo: document.getElementById("er-data-alvo").value || null,
  };
  try {
    await api(`/api/riscos/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    closeModal("modal-editar-risco");
    await loadRiscos();
    await loadPainel();
  } catch (e) {
    erroEl.textContent = e.message;
    erroEl.classList.remove("hidden");
  }
});

// ---------- fechamento de risco/problema (nota obrigatória) ----------

let frSelectAtivo = null;

function abrirFecharRisco(riscoId, selectEl) {
  frSelectAtivo = selectEl;
  document.getElementById("fr-risco-id").value = riscoId;
  document.getElementById("fr-nota").value = "";
  document.getElementById("fr-erro").classList.add("hidden");
  openModal("modal-fechar-risco");
}

function reverterSelectFechamento() {
  if (frSelectAtivo) frSelectAtivo.value = frSelectAtivo.value === "fechado" ? "aberto" : frSelectAtivo.value;
  frSelectAtivo = null;
}

document.querySelectorAll('[data-close-modal="modal-fechar-risco"]').forEach(el => {
  el.addEventListener("click", reverterSelectFechamento);
});

document.getElementById("fr-salvar").addEventListener("click", async () => {
  const riscoId = document.getElementById("fr-risco-id").value;
  const nota = document.getElementById("fr-nota").value.trim();
  const erroEl = document.getElementById("fr-erro");
  erroEl.classList.add("hidden");
  if (!nota) {
    erroEl.textContent = "Descreva como o risco/problema foi resolvido.";
    erroEl.classList.remove("hidden");
    return;
  }
  try {
    await api(`/api/riscos/${riscoId}`, {
      method: "PUT",
      body: JSON.stringify({ status: "fechado", nota_fechamento: nota }),
    });
    frSelectAtivo = null;
    closeModal("modal-fechar-risco");
    await loadRiscos();
    await loadPainel();
  } catch (e) {
    erroEl.textContent = e.message;
    erroEl.classList.remove("hidden");
  }
});

["risco-filtro-pilar", "risco-filtro-severidade"].forEach(id => {
  document.getElementById(id).addEventListener("change", loadRiscos);
});

document.getElementById("btn-novo-risco").addEventListener("click", async () => {
  const clienteSel = document.getElementById("nr-cliente");
  clienteSel.innerHTML = state.clientes.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
  const pilarSel = document.getElementById("nr-pilar");
  pilarSel.innerHTML = PILAR_ORDEM.map(p => `<option value="${p}">${PILAR_LABELS[p]}</option>`).join("");
  document.getElementById("nr-titulo").value = "";
  document.getElementById("nr-descricao").value = "";
  await popularSelectResponsavel("nr-responsavel", "");
  document.getElementById("nr-plano").value = "";
  document.getElementById("nr-data-alvo").value = "";
  openModal("modal-novo-risco");
});

document.getElementById("nr-salvar").addEventListener("click", async () => {
  const titulo = document.getElementById("nr-titulo").value.trim();
  if (!titulo) { alert("Informe um título."); return; }
  const payload = {
    cliente_id: Number(document.getElementById("nr-cliente").value),
    pilar: document.getElementById("nr-pilar").value,
    tipo: document.getElementById("nr-tipo").value,
    titulo,
    descricao: document.getElementById("nr-descricao").value.trim(),
    severidade: document.getElementById("nr-severidade").value,
    responsavel: document.getElementById("nr-responsavel").value.trim(),
    plano_mitigacao: document.getElementById("nr-plano").value.trim(),
    data_alvo: document.getElementById("nr-data-alvo").value || null,
  };
  try {
    await api("/api/riscos", { method: "POST", body: JSON.stringify(payload) });
    closeModal("modal-novo-risco");
    await loadRiscos();
  } catch (e) {
    alert(e.message);
  }
});

// ---------- ORGANIZAÇÃO tab ----------

function pessoasSemCliente() {
  const vinculadas = new Set();
  state.clientes.forEach(c => {
    if (c.am) vinculadas.add(c.am.id);
    (c.dms || []).forEach(d => vinculadas.add(d.id));
  });
  return state.pessoas.filter(p => p.ativo && (p.papel === "am" || p.papel === "dm") && !vinculadas.has(p.id));
}

function renderOrgConteudo() {
  const el = document.getElementById("org-conteudo");
  if (!state.clientes.length) { el.innerHTML = `<div class="empty-state">Carregando…</div>`; return; }
  el.innerHTML = state.orgView === "cliente" ? renderOrgPorClienteHtml() : renderOrgPorPessoaHtml();
}

function renderOrgPorClienteHtml() {
  const diretores = diretoresOrdenados();
  return diretores.map((dir, idx) => {
    const clientesDoDir = state.clientes.filter(c => c.bu_director && c.bu_director.id === dir.id);
    if (!clientesDoDir.length) return "";
    const industrias = [...new Set(clientesDoDir.map(c => c.industry_code))].join(", ");
    return `
      <div class="bu-section">
        <div class="bu-section-header">
          <span class="bu-dot" style="background:${directorColor(idx)}"></span>
          <span class="bu-section-title">${esc(dir.nome)}</span>
          <span class="bu-section-meta">BU Director · ${esc(industrias)}</span>
        </div>
        <div class="org-cliente-grid">
          ${clientesDoDir.map(c => `
            <div class="org-card">
              <div class="org-card-title">${esc(c.nome)}</div>
              <div class="org-card-line">AM · <b>${c.am ? esc(c.am.nome) : "—"}</b></div>
              <div class="org-card-line dm-line">DM · <b>${esc(dmsLabel(c.dms))}</b></div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }).join("");
}

function renderOrgPorPessoaHtml() {
  const diretores = diretoresOrdenados();
  const secoes = diretores.map((dir, idx) => {
    const clientesDoDir = state.clientes.filter(c => c.bu_director && c.bu_director.id === dir.id);
    if (!clientesDoDir.length) return "";
    const industrias = [...new Set(clientesDoDir.map(c => c.industry_code))].join(", ");

    const amMap = new Map();
    const dmMap = new Map();
    clientesDoDir.forEach(c => {
      if (c.am && c.am.id !== dir.id) {
        if (!amMap.has(c.am.id)) amMap.set(c.am.id, { nome: c.am.nome, clientes: [] });
        amMap.get(c.am.id).clientes.push(c.nome);
      }
      (c.dms || []).forEach(d => {
        if (!dmMap.has(d.id)) dmMap.set(d.id, { nome: d.nome, clientes: [] });
        dmMap.get(d.id).clientes.push(c.nome);
      });
    });

    const amCards = [...amMap.values()].sort((a, b) => a.nome.localeCompare(b.nome));
    const dmCards = [...dmMap.values()].sort((a, b) => a.nome.localeCompare(b.nome));

    return `
      <div class="bu-section">
        <div class="bu-section-header">
          <span class="bu-dot" style="background:${directorColor(idx)}"></span>
          <span class="bu-section-title">${esc(dir.nome)}</span>
          <span class="bu-section-meta">BU Director · ${esc(industrias)}</span>
        </div>
        <div class="org-cliente-grid">
          ${amCards.map(p => `
            <div class="org-card pessoa-card">
              <div class="org-card-title">${esc(p.nome)}</div>
              <div class="org-card-line">AM · <b>${esc(p.clientes.join(", "))}</b></div>
            </div>
          `).join("")}
          ${dmCards.map(p => `
            <div class="org-card pessoa-card">
              <div class="org-card-title">${esc(p.nome)}</div>
              <div class="org-card-line dm-line">DM · <b>${esc(p.clientes.join(", "))}</b></div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }).join("");

  const semCliente = pessoasSemCliente();
  const semClienteHtml = semCliente.length ? `
    <div class="bu-section">
      <div class="bu-section-header">
        <span class="bu-dot" style="background:var(--text-subtle)"></span>
        <span class="bu-section-title">Pessoas sem cliente vinculado ainda</span>
      </div>
      <div class="org-cliente-grid">
        ${semCliente.map(p => `
          <div class="org-card pessoa-card">
            <div class="org-card-title">${esc(p.nome)}</div>
            <div class="org-card-line"><span class="badge papel-${p.papel}">${PAPEL_LABELS[p.papel]}</span></div>
            <div class="org-empty-clientes">Nenhum cliente vinculado</div>
          </div>
        `).join("")}
      </div>
    </div>
  ` : "";

  return secoes + semClienteHtml;
}

// ---------- Modelo de Pontuação (referência estática) ----------

function regrasConsolidacaoHtml() {
  return `
    <p style="font-size:12px;color:var(--text-muted)">Ponderação por status: G = 100% · A = 50% · R = 0%</p>
    <p style="margin-top:10px"><strong>Regras de consolidação:</strong></p>
    <ol style="margin-left:18px">
      <li>Qualquer pilar em R ⇒ RAG geral = R (override automático, sem exceção).</li>
      <li>Sem pilares em R: Score ≥ 85 ⇒ G · Score entre 50 e 84,9 ⇒ A · Score &lt; 50 ⇒ R.</li>
      <li>Pesos e faixas de corte (85 / 50) são parametrizáveis — ajustar conforme maturidade da carteira.</li>
    </ol>
  `;
}

function modeloPontuacaoLinhasHtml() {
  const linhas = PILAR_GRUPOS.flatMap(cat => cat.pilares.map(p => {
    const pesoPct = Math.round(PILAR_PESO[p] * 100);
    return `
      <tr>
        <td>${esc(cat.label)}</td>
        <td><strong>${esc(PILAR_LABELS[p])}</strong></td>
        <td class="center">${pesoPct}%</td>
        <td class="center">100</td>
        <td class="center">${pesoPct}</td>
        <td>${esc(PILAR_DONO[p])}</td>
      </tr>
    `;
  })).join("");

  return linhas + `
    <tr class="modelo-pontuacao-total">
      <td colspan="2">TOTAL</td>
      <td class="center">100%</td>
      <td></td>
      <td class="center">100</td>
      <td></td>
    </tr>
  `;
}

function modeloPontuacaoTabelaHtml() {
  return `
    <h4>Modelo de Pontuação</h4>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Categoria</th><th>Pilar</th><th>Peso</th><th>Pontuação</th><th>Peso × Pontuação</th><th>Dono</th></tr></thead>
        <tbody>${modeloPontuacaoLinhasHtml()}</tbody>
      </table>
    </div>
  `;
}

function abrirRagGeralInfo() {
  document.getElementById("criterios-ref-titulo").textContent = "RAG Geral — Regras de Consolidação";
  document.getElementById("criterios-ref-corpo").innerHTML = modeloPontuacaoTabelaHtml() + regrasConsolidacaoHtml();
  openModal("modal-criterios-ref");
}

function renderModeloPontuacao() {
  document.getElementById("modelo-pontuacao-tbody").innerHTML = modeloPontuacaoLinhasHtml();
  document.getElementById("modelo-pontuacao-regras").innerHTML = regrasConsolidacaoHtml();
}

// ---------- CRITÉRIOS tab ----------

async function loadCriterios() {
  const criterios = await api("/api/criterios");
  state.criterios = criterios;
  renderCriterios();
}

function renderCriterios() {
  const grupos = new Map();
  state.criterios.forEach(c => {
    const key = `${c.pilar}|||${c.linha}`;
    if (!grupos.has(key)) grupos.set(key, { pilar: c.pilar, linha: c.linha, itens: {} });
    grupos.get(key).itens[c.status] = c;
  });

  const linhaHtml = g => `
    <tr>
      <td><strong>${PILAR_LABELS[g.pilar] || esc(g.pilar)}</strong></td>
      <td>${esc(g.linha)}</td>
      ${["G", "A", "R"].map(s => {
        const item = g.itens[s];
        if (!item) return `<td>—</td>`;
        return `<td class="criterio-cell" contenteditable="true" data-criterio-id="${item.id}">${esc(item.descricao)}</td>`;
      }).join("")}
    </tr>
  `;

  const todosGrupos = [...grupos.values()];
  const tbody = document.getElementById("criterios-tbody");
  tbody.innerHTML = PILAR_GRUPOS.map(cat => {
    const gruposCategoria = todosGrupos.filter(g => cat.pilares.includes(g.pilar));
    if (!gruposCategoria.length) return "";
    return `<tr class="criterios-categoria-row"><td colspan="5"><strong>${esc(cat.label)}</strong></td></tr>`
      + gruposCategoria.map(linhaHtml).join("");
  }).join("");

  tbody.querySelectorAll(".criterio-cell").forEach(td => {
    let original = td.textContent;
    td.addEventListener("focus", () => { original = td.textContent; });
    td.addEventListener("blur", async () => {
      const novoTexto = td.textContent.trim();
      if (novoTexto === original.trim()) return;
      try {
        await api(`/api/criterios/${td.dataset.criterioId}`, { method: "PUT", body: JSON.stringify({ descricao: novoTexto }) });
        td.style.background = "rgba(22,163,74,.12)";
        setTimeout(() => { td.style.background = ""; }, 800);
      } catch (e) {
        td.textContent = original;
        alert("Não foi possível salvar: " + e.message);
      }
    });
  });
}

function populaFiltroPilarRiscos() {
  const sel = document.getElementById("risco-filtro-pilar");
  sel.innerHTML = `<option value="">Pilar (todos)</option>` +
    PILAR_ORDEM.map(p => `<option value="${p}">${PILAR_LABELS[p]}</option>`).join("");
}

// ---------- ADMIN: Auditoria ----------

const ENTIDADE_LABELS = { cliente: "Cliente", pessoa: "Pessoa", status: "Status RAG", risco: "Risco/Problema", criterio: "Critério", sistema: "Sistema" };
const ACAO_LABELS = { criar: "Criar", editar: "Editar", fechar: "Encerrar", resetar_senha: "Resetar senha", trocar_senha: "Trocar senha", resetar: "Reset geral" };

async function loadAuditoria() {
  const entidade = document.getElementById("aud-filtro-entidade").value;
  const busca = document.getElementById("aud-filtro-busca").value.trim();
  const params = new URLSearchParams();
  if (entidade) params.set("entidade", entidade);
  if (busca) params.set("busca", busca);
  try {
    state.auditoria = await api(`/api/auditoria?${params.toString()}`);
  } catch (e) {
    state.auditoria = [];
  }
  renderAuditoria();
}

function renderAuditoria() {
  const tbody = document.getElementById("auditoria-tbody");
  if (!state.auditoria || state.auditoria.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Nenhum registro encontrado.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.auditoria.map(a => `
    <tr>
      <td>${fmtDataLonga(a.criado_em)}</td>
      <td>${esc(a.pessoa_nome)}</td>
      <td><span class="badge papel-${a.entidade === "pessoa" ? "bu_director" : "am"}">${ENTIDADE_LABELS[a.entidade] || esc(a.entidade)}</span></td>
      <td>${ACAO_LABELS[a.acao] || esc(a.acao)}</td>
      <td>${esc(a.detalhes || "—")}</td>
    </tr>
  `).join("");
}

["aud-filtro-entidade", "aud-filtro-busca"].forEach(id => {
  document.getElementById(id).addEventListener("change", loadAuditoria);
});
document.getElementById("aud-filtro-busca").addEventListener("keydown", (e) => { if (e.key === "Enter") loadAuditoria(); });

// ---------- ADMIN: Pessoas ----------

function resetFormPessoa() {
  document.getElementById("ap-id").value = "";
  document.getElementById("ap-nome").value = "";
  document.getElementById("ap-papel").value = "am";
  document.getElementById("ap-email").value = "";
  document.getElementById("ap-ativo").checked = true;
  document.getElementById("ap-acesso-full").checked = false;
  document.getElementById("ap-form-titulo").textContent = "Nova Pessoa";
  document.getElementById("ap-senha-hint").textContent = "Senha inicial: SysManager@2026 — a pessoa deverá trocar no primeiro acesso.";
}

async function loadAdminPessoas() {
  const pessoas = await api("/api/pessoas");
  state.pessoas = pessoas;
  const tbody = document.getElementById("admin-pessoas-tbody");
  tbody.innerHTML = pessoas.length ? pessoas.map(p => `
    <tr>
      <td>${esc(p.nome)}</td>
      <td>${esc(p.email || "—")}</td>
      <td><span class="badge papel-${p.papel}">${PAPEL_LABELS[p.papel] || esc(p.papel)}</span></td>
      <td>${p.ativo ? "Sim" : "Não"}</td>
      <td>${p.acesso_full ? "Sim" : "Não"}</td>
      <td>
        <button class="btn-small" data-editar-pessoa="${p.id}">Editar</button>
        <button class="btn-small" data-resetar-senha="${p.id}">Resetar senha</button>
      </td>
    </tr>
  `).join("") : `<tr><td colspan="6" class="empty-state">Nenhuma pessoa cadastrada.</td></tr>`;

  tbody.querySelectorAll("[data-editar-pessoa]").forEach(btn => {
    btn.addEventListener("click", () => {
      const p = pessoas.find(x => x.id === Number(btn.dataset.editarPessoa));
      if (!p) return;
      document.getElementById("ap-id").value = p.id;
      document.getElementById("ap-nome").value = p.nome;
      document.getElementById("ap-papel").value = p.papel;
      document.getElementById("ap-email").value = p.email || "";
      document.getElementById("ap-ativo").checked = !!p.ativo;
      document.getElementById("ap-acesso-full").checked = !!p.acesso_full;
      document.getElementById("ap-form-titulo").textContent = `Editando: ${p.nome}`;
      document.getElementById("ap-senha-hint").textContent = "Deixe o email como está para não alterar o login.";
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });

  tbody.querySelectorAll("[data-resetar-senha]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const p = pessoas.find(x => x.id === Number(btn.dataset.resetarSenha));
      if (!p) return;
      if (!confirm(`Resetar a senha de ${p.nome} para a senha padrão (SysManager@2026)? A pessoa precisará trocá-la no próximo login.`)) return;
      try {
        await api(`/api/pessoas/${p.id}/resetar-senha`, { method: "POST" });
        alert("Senha resetada para o padrão SysManager@2026.");
      } catch (e) {
        alert("Não foi possível resetar a senha: " + e.message);
      }
    });
  });
}

document.getElementById("ap-cancelar").addEventListener("click", resetFormPessoa);

document.getElementById("ap-salvar").addEventListener("click", async () => {
  const nome = document.getElementById("ap-nome").value.trim();
  if (!nome) { alert("Informe o nome."); return; }
  const id = document.getElementById("ap-id").value;
  const email = document.getElementById("ap-email").value.trim();
  const payload = {
    nome,
    papel: document.getElementById("ap-papel").value,
    email: email || null,
    ativo: document.getElementById("ap-ativo").checked,
    acesso_full: document.getElementById("ap-acesso-full").checked,
  };
  try {
    if (id) {
      await api(`/api/pessoas/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/pessoas", { method: "POST", body: JSON.stringify(payload) });
    }
    resetFormPessoa();
    await loadAdminPessoas();
  } catch (e) {
    alert("Não foi possível salvar: " + e.message);
  }
});

// ---------- ADMIN: Clientes ----------

function populaSelectsClienteForm() {
  const buSel = document.getElementById("ac-bu-director");
  const amSel = document.getElementById("ac-am");
  const dmSel = document.getElementById("ac-dms");

  buSel.innerHTML = pessoasAtivas("bu_director").map(p => `<option value="${p.id}">${esc(p.nome)}</option>`).join("");
  amSel.innerHTML = pessoasAtivas().map(p => `<option value="${p.id}">${esc(p.nome)} · ${PAPEL_LABELS[p.papel]}</option>`).join("");
  dmSel.innerHTML = pessoasAtivas().map(p => `<option value="${p.id}">${esc(p.nome)} · ${PAPEL_LABELS[p.papel]}</option>`).join("");
}

function resetFormCliente() {
  document.getElementById("ac-id").value = "";
  document.getElementById("ac-nome").value = "";
  document.getElementById("ac-industry").value = "";
  document.getElementById("ac-tipo-linha").value = "Projeto";
  document.getElementById("ac-ativo").checked = true;
  document.getElementById("ac-form-titulo").textContent = "Novo Cliente";
  populaSelectsClienteForm();
  document.getElementById("ac-bu-director").selectedIndex = -1;
  document.getElementById("ac-am").selectedIndex = -1;
  [...document.getElementById("ac-dms").options].forEach(o => o.selected = false);
}

async function loadAdminClientesTable() {
  if (!state.pessoas.length) state.pessoas = await api("/api/pessoas");
  const clientes = await api("/api/clientes");
  state.clientes = clientes;
  populaSelectsClienteForm();

  const tbody = document.getElementById("admin-clientes-tbody");
  tbody.innerHTML = clientes.length ? clientes.map(c => `
    <tr>
      <td>${esc(c.nome)}</td>
      <td><span class="pill">${esc(c.industry_code)}</span></td>
      <td>${c.bu_director ? esc(c.bu_director.nome) : "—"}</td>
      <td>${c.am ? esc(c.am.nome) : "—"}</td>
      <td>${esc(dmsLabel(c.dms))}</td>
      <td>Sim</td>
      <td><button class="btn-small" data-editar-cliente="${c.id}">Editar</button></td>
    </tr>
  `).join("") : `<tr><td colspan="7" class="empty-state">Nenhum cliente cadastrado.</td></tr>`;

  tbody.querySelectorAll("[data-editar-cliente]").forEach(btn => {
    btn.addEventListener("click", () => {
      const c = clientes.find(x => x.id === Number(btn.dataset.editarCliente));
      if (!c) return;
      document.getElementById("ac-id").value = c.id;
      document.getElementById("ac-nome").value = c.nome;
      document.getElementById("ac-industry").value = c.industry_code;
      document.getElementById("ac-tipo-linha").value = c.tipo_linha;
      document.getElementById("ac-ativo").checked = true;
      document.getElementById("ac-form-titulo").textContent = `Editando: ${c.nome}`;
      populaSelectsClienteForm();
      document.getElementById("ac-bu-director").value = c.bu_director ? c.bu_director.id : "";
      document.getElementById("ac-am").value = c.am ? c.am.id : "";
      const dmIds = new Set((c.dms || []).map(d => String(d.id)));
      [...document.getElementById("ac-dms").options].forEach(o => { o.selected = dmIds.has(o.value); });
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

document.getElementById("ac-cancelar").addEventListener("click", resetFormCliente);

document.getElementById("ac-salvar").addEventListener("click", async () => {
  const nome = document.getElementById("ac-nome").value.trim();
  const industry = document.getElementById("ac-industry").value.trim();
  if (!nome || !industry) { alert("Informe nome e industry code."); return; }
  const id = document.getElementById("ac-id").value;
  const dmIds = [...document.getElementById("ac-dms").selectedOptions].map(o => Number(o.value));
  const payload = {
    nome,
    industry_code: industry,
    tipo_linha: document.getElementById("ac-tipo-linha").value,
    bu_director_id: document.getElementById("ac-bu-director").value ? Number(document.getElementById("ac-bu-director").value) : null,
    am_id: document.getElementById("ac-am").value ? Number(document.getElementById("ac-am").value) : null,
    dm_ids: dmIds,
    ativo: document.getElementById("ac-ativo").checked,
  };
  try {
    if (id) {
      await api(`/api/clientes/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/clientes", { method: "POST", body: JSON.stringify(payload) });
    }
    resetFormCliente();
    await loadAdminClientesTable();
  } catch (e) {
    alert("Não foi possível salvar: " + e.message);
  }
});

// ---------- EXPORTAÇÃO: Excel (SheetJS) ----------

function exportarExcel(linhas, colunas, nomeArquivo, nomeAba) {
  if (typeof window.XLSX === "undefined") {
    alert("Exportador ainda carregando, tente novamente em instantes.");
    return;
  }
  const headers = colunas.map(c => c.header);
  const data = linhas.map(row => colunas.map(c => row[c.key]));
  const ws = window.XLSX.utils.aoa_to_sheet([headers, ...data]);
  ws["!cols"] = colunas.map(c => ({ wch: c.width || 18 }));
  const wb = window.XLSX.utils.book_new();
  window.XLSX.utils.book_append_sheet(wb, ws, nomeAba || "Dados");
  window.XLSX.writeFile(wb, nomeArquivo);
}

document.getElementById("btn-export-painel-excel").addEventListener("click", () => {
  const linhas = state.clientes.map(c => {
    const linha = {
      cliente: c.nome,
      industry: c.industry_code,
      bu_director: c.bu_director ? c.bu_director.nome : "",
      am: c.am ? c.am.nome : "",
      dms: dmsLabel(c.dms),
      modificado: fmtData(c.modificado),
      rag_geral: c.rag_geral,
      score_consolidado: c.score_consolidado,
      alertas: (c.alertas || []).join("; "),
    };
    PILAR_ORDEM.forEach(p => { linha[p] = c.pilares[p]; });
    return linha;
  });
  exportarExcel(linhas, [
    { header: "Cliente", key: "cliente", width: 22 },
    { header: "Industry Code", key: "industry", width: 14 },
    { header: "BU Director", key: "bu_director", width: 20 },
    { header: "AM", key: "am", width: 20 },
    { header: "DM(s)", key: "dms", width: 28 },
    { header: "Modificado", key: "modificado", width: 14 },
    { header: "RAG Geral", key: "rag_geral", width: 10 },
    { header: "Score Consolidado", key: "score_consolidado", width: 12 },
    ...PILAR_ORDEM.map(p => ({ header: `${PILAR_CATEGORIA[p]} — ${PILAR_LABELS[p]}`, key: p, width: 10 })),
    { header: "Alertas", key: "alertas", width: 40 },
  ], "rag-status-painel.xlsx", "Painel RAG Status");
});

document.getElementById("btn-export-riscos-excel").addEventListener("click", () => {
  const linhas = state.riscos.map(r => ({
    cliente: r.cliente_nome,
    pilar: PILAR_LABELS[r.pilar] || r.pilar,
    tipo: r.tipo,
    titulo: r.titulo,
    severidade: r.severidade,
    responsavel: r.responsavel || "",
    data_alvo: r.data_alvo || "",
    atrasado: r.atrasado ? "Sim" : "Não",
    dias_aberto: r.dias_aberto != null ? r.dias_aberto : "",
    status: r.status,
    nota_fechamento: r.nota_fechamento || "",
  }));
  exportarExcel(linhas, [
    { header: "Cliente", key: "cliente", width: 22 },
    { header: "Pilar", key: "pilar", width: 14 },
    { header: "Tipo", key: "tipo", width: 12 },
    { header: "Título", key: "titulo", width: 40 },
    { header: "Severidade", key: "severidade", width: 12 },
    { header: "Responsável", key: "responsavel", width: 22 },
    { header: "Data alvo", key: "data_alvo", width: 12 },
    { header: "Atrasado", key: "atrasado", width: 10 },
    { header: "Dias em aberto", key: "dias_aberto", width: 14 },
    { header: "Status", key: "status", width: 12 },
    { header: "Nota de encerramento", key: "nota_fechamento", width: 40 },
  ], "rag-status-riscos.xlsx", "Riscos e Problemas");
});

// ---------- EXPORTAÇÃO: PDF (print view) ----------

document.getElementById("btn-export-painel-pdf").addEventListener("click", () => {
  const diretores = diretoresOrdenados();
  const hoje = new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });

  const secoes = diretores.map(dir => {
    const clientesDoDir = state.clientes.filter(c => c.bu_director && c.bu_director.id === dir.id);
    if (!clientesDoDir.length) return "";
    return `
      <div class="print-section-title">${esc(dir.nome)} — BU Director</div>
      <table>
        <thead>
          <tr>
            <th rowspan="2">Cliente</th><th rowspan="2">Industry</th>
            <th rowspan="2">RAG Geral</th><th rowspan="2">Score</th>
            ${PILAR_GRUPOS.map(g => `<th colspan="${g.pilares.length}">${esc(g.label)}</th>`).join("")}
            <th rowspan="2">AM</th><th rowspan="2">DM</th>
          </tr>
          <tr>${PILAR_ORDEM.map(p => `<th>${PILAR_LABELS_CURTO[p]}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${clientesDoDir.map(c => `
            <tr>
              <td>${esc(c.nome)}</td>
              <td>${esc(c.industry_code)}</td>
              <td>${c.rag_geral}</td>
              <td>${c.score_consolidado}</td>
              ${PILAR_ORDEM.map(p => `<td>${c.pilares[p]}</td>`).join("")}
              <td>${c.am ? esc(c.am.nome) : "—"}</td>
              <td>${esc(dmsLabel(c.dms))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `;
  }).join("");

  document.getElementById("print-view").innerHTML = `
    <div class="print-title">RAG Status — Painel Executivo</div>
    <div class="print-meta">Gerado em ${hoje}</div>
    ${secoes}
  `;
  window.print();
});

// ---------- init ----------

function setPeriodo() {
  const hoje = new Date();
  const seg = new Date(hoje);
  seg.setDate(hoje.getDate() - ((hoje.getDay() + 6) % 7));
  document.getElementById("periodo-atual").textContent = `Semana de ${seg.toLocaleDateString("pt-BR", { day: "2-digit", month: "long" })}`;
}

async function init() {
  setPeriodo();
  populaFiltroPilarRiscos();

  if (!session.token) {
    mostrarLogin();
    return;
  }
  try {
    session.pessoa = await api("/api/auth/me");
    await entrarNaAplicacao();
  } catch (e) {
    limparSessao();
    mostrarLogin();
  }
}

init().catch(err => {
  console.error(err);
  const erroEl = document.getElementById("login-erro");
  erroEl.textContent = `Falha ao carregar a aplicação: ${err.message}. Verifique se o backend está rodando.`;
  erroEl.classList.remove("hidden");
  mostrarLogin();
});
