/* ============================================================
   app.js — utilidades compartilhadas + lógica de cada tela.
   Depende de api.js (Api, MOCK_UNIDADES, GRUPAMENTOS, TURNOS,
   MOCK_PERGUNTAS) já carregado antes deste arquivo.
   ============================================================ */

const App = {};

/* ---------------------------- utilidades gerais ---------------------------- */

App.qs = (sel, root) => (root || document).querySelector(sel);
App.qsa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

App.getParam = (name) => new URLSearchParams(window.location.search).get(name);

App.getCriancaId = () => App.getParam("crianca_id") || localStorage.getItem("creche_crianca_id") || null;

App.setCriancaId = (id) => localStorage.setItem("creche_crianca_id", id);

App.goTo = (page, extraParams) => {
  const params = new URLSearchParams(extraParams || {});
  const id = App.getCriancaId();
  if (id && !params.has("crianca_id")) params.set("crianca_id", id);
  const qs = params.toString();
  window.location.href = page + (qs ? "?" + qs : "");
};

App.formatDatePt = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric" });
  } catch (_) { return "—"; }
};

App.formatDateHoraPt = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch (_) { return "—"; }
};

App.diasRestantes = (iso) => {
  if (!iso) return -1;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / (1000 * 60 * 60 * 24));
};

App.ordinal = (n) => `${n}ª`;

// mensagens de erro amigáveis — a família não deveria ver "Failed to fetch"
App.mensagemErroAmigavel = (err) => {
  if (!err) return "Algo deu errado. Tente novamente.";
  if (err.status === 0) return "Não conseguimos conectar. Verifique sua internet e tente de novo.";
  if (err.status === 404) return "Não encontramos sua inscrição. Confira o link ou inscreva-se novamente.";
  if (err.status === 422) return err.message || "Essa ação não é mais possível.";
  return err.message || "Algo deu errado do nosso lado. Tente novamente em instantes.";
};

App.bannerHtml = (tipo, mensagem, tituloOpt) => `
  <div class="banner banner-${tipo}" role="status">
    <span aria-hidden="true">${tipo === "error" ? "⚠️" : tipo === "success" ? "✅" : tipo === "warning" ? "⏳" : "ℹ️"}</span>
    <span>${tituloOpt ? `<b>${tituloOpt}</b><br>` : ""}${mensagem}</span>
  </div>
`;

App.loadingHtml = (texto) => `
  <div class="loading-state">
    <div class="glyph" aria-hidden="true">⏳</div>
    <p>${texto || "Carregando..."}</p>
  </div>
`;

App.emptyHtml = (texto) => `
  <div class="empty-state">
    <div class="glyph" aria-hidden="true">🗂️</div>
    <p>${texto}</p>
  </div>
`;

App.erroHtml = (texto, comBotaoRetentar) => `
  <div class="error-state">
    <div class="glyph" aria-hidden="true">⚠️</div>
    <p>${texto}</p>
    ${comBotaoRetentar ? `<button class="btn btn-secondary btn-sm" data-acao="retentar" style="margin-top:12px;">Tentar de novo</button>` : ""}
  </div>
`;

/* ============================================================
   TELA 1 — Inscrição
   ============================================================ */

