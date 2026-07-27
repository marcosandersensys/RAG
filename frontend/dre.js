/* DRE — dashboard gerencial (menu DRE). Consome /api/dre/dashboard (dataset
   consolidado 2025+2026, gated ao dono). Réplica do design Claude Design em
   5 abas: Visão Geral, Evolução, Tipo Fornecimento, Clientes, Detalhes Clientes.
   Usa Chart.js (CDN). Reusa `api`/`esc` do app.js (mesmo escopo global). */
(function () {
  const C = {
    azul: "#1059AF", magenta: "#FC429A", roxo: "#663B8A", verde: "#16A34A",
    teal: "#0E9F9A", ambar: "#E08A1E", cinza: "#94A3B8", vermelho: "#DC2626",
    grid: "rgba(148,163,184,.18)", texto: "#475569",
  };
  const dre = { data: null, ano: "all", sub: "visao", cli: null, charts: [], wired: false };

  // ---------- helpers ----------
  function range() { return dre.ano === "2025" ? [0, 12] : dre.ano === "2026" ? [12, 17] : [0, 17]; }
  function sl(a) { const [i, j] = range(); return a.slice(i, j); }
  function meses() { return sl(dre.data.meses); }
  function sum(a) { return a.reduce((s, v) => s + (v || 0), 0); }
  function fmtBRL(v) {
    if (v == null || isNaN(v)) return "—";
    const a = Math.abs(v), s = v < 0 ? "-" : "";
    if (a >= 1e6) return `${s}R$ ${(a / 1e6).toFixed(1)}M`;
    if (a >= 1e3) return `${s}R$ ${Math.round(a / 1e3)}K`;
    return `${s}R$ ${Math.round(a)}`;
  }
  function fmtPct(v, d = 1) { return v == null || isNaN(v) ? "—" : `${v.toFixed(d)}%`; }
  function fmtPP(v) { return v == null || isNaN(v) ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)} pp`; }
  // margem ponderada pela RL sobre um recorte (rl[], margem%[])
  function margemPond(rl, mb) {
    let num = 0, den = 0;
    for (let i = 0; i < rl.length; i++) { num += (rl[i] || 0) * (mb[i] || 0); den += (rl[i] || 0); }
    return den ? num / den : 0;
  }
  function margemVal(rl, mb) { let x = 0; for (let i = 0; i < rl.length; i++) x += (rl[i] || 0) * (mb[i] || 0) / 100; return x; }
  function destroyCharts() { dre.charts.forEach(c => { try { c.destroy(); } catch (e) {} }); dre.charts = []; }

  const baseOpts = (extra = {}) => ({
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } },
      tooltip: { callbacks: {} },
    },
    scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } } },
    ...extra,
  });
  function mkChart(canvas, config) { const ch = new window.Chart(canvas.getContext("2d"), config); dre.charts.push(ch); return ch; }
  function yMoney() { return { grid: { color: C.grid }, ticks: { font: { size: 10 }, color: C.texto, callback: v => fmtBRL(v) } }; }
  function yPct() { return { position: "right", grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto, callback: v => v + "%" } }; }

  // ---------- KPI card ----------
  function kpi(label, big, sub, cor) {
    return `<div class="dre-kpi"><div class="dre-kpi-label">${esc(label)}</div>
      <div class="dre-kpi-num" style="${cor ? `color:${cor}` : ""}">${big}</div>
      <div class="dre-kpi-sub">${sub || ""}</div></div>`;
  }

  // ========== VISÃO GERAL ==========
  function renderVisao(box) {
    const e = dre.data.empresa, L = meses();
    const rl = sl(e.total.rl), mb = sl(e.total.margem_pct);
    const rlAcum = sum(rl), mbAcum = margemPond(rl, mb), mbAcumVal = margemVal(rl, mb);
    const srv = { rl: sl(e.servicos.rl), mb: sl(e.servicos.margem_pct) };
    const lic = { rl: sl(e.licenciamento.rl), mb: sl(e.licenciamento.margem_pct) };
    const eb = sl(e.ebitda), lu = sl(e.lucro);
    const ebAcum = sum(eb), luAcum = sum(lu);
    box.innerHTML = `
      <div class="dre-kpis">
        ${kpi("Receita Líquida Acum.", fmtBRL(rlAcum), periodoLabel(), C.azul)}
        ${kpi("Margem Bruta Acum.", fmtPct(mbAcum), fmtBRL(mbAcumVal), C.verde)}
        ${kpi("Margem Bruta — Serviços", fmtPct(margemPond(srv.rl, srv.mb)), fmtBRL(margemVal(srv.rl, srv.mb)), C.verde)}
        ${kpi("Margem Bruta — Licenciamento", fmtPct(margemPond(lic.rl, lic.mb)), fmtBRL(margemVal(lic.rl, lic.mb)), C.roxo)}
        ${kpi("EBITDA Acum.", fmtBRL(ebAcum), `${fmtPct(rlAcum ? ebAcum / rlAcum * 100 : 0)} da RL`, C.azul)}
        ${kpi("Lucro Líquido Acum.", fmtBRL(luAcum), `${fmtPct(rlAcum ? luAcum / rlAcum * 100 : 0)} da RL`, C.azul)}
      </div>
      <div class="card dre-chart-card">
        <div class="dre-chart-head">
          <span class="dre-chart-title">Receita Líquida & Margem Bruta — ${periodoLabel()}</span>
          <div class="dre-mini-toggle" id="dre-vg-tog">
            <button class="active" data-k="total">Total</button>
            <button data-k="servicos">Serviços</button>
            <button data-k="licenciamento">Licenciamento</button>
          </div>
        </div>
        <div class="dre-chart-wrap"><canvas id="dre-vg-rlmb"></canvas></div>
      </div>
      <div class="card dre-chart-card">
        <div class="dre-chart-head"><span class="dre-chart-title">EBITDA & Lucro Líquido — ${periodoLabel()}</span></div>
        <div class="dre-chart-wrap"><canvas id="dre-vg-eblu"></canvas></div>
      </div>`;
    const drawRlMb = (key) => {
      const src = key === "total" ? e.total : e[key];
      const r = sl(src.rl), m = sl(src.margem_pct);
      if (dre._vg) { try { dre._vg.destroy(); } catch (e) {} dre.charts = dre.charts.filter(c => c !== dre._vg); }
      dre._vg = mkChart(document.getElementById("dre-vg-rlmb"), {
        data: {
          labels: L,
          datasets: [
            { type: "bar", label: "Receita Líquida", data: r, backgroundColor: C.azul, borderRadius: 3, yAxisID: "y", order: 2 },
            { type: "line", label: "Margem Bruta %", data: m, borderColor: C.magenta, backgroundColor: C.magenta, tension: .3, yAxisID: "y1", order: 1, pointRadius: 2 },
          ],
        },
        options: baseOpts({
          scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } }, y: yMoney(), y1: yPct() },
          plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } },
            tooltip: { callbacks: { label: (c) => c.dataset.yAxisID === "y1" ? `${c.dataset.label}: ${fmtPct(c.parsed.y)}` : `${c.dataset.label}: ${fmtBRL(c.parsed.y)}` } } },
        }),
      });
    };
    drawRlMb("total");
    box.querySelectorAll("#dre-vg-tog button").forEach(b => b.addEventListener("click", () => {
      box.querySelectorAll("#dre-vg-tog button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); drawRlMb(b.dataset.k);
    }));
    mkChart(document.getElementById("dre-vg-eblu"), {
      type: "bar",
      data: { labels: L, datasets: [
        { label: "EBITDA", data: eb, backgroundColor: C.azul, borderRadius: 3 },
        { label: "Lucro Líquido", data: lu, backgroundColor: C.verde, borderRadius: 3 },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } }, y: yMoney() },
        plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtBRL(c.parsed.y)}` } } } }),
    });
  }

  // ========== EVOLUÇÃO ==========
  function renderEvolucao(box) {
    const e = dre.data.empresa, L = meses();
    const rl = sl(e.total.rl), mb = sl(e.total.margem_pct);
    const mom = rl.map((v, i) => i === 0 ? null : (rl[i - 1] ? (v - rl[i - 1]) / rl[i - 1] * 100 : null));
    const momValid = mom.filter(v => v != null);
    const crescMedio = momValid.length ? momValid.reduce((s, v) => s + v, 0) / momValid.length : 0;
    const crescAcum = rl[0] ? (rl[rl.length - 1] - rl[0]) / rl[0] * 100 : 0;
    const mbMedia = mb.reduce((s, v) => s + v, 0) / mb.length;
    let melhorI = 1, piorI = 1;
    mom.forEach((v, i) => { if (v == null) return; if (v > (mom[melhorI] ?? -1e9)) melhorI = i; if (v < (mom[piorI] ?? 1e9)) piorI = i; });
    const dpp = mb.map((v, i) => i === 0 ? null : v - mb[i - 1]);
    box.innerHTML = `
      <div class="dre-kpis">
        ${kpi("Crescimento médio MoM", `${crescMedio >= 0 ? "+" : ""}${crescMedio.toFixed(1)}%`, `média mensal · ${momValid.length} meses`, crescMedio >= 0 ? C.verde : C.vermelho)}
        ${kpi("Crescimento acumulado", `${crescAcum >= 0 ? "+" : ""}${crescAcum.toFixed(1)}%`, "1º → último mês", crescAcum >= 0 ? C.verde : C.vermelho)}
        ${kpi("Margem Bruta média", fmtPct(mbMedia), "média do período", C.azul)}
        ${kpi("Melhor / Pior mês (RL)", `${L[melhorI]} / ${L[piorI]}`, `${fmtPP(mom[melhorI])} · ${fmtPP(mom[piorI])}`, C.texto)}
      </div>
      <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">Variação MoM — Receita Líquida</span></div>
        <div class="dre-chart-wrap"><canvas id="dre-ev-rl"></canvas></div></div>
      <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">Variação — Margem Bruta %</span></div>
        <div class="dre-chart-wrap"><canvas id="dre-ev-mb"></canvas></div></div>
      <div class="card"><div class="table-wrap"><table class="tabela-fpa dre-tab">
        <thead><tr><th>Período</th><th class="num">Receita RL</th><th class="num">Cresc. MoM %</th><th class="num">Margem %</th><th class="num">Δ Margem</th></tr></thead>
        <tbody>${L.map((m, i) => `<tr><td>${m}</td><td class="num">${fmtBRL(rl[i])}</td>
          <td class="num" style="color:${mom[i] == null ? C.texto : mom[i] >= 0 ? C.verde : C.vermelho}">${mom[i] == null ? "—" : (mom[i] >= 0 ? "+" : "") + mom[i].toFixed(1) + "%"}</td>
          <td class="num">${fmtPct(mb[i])}</td>
          <td class="num" style="color:${dpp[i] == null ? C.texto : dpp[i] >= 0 ? C.verde : C.vermelho}">${dpp[i] == null ? "—" : fmtPP(dpp[i])}</td></tr>`).join("")}</tbody>
      </table></div></div>`;
    mkChart(document.getElementById("dre-ev-rl"), {
      data: { labels: L, datasets: [
        { type: "bar", label: "Receita Líquida", data: rl, backgroundColor: C.azul, borderRadius: 3, yAxisID: "y", order: 2 },
        { type: "line", label: "Crescimento MoM %", data: mom, borderColor: C.magenta, backgroundColor: C.magenta, tension: .3, yAxisID: "y1", order: 1, pointRadius: 2, spanGaps: true },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } }, y: yMoney(), y1: yPct() },
        plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } }, tooltip: { callbacks: { label: c => c.dataset.yAxisID === "y1" ? `${c.dataset.label}: ${c.parsed.y == null ? "—" : c.parsed.y.toFixed(1) + "%"}` : `${c.dataset.label}: ${fmtBRL(c.parsed.y)}` } } } }),
    });
    mkChart(document.getElementById("dre-ev-mb"), {
      data: { labels: L, datasets: [
        { type: "line", label: "Margem Bruta %", data: mb, borderColor: C.magenta, backgroundColor: C.magenta, tension: .3, pointRadius: 2 },
        { type: "line", label: "Margem média", data: mb.map(() => mbMedia), borderColor: C.cinza, borderDash: [5, 4], pointRadius: 0 },
      ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } }, y: { grid: { color: C.grid }, ticks: { font: { size: 10 }, color: C.texto, callback: v => v + "%" } } },
        plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtPct(c.parsed.y)}` } } } }),
    });
  }

  // ========== TIPO FORNECIMENTO ==========
  function parBloco(box, id, titulo, aRl, aMb, bRl, bMb, aLabel, bLabel, aCor, bCor) {
    const L = meses();
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="dre-sec-title">${esc(titulo)}</div>
      <div class="dre-grid3">
        <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">Receita Líquida mensal</span></div><div class="dre-chart-wrap sm"><canvas id="${id}-rl"></canvas></div></div>
        <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">% da Receita Líquida</span></div><div class="dre-chart-wrap sm"><canvas id="${id}-pct"></canvas></div></div>
        <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">Margem % mensal</span></div><div class="dre-chart-wrap sm"><canvas id="${id}-mb"></canvas></div></div>
      </div>`;
    box.appendChild(wrap);
    const pctA = aRl.map((v, i) => { const t = v + bRl[i]; return t ? v / t * 100 : 0; });
    const pctB = aRl.map((v, i) => { const t = v + bRl[i]; return t ? bRl[i] / t * 100 : 0; });
    mkChart(document.getElementById(`${id}-rl`), {
      type: "bar", data: { labels: L, datasets: [
        { label: aLabel, data: aRl, backgroundColor: aCor, borderRadius: 2 },
        { label: bLabel, data: bRl, backgroundColor: bCor, borderRadius: 2 } ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 9 }, color: C.texto } }, y: yMoney() },
        plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 }, color: C.texto } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtBRL(c.parsed.y)}` } } } }),
    });
    mkChart(document.getElementById(`${id}-pct`), {
      type: "bar", data: { labels: L, datasets: [
        { label: aLabel, data: pctA, backgroundColor: aCor, stack: "s" },
        { label: bLabel, data: pctB, backgroundColor: bCor, stack: "s" } ] },
      options: baseOpts({ scales: { x: { stacked: true, grid: { display: false }, ticks: { font: { size: 9 }, color: C.texto } }, y: { stacked: true, max: 100, grid: { color: C.grid }, ticks: { font: { size: 10 }, color: C.texto, callback: v => v + "%" } } },
        plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 }, color: C.texto } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } } } }),
    });
    mkChart(document.getElementById(`${id}-mb`), {
      data: { labels: L, datasets: [
        { type: "line", label: aLabel, data: aMb, borderColor: aCor, backgroundColor: aCor, tension: .3, pointRadius: 2 },
        { type: "line", label: bLabel, data: bMb, borderColor: bCor, backgroundColor: bCor, tension: .3, pointRadius: 2 } ] },
      options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 9 }, color: C.texto } }, y: { grid: { color: C.grid }, ticks: { font: { size: 10 }, color: C.texto, callback: v => v + "%" } } },
        plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 }, color: C.texto } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmtPct(c.parsed.y)}` } } } }),
    });
  }
  function renderTipo(box) {
    const e = dre.data.empresa;
    const srvRl = sl(e.servicos.rl), srvMb = sl(e.servicos.margem_pct);
    const licRl = sl(e.licenciamento.rl), licMb = sl(e.licenciamento.margem_pct);
    const gerRl = sl(e.gerenciados.rl), gerMb = sl(e.gerenciados.margem_pct);
    const ngRl = sl(e.nao_gerenciados.rl), ngMb = sl(e.nao_gerenciados.margem_pct);
    const totRl = sum(srvRl) + sum(licRl);
    box.innerHTML = `<div class="dre-kpis">
      ${kpi("RL Serviços (acum.)", fmtBRL(sum(srvRl)), `${fmtPct(totRl ? sum(srvRl) / totRl * 100 : 0)} do total`, C.azul)}
      ${kpi("RL Licenciamento (acum.)", fmtBRL(sum(licRl)), `${fmtPct(totRl ? sum(licRl) / totRl * 100 : 0)} do total`, C.roxo)}
      ${kpi("Margem Serviços", fmtPct(margemPond(srvRl, srvMb)), fmtBRL(margemVal(srvRl, srvMb)), C.verde)}
      ${kpi("Margem Licenciamento", fmtPct(margemPond(licRl, licMb)), fmtBRL(margemVal(licRl, licMb)), C.roxo)}
    </div><div class="dre-aviso">⚠ A abertura por tipo de fornecimento é apenas no nível empresa — a base não permite quebrar Serviços/Licenciamento nem Gerenciados/Não-Gerenciados por cliente.</div>
    <div id="dre-tipo-blocos"></div>`;
    const blocos = document.getElementById("dre-tipo-blocos");
    parBloco(blocos, "dre-sl", "Serviços × Licenciamento", srvRl, srvMb, licRl, licMb, "Serviços", "Licenciamento", C.azul, C.roxo);
    parBloco(blocos, "dre-gn", "Gerenciados × Não Gerenciados (dentro de Serviços)", gerRl, gerMb, ngRl, ngMb, "Gerenciados", "Não Gerenciados", C.teal, C.ambar);
  }

  // ========== CLIENTES ==========
  function renderClientes(box) {
    const L = meses(), e = dre.data.empresa;
    const totalRl = sum(sl(e.total.rl));
    const linhas = dre.data.clientes.map(c => ({ nome: c.nome, rl: sum(sl(c.rl)), mb: margemPond(sl(c.rl), sl(c.margem_pct)) }));
    linhas.push({ nome: "Outros", rl: sum(sl(dre.data.outros_rl)), mb: null });
    linhas.sort((a, b) => b.rl - a.rl);
    const maxRl = Math.max(...linhas.map(l => l.rl));
    const top5 = linhas.filter(l => l.nome !== "Outros").slice(0, 5);
    const conc = totalRl ? top5.reduce((s, l) => s + l.rl, 0) / totalRl * 100 : 0;
    box.innerHTML = `
      <div class="dre-kpis">
        ${kpi("Concentração · Top 5 clientes", fmtPct(conc), top5.map(l => l.nome).join(" · "), C.magenta)}
        ${kpi("Receita Líquida — Total", fmtBRL(totalRl), periodoLabel(), C.azul)}
        ${kpi("Nº clientes desmembrados", "7", "+ Outros agregado", C.texto)}
      </div>
      <div class="card"><div class="dre-chart-head"><span class="dre-chart-title">Ranking — Receita Líquida acumulada · ${periodoLabel()}</span></div>
      <div class="table-wrap"><table class="tabela-fpa dre-tab">
        <thead><tr><th>#</th><th>Cliente</th><th style="width:220px">Participação</th><th class="num">RL Acum.</th><th class="num">%</th><th class="num">Margem</th></tr></thead>
        <tbody>${linhas.map((l, i) => `<tr>
          <td>${i + 1}</td><td class="${l.nome === "Outros" ? "" : "fpa-cliente-nome"}">${esc(l.nome)}</td>
          <td><div class="dre-bar-bg"><div class="dre-bar-fill" style="width:${maxRl ? l.rl / maxRl * 100 : 0}%;background:${l.nome === "Outros" ? C.cinza : C.azul}"></div></div></td>
          <td class="num">${fmtBRL(l.rl)}</td><td class="num">${fmtPct(totalRl ? l.rl / totalRl * 100 : 0)}</td>
          <td class="num">${l.mb == null ? "—" : fmtPct(l.mb)}</td></tr>`).join("")}</tbody>
      </table></div></div>
      ${dreYoYBlocos()}
      <div class="dre-sec-title">Receita Líquida & Margem % por cliente</div>
      <div class="dre-grid3" id="dre-cli-mini"></div>`;
    const mini = document.getElementById("dre-cli-mini");
    dre.data.clientes.forEach(c => {
      const d = document.createElement("div"); d.className = "card dre-chart-card";
      d.innerHTML = `<div class="dre-chart-head"><span class="dre-chart-title">${esc(c.nome)}</span></div><div class="dre-chart-wrap sm"><canvas></canvas></div>`;
      mini.appendChild(d);
      mkChart(d.querySelector("canvas"), {
        data: { labels: L, datasets: [
          { type: "bar", label: "RL", data: sl(c.rl), backgroundColor: C.azul, borderRadius: 2, yAxisID: "y", order: 2 },
          { type: "line", label: "MB %", data: sl(c.margem_pct), borderColor: C.magenta, backgroundColor: C.magenta, tension: .3, pointRadius: 1.5, yAxisID: "y1", order: 1 } ] },
        options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 8 }, color: C.texto } }, y: { grid: { color: C.grid }, ticks: { font: { size: 9 }, color: C.texto, callback: v => fmtBRL(v) } }, y1: yPct() },
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: c2 => c2.dataset.yAxisID === "y1" ? `MB: ${fmtPct(c2.parsed.y)}` : `RL: ${fmtBRL(c2.parsed.y)}` } } } }),
      });
    });
  }
  // YoY Jan–Mai/25 vs Jan–Mai/26 (fixo, independe do filtro de ano) — só no modo all/…
  function dreYoYBlocos() {
    const idx25 = [0, 1, 2, 3, 4], idx26 = [12, 13, 14, 15, 16];
    const rows = dre.data.clientes.map(c => {
      const a = idx25.reduce((s, i) => s + c.rl[i], 0), b = idx26.reduce((s, i) => s + c.rl[i], 0);
      const mbA = margemPond(idx25.map(i => c.rl[i]), idx25.map(i => c.margem_pct[i]));
      const mbB = margemPond(idx26.map(i => c.rl[i]), idx26.map(i => c.margem_pct[i]));
      return { nome: c.nome, a, b, varRl: a ? (b - a) / a * 100 : null, dmb: mbB - mbA };
    });
    const cresc = rows.filter(r => r.varRl != null && r.varRl >= 0).sort((x, y) => y.varRl - x.varRl).slice(0, 6);
    const eros = rows.filter(r => r.varRl != null && r.varRl < 0).sort((x, y) => x.varRl - y.varRl).slice(0, 6);
    const tbl = (titulo, arr) => `<div class="card"><div class="dre-chart-head"><span class="dre-chart-title">${titulo}</span></div>
      <div class="table-wrap"><table class="tabela-fpa dre-tab"><thead><tr><th>Cliente</th><th class="num">Jan–Mai/25</th><th class="num">Jan–Mai/26</th><th class="num">Var. RL YoY</th><th class="num">Δ MB (pp)</th></tr></thead>
      <tbody>${arr.map(r => `<tr><td class="fpa-cliente-nome">${esc(r.nome)}</td><td class="num">${fmtBRL(r.a)}</td><td class="num">${fmtBRL(r.b)}</td>
        <td class="num" style="color:${r.varRl >= 0 ? C.verde : C.vermelho}">${r.varRl == null ? "—" : (r.varRl >= 0 ? "+" : "") + r.varRl.toFixed(1) + "%"}</td>
        <td class="num" style="color:${r.dmb >= 0 ? C.verde : C.vermelho}">${fmtPP(r.dmb)}</td></tr>`).join("")}</tbody></table></div></div>`;
    return `<div class="dre-sec-title">Comparativo YoY YTD — Jan–Mai/25 vs Jan–Mai/26 <span class="dre-fixo">· fixo, independe do filtro</span></div>
      <div class="dre-grid2">${tbl("Top crescimento YoY", cresc)}${tbl("Erosão / Atenção YoY", eros)}</div>`;
  }

  // ========== DETALHES CLIENTES ==========
  function renderDetalhes(box) {
    const L = meses();
    if (!dre.cli) dre.cli = dre.data.clientes[0].nome;
    box.innerHTML = `
      <div class="dre-detalhe-head">
        <label>Cliente:</label>
        <select id="dre-cli-sel">${dre.data.clientes.map(c => `<option ${c.nome === dre.cli ? "selected" : ""}>${esc(c.nome)}</option>`).join("")}</select>
      </div>
      <div id="dre-detalhe-corpo"></div>`;
    const sel = document.getElementById("dre-cli-sel");
    sel.addEventListener("change", () => { dre.cli = sel.value; drawDetalhe(); });
    drawDetalhe();
    function drawDetalhe() {
      const c = dre.data.clientes.find(x => x.nome === dre.cli);
      const rl = sl(c.rl), mb = sl(c.margem_pct);
      const rlAcum = sum(rl), mbPond = margemPond(rl, mb);
      const corpo = document.getElementById("dre-detalhe-corpo");
      corpo.innerHTML = `
        <div class="dre-kpis">
          ${kpi("Receita Líquida Acum.", fmtBRL(rlAcum), periodoLabel(), C.azul)}
          ${kpi("Margem Bruta média", fmtPct(mbPond), fmtBRL(margemVal(rl, mb)), C.verde)}
          ${kpi("Melhor mês (RL)", L[rl.indexOf(Math.max(...rl))], fmtBRL(Math.max(...rl)), C.texto)}
        </div>
        <div class="card dre-chart-card"><div class="dre-chart-head"><span class="dre-chart-title">${esc(c.nome)} — Receita Líquida & Margem %</span></div>
          <div class="dre-chart-wrap"><canvas id="dre-det-chart"></canvas></div></div>
        <div class="card"><div class="table-wrap"><table class="tabela-fpa dre-tab">
          <thead><tr><th>Período</th><th class="num">Receita Líquida</th><th class="num">Margem %</th></tr></thead>
          <tbody>${L.map((m, i) => `<tr><td>${m}</td><td class="num">${fmtBRL(rl[i])}</td><td class="num">${fmtPct(mb[i])}</td></tr>`).join("")}</tbody>
        </table></div></div>`;
      // recria o chart destruindo o anterior desta aba
      mkChart(document.getElementById("dre-det-chart"), {
        data: { labels: L, datasets: [
          { type: "bar", label: "Receita Líquida", data: rl, backgroundColor: C.azul, borderRadius: 3, yAxisID: "y", order: 2 },
          { type: "line", label: "Margem Bruta %", data: mb, borderColor: C.magenta, backgroundColor: C.magenta, tension: .3, pointRadius: 2, yAxisID: "y1", order: 1 } ] },
        options: baseOpts({ scales: { x: { grid: { display: false }, ticks: { font: { size: 10 }, color: C.texto } }, y: yMoney(), y1: yPct() },
          plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 }, color: C.texto } }, tooltip: { callbacks: { label: c2 => c2.dataset.yAxisID === "y1" ? `${c2.dataset.label}: ${fmtPct(c2.parsed.y)}` : `${c2.dataset.label}: ${fmtBRL(c2.parsed.y)}` } } } }),
      });
    }
  }

  function periodoLabel() {
    const m = meses();
    return `${m[0]} – ${m[m.length - 1]}`;
  }

  // ---------- render dispatcher ----------
  function render() {
    destroyCharts(); dre._vg = null;
    const box = document.getElementById("dre-conteudo");
    if (!dre.data) { box.innerHTML = `<p class="hint">Carregando…</p>`; return; }
    ({ visao: renderVisao, evolucao: renderEvolucao, tipo: renderTipo, clientes: renderClientes, detalhes: renderDetalhes }[dre.sub] || renderVisao)(box);
  }

  function wire() {
    if (dre.wired) return; dre.wired = true;
    document.querySelectorAll("#dre-ano-toggle .dre-ano-btn").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll("#dre-ano-toggle .dre-ano-btn").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); dre.ano = b.dataset.ano; render();
    }));
    document.querySelectorAll("#dre-subtabs .dre-subtab").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll("#dre-subtabs .dre-subtab").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); dre.sub = b.dataset.sub; render();
    }));
  }

  async function loadDre() {
    wire();
    if (!dre.data) {
      try { dre.data = await api("/api/dre/dashboard"); }
      catch (e) { document.getElementById("dre-conteudo").innerHTML = `<div class="card"><div class="empty-state">Não foi possível carregar o DRE (${esc(e.message)}).</div></div>`; return; }
    }
    render();
  }
  window.loadDre = loadDre;
})();
