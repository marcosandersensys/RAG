const PILAR_ORDEM = ["prazo", "escopo", "rh", "contrato", "faturamento"];
const PILAR_LABELS = { prazo: "Prazo", escopo: "Escopo", rh: "RH", contrato: "Contrato", faturamento: "Faturamento" };
const PAPEL_LABELS = { bu_director: "BU Director", am: "AM", dm: "DM" };
const DIRECTOR_COLORS = ["var(--sys-magenta)", "var(--sys-blue)", "var(--sys-purple)"];

const state = {
  clientes: [],
  pessoas: [],
  riscos: [],
  criterios: [],
  orgView: "cliente",
  adminView: "pessoas",
};

// ---------- helpers ----------

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

async function api(path, opts) {
  const res = await fetch(path, opts && {
    ...opts,
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
  });
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

function fmtDataLonga(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function lastUsedPessoaId(setVal) {
  const key = "rag-status:atualizado-por-id";
  if (setVal !== undefined) { localStorage.setItem(key, setVal); return; }
  return localStorage.getItem(key) || "";
}

function pessoasAtivas(papel) {
  return state.pessoas.filter(p => p.ativo && (!papel || p.papel === papel)).sort((a, b) => a.nome.localeCompare(b.nome));
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
document.querySelector('.tab[data-view="criterios"]').addEventListener("click", loadCriterios);
document.querySelector('.tab[data-view="organizacao"]').addEventListener("click", renderOrgConteudo);
document.querySelector('.tab[data-view="admin"]').addEventListener("click", () => { loadAdminPessoas(); loadAdminClientesTable(); });

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
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(overlay.id); });
});

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
  `;
}

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
                  <th>Cliente</th><th>Industry</th><th>AM</th><th>DM(s)</th><th>Modificado</th>
                  <th>Prazo</th><th>Escopo</th><th>RH</th><th>Contrato</th><th>Faturamento</th>
                </tr>
              </thead>
              <tbody>
                ${clientesDoDir.map(c => `
                  <tr>
                    <td><span class="cliente-nome" data-cliente-id="${c.id}">${esc(c.nome)}</span></td>
                    <td><span class="pill">${esc(c.industry_code)}</span></td>
                    <td>${c.am ? esc(c.am.nome) : "—"}</td>
                    <td>${esc(dmsLabel(c.dms))}</td>
                    <td>${fmtData(c.modificado)}</td>
                    ${PILAR_ORDEM.map(p => `
                      <td><button class="badge-rag ${c.pilares[p].toLowerCase()}" data-cliente-id="${c.id}" data-pilar="${p}">${c.pilares[p]}</button></td>
                    `).join("")}
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
}

["filtro-busca", "filtro-bu-director", "filtro-industry", "filtro-somente-risco"].forEach(id => {
  document.getElementById(id).addEventListener("input", renderPainelSecoes);
  document.getElementById(id).addEventListener("change", renderPainelSecoes);
});

// ---------- modal: atualizar status ----------

let msSelectedStatus = null;

function populateAtualizadoPorSelect() {
  const sel = document.getElementById("ms-atualizado-por");
  const pessoas = pessoasAtivas();
  sel.innerHTML = pessoas.map(p => `<option value="${p.id}">${esc(p.nome)} · ${PAPEL_LABELS[p.papel]}</option>`).join("");
  const last = lastUsedPessoaId();
  if (last && pessoas.some(p => String(p.id) === last)) sel.value = last;
}