App.initInscricao = function () {
  const MAX_PREFS = 5;
  const listaEl = App.qs("#lista-preferencias");
  const perguntasEl = App.qs("#lista-perguntas");
  const form = App.qs("#form-inscricao");
  const btnAdicionar = App.qs("#btn-adicionar-pref");
  const bannerEl = App.qs("#form-banner");
  const btnEnviar = App.qs("#btn-enviar");

  let prefCount = 0;

  function optionsHtml(list, valueKey, labelKey) {
    return list.map((item) => {
      const value = valueKey ? item[valueKey] : item;
      const label = labelKey ? item[labelKey] : item;
      return `<option value="${value}">${label}</option>`;
    }).join("");
  }

  function criarLinhaPreferencia() {
    if (prefCount >= MAX_PREFS) return;
    prefCount++;
    const idx = prefCount;
    const row = document.createElement("div");
    row.className = "pref-row";
    row.dataset.idx = idx;
    row.innerHTML = `
      <div class="pref-row-head">
        <span class="pref-badge"><span class="n">${idx}</span> ${idx === 1 ? "1ª opção (preferida)" : idx + "ª opção"}</span>
        ${idx > 1 ? `<button type="button" class="icon-btn" data-acao="remover">Remover</button>` : ""}
      </div>
      <div class="pref-grid">
        <div class="field full" style="margin-bottom:0;">
          <label>Unidade / creche</label>
          <select class="input" data-campo="unidade" required>
            <option value="" disabled selected>Escolha a unidade</option>
            ${optionsHtml(MOCK_UNIDADES, "unidade", "nome_unidade")}
          </select>
        </div>
        <div class="field" style="margin-bottom:0;">
          <label>Turma</label>
          <select class="input" data-campo="grupamento" required>
            <option value="" disabled selected>Turma</option>
            ${optionsHtml(GRUPAMENTOS)}
          </select>
        </div>
        <div class="field" style="margin-bottom:0;">
          <label>Turno</label>
          <select class="input" data-campo="turno" required>
            <option value="" disabled selected>Turno</option>
            ${optionsHtml(TURNOS)}
          </select>
        </div>
      </div>
    `;
    listaEl.appendChild(row);
    atualizarBotaoAdicionar();
  }

  function renumerar() {
    App.qsa(".pref-row", listaEl).forEach((row, i) => {
      const idx = i + 1;
      row.dataset.idx = idx;
      App.qs(".n", row).textContent = idx;
      App.qs(".pref-badge", row).innerHTML =
        `<span class="n">${idx}</span> ${idx === 1 ? "1ª opção (preferida)" : idx + "ª opção"}`;
    });
    prefCount = App.qsa(".pref-row", listaEl).length;
    atualizarBotaoAdicionar();
  }

  function atualizarBotaoAdicionar() {
    btnAdicionar.style.display = prefCount >= MAX_PREFS ? "none" : "";
  }

  listaEl.addEventListener("click", (e) => {
    const btn = e.target.closest('[data-acao="remover"]');
    if (!btn) return;
    btn.closest(".pref-row").remove();
    renumerar();
  });

  btnAdicionar.addEventListener("click", criarLinhaPreferencia);

  // perguntas sim/não
  perguntasEl.innerHTML = MOCK_PERGUNTAS.map((p) => `
    <div class="yn-item" data-perg-id="${p.perg_id}">
      <span class="yn-question">${p.texto}</span>
      <span class="yn-toggle" role="group" aria-label="${p.texto}">
        <button type="button" class="yn-btn sim" data-valor="true" aria-pressed="false">Sim</button>
        <button type="button" class="yn-btn no" data-valor="false" aria-pressed="true">Não</button>
      </span>
    </div>
  `).join("");

  perguntasEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".yn-btn");
    if (!btn) return;
    const grupo = btn.closest(".yn-toggle");
    App.qsa(".yn-btn", grupo).forEach((b) => b.setAttribute("aria-pressed", "false"));
    btn.setAttribute("aria-pressed", "true");
  });

  // primeira linha de preferência já vem pronta
  criarLinhaPreferencia();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    bannerEl.innerHTML = "";

    const bairroCep = App.qs("#bairro-cep").value.trim();
    if (!bairroCep) {
      bannerEl.innerHTML = App.bannerHtml("error", "Informe o bairro ou o CEP da família.");
      App.qs("#bairro-cep").focus();
      return;
    }

    const linhas = App.qsa(".pref-row", listaEl);
    const preferencias = [];
    for (const row of linhas) {
      const unidade = App.qs('[data-campo="unidade"]', row).value;
      const grupamento = App.qs('[data-campo="grupamento"]', row).value;
      const turno = App.qs('[data-campo="turno"]', row).value;
      if (!unidade || !grupamento || !turno) {
        bannerEl.innerHTML = App.bannerHtml("error", "Complete unidade, turma e turno em todas as opções escolhidas, ou remova a opção incompleta.");
        return;
      }
      preferencias.push({ unidade, grupamento, turno });
    }
    if (preferencias.length === 0) {
      bannerEl.innerHTML = App.bannerHtml("error", "Escolha ao menos 1 opção de creche.");
      return;
    }

    const respostas = {};
    App.qsa(".yn-item", perguntasEl).forEach((item) => {
      const pergId = item.dataset.pergId;
      const pressed = App.qs('.yn-btn[aria-pressed="true"]', item);
      respostas[pergId] = pressed ? pressed.dataset.valor === "true" : false;
    });

    btnEnviar.disabled = true;
    btnEnviar.textContent = "Enviando...";

    try {
      const resposta = await Api.enviarInscricao({ bairro_cep: bairroCep, preferencias, respostas });
      App.setCriancaId(resposta.crianca_id);
      localStorage.setItem("creche_inscricao_" + resposta.crianca_id, JSON.stringify({
        bairro_cep: bairroCep,
        preferencias,
        unidade_comprovacao_sugerida: resposta.unidade_comprovacao_sugerida,
      }));
      App.goTo("verificacao.html", { crianca_id: resposta.crianca_id });
    } catch (err) {
      bannerEl.innerHTML = App.bannerHtml("error", App.mensagemErroAmigavel(err), "Não foi possível enviar sua inscrição");
      btnEnviar.disabled = false;
      btnEnviar.textContent = "Enviar inscrição";
    }
  });
};