function openStatusModal(clienteId, pilar) {
  const cliente = state.clientes.find(c => c.id === clienteId);
  if (!cliente) return;

  document.getElementById("ms-cliente-id").value = clienteId;
  document.getElementById("ms-pilar").value = pilar;
  document.getElementById("modal-status-titulo").textContent = `${cliente.nome} — ${PILAR_LABELS[pilar]}`;
  document.getElementById("ms-comentario").value = "";
  populateAtualizadoPorSelect();
  document.getElementById("ms-erro").classList.add("hidden");
  document.getElementById("ms-r-titulo").value = "";
  document.getElementById("ms-r-descricao").value = "";
  document.getElementById("ms-r-responsavel").value = "";
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
  const atualizadoPorId = document.getElementById("ms-atualizado-por").value;
  const atualizadoPorPessoa = state.pessoas.find(p => String(p.id) === atualizadoPorId);
  const erroEl = document.getElementById("ms-erro");
  erroEl.classList.add("hidden");

  if (!msSelectedStatus) { erroEl.textContent = "Selecione um status."; erroEl.classList.remove("hidden"); return; }
  if (!atualizadoPorPessoa) { erroEl.textContent = "Selecione quem está atualizando."; erroEl.classList.remove("hidden"); return; }

  const payload = {
    cliente_id: clienteId,
    pilar,
    status: msSelectedStatus,
    comentario: document.getElementById("ms-comentario").value.trim(),
    atualizado_por: atualizadoPorPessoa.nome,
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
    lastUsedPessoaId(atualizadoPorId);
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

async function openClienteModal(clienteId) {
  const detalhe = await api(`/api/clientes/${clienteId}`);
  document.getElementById("mc-titulo").textContent = `${detalhe.nome} · ${detalhe.industry_code}`;

  document.getElementById("mc-pilares").innerHTML = PILAR_ORDEM.map(p => `
    <div class="pilar-mini">
      <div class="lbl">${PILAR_LABELS[p]}</div>
      <span class="badge-rag ${detalhe.pilares[p].toLowerCase()}">${detalhe.pilares[p]}</span>
    </div>
  `).join("");

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
    <div class="historico-item">
      <span><span class="badge tipo-${r.tipo}">${r.tipo}</span> ${PILAR_LABELS[r.pilar]} — <strong>${esc(r.titulo)}</strong>
      <span class="badge st-${r.status}">${r.status}</span></span>
      <span class="meta">${esc(r.responsavel || "—")}</span>
    </div>
  `).join("") : `<div class="empty-state">Nenhum risco/problema vinculado.</div>`;

  openModal("modal-cliente");
}

// ---------- RISCOS & PROBLEMAS tab ----------

async function loadRiscos() {
  const pilar = document.getElementById("risco-filtro-pilar").value;
  const status = document.getElementById("risco-filtro-status").value;
  const severidade = document.getElementById("risco-filtro-severidade").value;

  const params = new URLSearchParams();
  if (pilar) params.set("pilar", pilar);
  if (status) params.set("status", status);
  if (severidade) params.set("severidade", severidade);

  const riscos = await api(`/api/riscos?${params.toString()}`);
  state.riscos = riscos;
  renderTabelaRiscos();
}

function renderTabelaRiscos() {
  const tbody = document.getElementById("riscos-tbody");
  if (state.riscos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Nenhum risco/problema encontrado.</td></tr>`;
    return;
  }
  tbody.innerHTML = state.riscos.map(r => `
    <tr>
      <td>${esc(r.cliente_nome)}</td>
      <td>${PILAR_LABELS[r.pilar] || esc(r.pilar)}</td>
      <td><span class="badge tipo-${r.tipo}">${r.tipo}</span></td>
      <td>${esc(r.titulo)}</td>
      <td><span class="badge sev-${r.severidade}">${r.severidade}</span></td>
      <td>${esc(r.responsavel || "—")}</td>
      <td>${r.data_alvo ? esc(r.data_alvo) : "—"}</td>
      <td>
        <select class="risco-status-select" data-risco-id="${r.id}">
          <option value="aberto" ${r.status === "aberto" ? "selected" : ""}>Aberto</option>
          <option value="mitigando" ${r.status === "mitigando" ? "selected" : ""}>Mitigando</option>
          <option value="fechado" ${r.status === "fechado" ? "selected" : ""}>Fechado</option>
        </select>
      </td>
      <td><button class="btn-small" data-detalhe-risco="${r.id}">Ver</button></td>
    </tr>
  `).join("");

  tbody.querySelectorAll(".risco-status-select").forEach(sel => {
    sel.addEventListener("change", async () => {
      try {
        await api(`/api/riscos/${sel.dataset.riscoId}`, { method: "PUT", body: JSON.stringify({ status: sel.value }) });
        await loadRiscos();
        await loadPainel();
      } catch (e) {
        alert(e.message);
      }
    });
  });

  tbody.querySelectorAll("[data-detalhe-risco]").forEach(btn => {
    btn.addEventListener("click", () => {
      const r = state.riscos.find(x => x.id === Number(btn.dataset.detalheRisco));
      if (!r) return;
      alert(
        `${r.titulo}\n\nCliente: ${r.cliente_nome}\nPilar: ${PILAR_LABELS[r.pilar]}\nSeveridade: ${r.severidade}\n` +
        `Responsável: ${r.responsavel || "—"}\n\nDescrição:\n${r.descricao || "—"}\n\nPlano de mitigação:\n${r.plano_mitigacao || "—"}`
      );
    });
  });
}

["risco-filtro-pilar", "risco-filtro-status", "risco-filtro-severidade"].forEach(id => {
  document.getElementById(id).addEventListener("change", loadRiscos);
});

document.getElementById("btn-novo-risco").addEventListener("click", () => {
  const clienteSel = document.getElementById("nr-cliente");
  clienteSel.innerHTML = state.clientes.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
  const pilarSel = document.getElementById("nr-pilar");
  pilarSel.innerHTML = PILAR_ORDEM.map(p => `<option value="${p}">${PILAR_LABELS[p]}</option>`).join("");
  document.getElementById("nr-titulo").value = "";
  document.getElementById("nr-descricao").value = "";
  document.getElementById("nr-responsavel").value = "";
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

  const tbody = document.getElementById("criterios-tbody");
  tbody.innerHTML = [...grupos.values()].map(g => `
    <tr>
      <td><strong>${PILAR_LABELS[g.pilar] || esc(g.pilar)}</strong></td>
      <td>${esc(g.linha)}</td>
      ${["G", "A", "R"].map(s => {
        const item = g.itens[s];
        if (!item) return `<td>—</td>`;
        return `<td class="criterio-cell" contenteditable="true" data-criterio-id="${item.id}">${esc(item.descricao)}</td>`;
      }).join("")}
    </tr>
  `).join("");

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

// ---------- ADMIN: Pessoas ----------

function resetFormPessoa() {
  document.getElementById("ap-id").value = "";
  document.getElementById("ap-nome").value = "";
  document.getElementById("ap-papel").value = "am";
  document.getElementById("ap-ativo").checked = true;
  document.getElementById("ap-form-titulo").textContent = "Nova Pessoa";
}

async function loadAdminPessoas() {
  const pessoas = await api("/api/pessoas");
  state.pessoas = pessoas;
  const tbody = document.getElementById("admin-pessoas-tbody");
  tbody.innerHTML = pessoas.length ? pessoas.map(p => `
    <tr>
      <td>${esc(p.nome)}</td>
      <td><span class="badge papel-${p.papel}">${PAPEL_LABELS[p.papel]}</span></td>
      <td>${p.ativo ? "Sim" : "Não"}</td>
      <td><button class="btn-small" data-editar-pessoa="${p.id}">Editar</button></td>
    </tr>
  `).join("") : `<tr><td colspan="4" class="empty-state">Nenhuma pessoa cadastrada.</td></tr>`;

  tbody.querySelectorAll("[data-editar-pessoa]").forEach(btn => {
    btn.addEventListener("click", () => {
      const p = pessoas.find(x => x.id === Number(btn.dataset.editarPessoa));
      if (!p) return;
      document.getElementById("ap-id").value = p.id;
      document.getElementById("ap-nome").value = p.nome;
      document.getElementById("ap-papel").value = p.papel;
      document.getElementById("ap-ativo").checked = !!p.ativo;
      document.getElementById("ap-form-titulo").textContent = `Editando: ${p.nome}`;
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

document.getElementById("ap-cancelar").addEventListener("click", resetFormPessoa);

document.getElementById("ap-salvar").addEventListener("click", async () => {
  const nome = document.getElementById("ap-nome").value.trim();
  if (!nome) { alert("Informe o nome."); return; }
  const id = document.getElementById("ap-id").value;
  const payload = {
    nome,
    papel: document.getElementById("ap-papel").value,
    ativo: document.getElementById("ap-ativo").checked,
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
  const linhas = state.clientes.map(c => ({
    cliente: c.nome,
    industry: c.industry_code,
    bu_director: c.bu_director ? c.bu_director.nome : "",
    am: c.am ? c.am.nome : "",
    dms: dmsLabel(c.dms),
    modificado: fmtData(c.modificado),
    prazo: c.pilares.prazo,
    escopo: c.pilares.escopo,
    rh: c.pilares.rh,
    contrato: c.pilares.contrato,
    faturamento: c.pilares.faturamento,
  }));
  exportarExcel(linhas, [
    { header: "Cliente", key: "cliente", width: 22 },
    { header: "Industry Code", key: "industry", width: 14 },
    { header: "BU Director", key: "bu_director", width: 20 },
    { header: "AM", key: "am", width: 20 },
    { header: "DM(s)", key: "dms", width: 28 },
    { header: "Modificado", key: "modificado", width: 14 },
    { header: "Prazo", key: "prazo", width: 10 },
    { header: "Escopo", key: "escopo", width: 10 },
    { header: "RH", key: "rh", width: 10 },
    { header: "Contrato", key: "contrato", width: 10 },
    { header: "Faturamento", key: "faturamento", width: 12 },
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
    status: r.status,
  }));
  exportarExcel(linhas, [
    { header: "Cliente", key: "cliente", width: 22 },
    { header: "Pilar", key: "pilar", width: 14 },
    { header: "Tipo", key: "tipo", width: 12 },
    { header: "Título", key: "titulo", width: 40 },
    { header: "Severidade", key: "severidade", width: 12 },
    { header: "Responsável", key: "responsavel", width: 22 },
    { header: "Data alvo", key: "data_alvo", width: 12 },
    { header: "Status", key: "status", width: 12 },
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
        <thead><tr><th>Cliente</th><th>Industry</th><th>AM</th><th>DM(s)</th><th>Prazo</th><th>Escopo</th><th>RH</th><th>Contrato</th><th>Faturamento</th></tr></thead>
        <tbody>
          ${clientesDoDir.map(c => `
            <tr>
              <td>${esc(c.nome)}</td>
              <td>${esc(c.industry_code)}</td>
              <td>${c.am ? esc(c.am.nome) : "—"}</td>
              <td>${esc(dmsLabel(c.dms))}</td>
              <td>${c.pilares.prazo}</td><td>${c.pilares.escopo}</td><td>${c.pilares.rh}</td>
              <td>${c.pilares.contrato}</td><td>${c.pilares.faturamento}</td>
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
  await loadPainel();
}

init().catch(err => {
  console.error(err);
  document.querySelector(".shell").insertAdjacentHTML("afterbegin",
    `<div class="modal-error" style="margin:20px 0">Falha ao carregar a aplicação: ${esc(err.message)}. Verifique se o backend está rodando.</div>`);
});
