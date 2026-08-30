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

App.initInscricao = async function () {
  const MAX_PREFS = 5;
  const listaEl = App.qs("#lista-preferencias");
  const perguntasEl = App.qs("#lista-perguntas");
  const form = App.qs("#form-inscricao");
  const btnAdicionar = App.qs("#btn-adicionar-pref");
  const bannerEl = App.qs("#form-banner");
  const btnEnviar = App.qs("#btn-enviar");

  let prefCount = 0;
  let unidades;
  try {
    unidades = await Api.listarUnidades();
  } catch (err) {
    listaEl.innerHTML = App.erroHtml("Não foi possível carregar a lista de unidades. Recarregue a página para tentar de novo.");
    btnAdicionar.style.display = "none";
    btnEnviar.disabled = true;
    return;
  }

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
            ${optionsHtml(unidades, "unidade", "nome_unidade")}
          </select>
        </div>
        <div class="field" style="margin-bottom:0;">
          <label>Faixa etária</label>
          <select class="input" data-campo="grupamento" required>
            <option value="" disabled selected>Faixa etária</option>
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

    const nome = App.qs("#crianca-nome").value.trim();
    const dataNascimento = App.qs("#crianca-nascimento").value.trim();
    const responsavelNome = App.qs("#responsavel-nome").value.trim();
    const responsavelTelefone = App.qs("#responsavel-telefone").value.trim();
    if (!nome || !dataNascimento || !responsavelNome || !responsavelTelefone) {
      bannerEl.innerHTML = App.bannerHtml("error", "Preencha o nome e a data de nascimento da criança, e o nome e telefone do responsável.");
      return;
    }

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
      const infoUnidade = unidades.find((u) => String(u.unidade) === String(unidade));
      preferencias.push({ unidade, grupamento, turno, nome_unidade: infoUnidade ? infoUnidade.nome_unidade : unidade });
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
      const resposta = await Api.enviarInscricao({
        nome,
        data_nascimento: dataNascimento,
        responsavel_nome: responsavelNome,
        responsavel_telefone: responsavelTelefone,
        bairro_cep: bairroCep,
        preferencias,
        respostas,
      });
      App.setCriancaId(resposta.crianca_id);
      localStorage.setItem("creche_inscricao_" + resposta.crianca_id, JSON.stringify({
        bairro_cep: bairroCep,
        preferencias,
        respostas,
        score: resposta.score,
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

/* ============================================================
   TELA 2 — Verificação / comprovação de documentos
   ============================================================ */

App.initVerificacao = function () {
  const AUTO_CONFIRMA_SEGUNDOS = 20;
  const root = App.qs("#conteudo-verificacao");
  const criancaId = App.getCriancaId();

  if (!criancaId) {
    root.innerHTML = App.erroHtml("Não encontramos sua inscrição. Comece pela tela de inscrição.");
    App.qs("#cta-continuar").style.display = "none";
    return;
  }

  const dados = JSON.parse(localStorage.getItem("creche_inscricao_" + criancaId) || "null");
  if (!dados || !dados.unidade_comprovacao_sugerida) {
    root.innerHTML = App.erroHtml("Não encontramos os dados dessa inscrição neste aparelho. Se você já se inscreveu em outro celular, isso é esperado — fale com a equipe da creche.");
    App.qs("#cta-continuar").style.display = "none";
    return;
  }

  const sugerida = dados.unidade_comprovacao_sugerida;
  const preferencias = dados.preferencias || [];
  let escolhidaUnidade = sugerida.unidade;
  let contadorId = null;
  let segundosRestantes = AUTO_CONFIRMA_SEGUNDOS;

  function nomeDaUnidade(codigoUnidade) {
    if (codigoUnidade === sugerida.unidade) return sugerida.nome_unidade;
    const pref = preferencias.find((p) => p.unidade === codigoUnidade);
    if (pref && pref.nome_unidade) return pref.nome_unidade;
    const info = MOCK_UNIDADES.find((u) => u.unidade === codigoUnidade);
    return info ? info.nome_unidade : codigoUnidade;
  }

  function pararContador(motivoTexto) {
    if (contadorId) clearInterval(contadorId);
    const el = App.qs("#contador-auto");
    if (el) el.outerHTML = motivoTexto ? `<p class="meta-line" id="contador-auto">${motivoTexto}</p>` : "";
  }

  function render() {
    const distanciaTxt = sugerida.distancia_km != null ? `≈ ${String(sugerida.distancia_km).replace(".", ",")} km do bairro informado` : "distância não calculada";

    const outrasOpcoes = preferencias.filter((p) => p.unidade !== sugerida.unidade);
    const criterios = criteriosDeclarados(dados.respostas);

    root.innerHTML = `
      <div class="card">
        <p class="small-caps">Unidade sugerida para comprovação</p>
        <p class="section-title" style="font-size:18px;margin-top:6px;">${sugerida.nome_unidade}</p>
        <p class="section-sub" style="margin-bottom:0;">${distanciaTxt}</p>
      </div>

      <div style="margin-top:12px;">
        ${App.bannerHtml("info", "Essa distância é aproximada, calculada pelo bairro informado — não temos o endereço exato da família, só o bairro (dado anonimizado por privacidade).")}
      </div>

      ${criterios.length > 0 ? `
      <div class="card" style="margin-top:12px;">
        <p class="section-title">Critérios que você declarou</p>
        <p class="section-sub">Leve os documentos que comprovem cada um. Sua pontuação atual (${dados.score} de ${SCORE_MAXIMO_2025} pontos) considera todos eles.</p>
        <div class="stack-tight">
          ${criterios.map((c) => `
            <div class="pref-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
              <span style="font-size:13.5px;">${c.texto}</span>
              ${c.criterio
                ? `<span class="badge badge-baixa" style="flex:none;">Critério de desempate</span>`
                : `<span class="badge badge-media" style="flex:none;">+${c.pontos} pts</span>`}
            </div>
          `).join("")}
        </div>
      </div>
      <div style="margin-top:12px;">
        ${App.bannerHtml("warning", "Se algum critério não puder ser comprovado com documento, ele é removido do cálculo — sua pontuação é recalculada sem ele, e sua posição na fila pode mudar. Isso não zera sua pontuação nem desclassifica sua inscrição.", "Importante")}
      </div>
      ` : `
      <div style="margin-top:12px;">
        ${App.bannerHtml("info", "Você não declarou nenhum critério de pontuação — sua posição na fila segue pela ordem de inscrição e critérios de desempate.")}
      </div>
      `}

      ${outrasOpcoes.length > 0 ? `
      <div class="card" style="margin-top:12px;">
        <p class="section-title">Prefere levar os documentos em outra unidade?</p>
        <p class="section-sub">Só entre as opções que a família já escolheu na inscrição.</p>
        <div class="stack-tight" id="opcoes-unidade" role="radiogroup">
          ${[sugerida.unidade, ...outrasOpcoes.map((p) => p.unidade)].map((codigo) => `
            <label class="pref-row" style="display:flex;align-items:center;gap:10px;cursor:pointer;">
              <input type="radio" name="unidade-comprovacao" value="${codigo}" ${codigo === escolhidaUnidade ? "checked" : ""} style="width:18px;height:18px;flex:none;">
              <span>${nomeDaUnidade(codigo)}${codigo === sugerida.unidade ? " <span class=\"small-caps\">(sugerida)</span>" : ""}</span>
            </label>
          `).join("")}
        </div>
      </div>` : ""}

      <p class="meta-line" id="contador-auto" style="margin-top:14px;">
        <span class="countdown" id="countdown-badge">⏱ Confirmando a sugestão em ${segundosRestantes}s</span>
      </p>
    `;

    const grupo = App.qs("#opcoes-unidade");
    if (grupo) {
      grupo.addEventListener("change", (e) => {
        escolhidaUnidade = e.target.value;
        pararContador("Unidade escolhida por você — não vamos alterar automaticamente.");
      });
    }
  }

  render();

  contadorId = setInterval(() => {
    segundosRestantes -= 1;
    const badge = App.qs("#countdown-badge");
    if (badge) badge.textContent = `⏱ Confirmando a sugestão em ${segundosRestantes}s`;
    if (segundosRestantes <= 0) {
      pararContador(`✓ Confirmamos a unidade sugerida automaticamente: ${sugerida.nome_unidade}.`);
    }
  }, 1000);

  App.qs("#cta-continuar").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = "Confirmando...";
    try {
      await Api.confirmarUnidade(criancaId, escolhidaUnidade);
      pararContador();
      localStorage.setItem("creche_comprovacao_" + criancaId, JSON.stringify({
        unidade: escolhidaUnidade,
        nome_unidade: nomeDaUnidade(escolhidaUnidade),
      }));
      App.goTo("classificacao.html", { crianca_id: criancaId });
    } catch (err) {
      root.insertAdjacentHTML("afterbegin", App.bannerHtml("error", App.mensagemErroAmigavel(err), "Não foi possível confirmar a unidade"));
      btn.disabled = false;
      btn.textContent = "Continuar e acompanhar minha fila";
    }
  });
};

/* ============================================================
   TELA 3 — Classificação (a tela mais importante)
   ============================================================ */

App.initClassificacao = function () {
  const root = App.qs("#conteudo-classificacao");
  const criancaId = App.getCriancaId();
  const cacheKey = "creche_classificacao_cache_" + criancaId;

  if (!criancaId) {
    root.innerHTML = App.erroHtml("Não encontramos sua inscrição. Comece pela tela de inscrição.");
    return;
  }

  const STATUS_LABEL = {
    dentro: "Dentro da chamada atual",
    espera: "Lista de espera",
    fora: "Fora da vaga por enquanto",
  };
  const CHANCE_LABEL = { alta: "Chance alta", media: "Chance média", baixa: "Chance baixa" };

  let dadosAtuais = null;   // { classificacoes, sugestoes }
  let modoTroca = false;
  let ordemEmEdicao = [];

  function badgeStatus(status) {
    return `<span class="badge badge-${status}">${STATUS_LABEL[status] || status}</span>`;
  }

  function cardClassificacao(item, idx) {
    const dias = App.diasRestantes(item.pode_trocar_ate);
    const podeTrocar = dias > 0;
    return `
      <div class="card">
        <p class="small-caps">${item.programa.nome_unidade} · ${item.programa.grupamento} · ${item.programa.turno}</p>
        <div class="position-hero">
          <div class="num">${App.ordinal(item.posicao)}</div>
          <p class="of">posição de ${item.total_fila} na fila</p>
        </div>
        <div style="display:flex;justify-content:center;margin-bottom:14px;">${badgeStatus(item.status)}</div>
        <div style="text-align:center;">
          ${podeTrocar
            ? `<span class="countdown">⏳ Você pode trocar sua escolha por mais ${dias} dia${dias === 1 ? "" : "s"}</span>`
            : `<span class="countdown expired">Prazo para troca encerrado em ${App.formatDatePt(item.pode_trocar_ate)}</span>`}
        </div>
      </div>
    `;
  }

  function cardSugestao(s) {
    return `
      <div class="pref-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <span>
          <b>${s.nome_unidade}</b><br>
          <span class="section-sub" style="margin:2px 0 0;">${s.grupamento} · ${s.turno}</span>
        </span>
        <span class="badge badge-${s.chance}">${CHANCE_LABEL[s.chance]}</span>
      </div>
    `;
  }

  function renderNormal(dados, atualizadoEm, avisoCache) {
    dadosAtuais = dados;
    const semClassificacao = !dados.classificacoes || dados.classificacoes.length === 0;

    root.innerHTML = `
      ${avisoCache ? App.bannerHtml("warning", "Não conseguimos atualizar agora. Mostrando a última posição salva neste aparelho.") : ""}

      ${semClassificacao
        ? App.emptyHtml("Sua inscrição ainda está sendo processada. Volte em algumas horas para ver sua posição na fila.")
        : `
        <div class="stack">
          ${dados.classificacoes.map(cardClassificacao).join("")}
        </div>

        <div style="margin-top:16px;">
          <button type="button" id="btn-trocar" class="btn btn-secondary btn-block">Trocar minha escolha</button>
        </div>

        <div id="area-troca" style="margin-top:12px;"></div>
        `}

      ${dados.sugestoes && dados.sugestoes.length > 0 ? `
        <hr class="divider">
        <p class="section-title">Outras unidades com chance real</p>
        <p class="section-sub">Estas são <b>sugestões</b> — elas nunca substituem a sua preferência declarada. Sua ordem de preferência continua sendo a que você escolheu.</p>
        <div class="stack-tight">${dados.sugestoes.map(cardSugestao).join("")}</div>
      ` : ""}

      <p class="meta-line" style="margin-top:20px;justify-content:center;">🔄 Lista atualizada diariamente · última atualização: ${atualizadoEm}</p>
    `;

    const btnTrocar = App.qs("#btn-trocar");
    if (btnTrocar) {
      const podeTrocarGlobal = dados.classificacoes.some((c) => App.diasRestantes(c.pode_trocar_ate) > 0);
      if (!podeTrocarGlobal) {
        btnTrocar.disabled = true;
        btnTrocar.textContent = "Prazo para troca encerrado";
      }
      btnTrocar.addEventListener("click", () => abrirModoTroca(dados.classificacoes));
    }
  }

  function abrirModoTroca(classificacoes) {
    modoTroca = true;
    ordemEmEdicao = classificacoes.map((c) => ({ ...c.programa }));
    renderModoTroca();
  }

  function renderModoTroca() {
    const area = App.qs("#area-troca");
    if (!area) return;
    area.innerHTML = `
      <div class="card">
        <p class="section-title">Reordenar suas opções</p>
        <p class="section-sub">Use as setas para mudar a ordem. A 1ª opção é a que a família mais quer.</p>
        <div class="stack-tight" id="lista-reordenar">
          ${ordemEmEdicao.map((p, i) => `
            <div class="pref-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;" data-i="${i}">
              <span class="pref-badge"><span class="n">${i + 1}</span> ${p.nome_unidade}</span>
              <span class="reorder-btns">
                <button type="button" data-mover="cima" ${i === 0 ? "disabled" : ""} aria-label="Mover para cima">↑</button>
                <button type="button" data-mover="baixo" ${i === ordemEmEdicao.length - 1 ? "disabled" : ""} aria-label="Mover para baixo">↓</button>
              </span>
            </div>
          `).join("")}
        </div>
        <div id="troca-banner" style="margin-top:12px;"></div>
        <div style="display:flex;gap:10px;margin-top:14px;">
          <button type="button" id="btn-cancelar-troca" class="btn btn-ghost" style="flex:1;">Cancelar</button>
          <button type="button" id="btn-confirmar-troca" class="btn btn-primary" style="flex:1;">Confirmar nova ordem</button>
        </div>
      </div>
    `;

    App.qs("#lista-reordenar").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-mover]");
      if (!btn) return;
      const row = btn.closest("[data-i]");
      const i = Number(row.dataset.i);
      const alvo = btn.dataset.mover === "cima" ? i - 1 : i + 1;
      if (alvo < 0 || alvo >= ordemEmEdicao.length) return;
      [ordemEmEdicao[i], ordemEmEdicao[alvo]] = [ordemEmEdicao[alvo], ordemEmEdicao[i]];
      renderModoTroca();
    });

    App.qs("#btn-cancelar-troca").addEventListener("click", () => {
      modoTroca = false;
      App.qs("#area-troca").innerHTML = "";
    });

    App.qs("#btn-confirmar-troca").addEventListener("click", async (e) => {
      const btn = e.target;
      btn.disabled = true;
      btn.textContent = "Confirmando...";
      try {
        const novaOrdem = ordemEmEdicao.map((p) => ({ unidade: p.unidade, grupamento: p.grupamento, turno: p.turno }));
        const resposta = await Api.trocarPreferencias(criancaId, novaOrdem);
        const dadosAtualizados = { classificacoes: resposta.classificacoes, sugestoes: dadosAtuais.sugestoes };
        const agora = App.formatDateHoraPt(new Date().toISOString());
        localStorage.setItem(cacheKey, JSON.stringify({ dados: dadosAtualizados, quando: agora }));
        modoTroca = false;
        renderNormal(dadosAtualizados, agora, false);
        root.insertAdjacentHTML("afterbegin", App.bannerHtml("success", "Sua nova ordem de preferência foi salva."));
      } catch (err) {
        App.qs("#troca-banner").innerHTML = App.bannerHtml("error", App.mensagemErroAmigavel(err));
        btn.disabled = false;
        btn.textContent = "Confirmar nova ordem";
      }
    });
  }

  async function carregar() {
    root.innerHTML = App.loadingHtml("Carregando sua posição na fila...");
    try {
      const dados = await Api.buscarClassificacao(criancaId);
      const agora = App.formatDateHoraPt(new Date().toISOString());
      localStorage.setItem(cacheKey, JSON.stringify({ dados, quando: agora }));
      renderNormal(dados, agora, false);
    } catch (err) {
      const cache = JSON.parse(localStorage.getItem(cacheKey) || "null");
      if (cache) {
        renderNormal(cache.dados, cache.quando, true);
      } else {
        root.innerHTML = App.erroHtml(App.mensagemErroAmigavel(err), true);
        App.qs('[data-acao="retentar"]').addEventListener("click", carregar);
      }
    }
  }

  carregar();
};

/* ============================================================
   TELA 4 — Status da matrícula
   ============================================================ */

App.initStatus = function () {
  const root = App.qs("#conteudo-status");
  const criancaId = App.getCriancaId();

  if (!criancaId) {
    root.innerHTML = App.erroHtml("Não encontramos sua inscrição. Comece pela tela de inscrição.");
    return;
  }

  function renderSelecionado(dados) {
    root.innerHTML = `
      <div class="card" style="text-align:center;background:var(--success-bg);border-color:var(--success);">
        <p style="font-size:32px;margin-bottom:6px;" aria-hidden="true">🎉</p>
        <p class="section-title" style="font-size:19px;color:var(--success);">Parabéns! Sua criança foi selecionada.</p>
        <p class="page-lede" style="margin:10px 0 0;color:var(--ink-900);">
          Dirija-se à <b>${dados.unidade}</b> até <b>${App.formatDatePt(dados.prazo_matricula)}</b> para matricular presencialmente.
        </p>
      </div>
      <div style="margin-top:14px;">
        ${App.bannerHtml("info", "Leve documento de identidade do responsável e da criança, e comprovante de residência. Confira a lista completa na própria unidade.")}
      </div>
    `;
  }

  function renderAguardando(resumo) {
    root.innerHTML = `
      <div class="card" style="text-align:center;">
        <p style="font-size:28px;margin-bottom:6px;" aria-hidden="true">⏳</p>
        <p class="section-title" style="font-size:18px;">Ainda aguardando</p>
        <p class="page-lede" style="margin:8px 0 0;">Sua criança ainda não foi chamada para matrícula. Assim que houver uma vaga dentro da chamada, avisaremos aqui.</p>
      </div>
      ${resumo ? `
      <div class="card" style="margin-top:12px;">
        <p class="small-caps">${resumo.programa.nome_unidade}</p>
        <div class="position-hero">
          <div class="num" style="font-size:34px;">${App.ordinal(resumo.posicao)}</div>
          <p class="of">posição de ${resumo.total_fila} na fila</p>
        </div>
      </div>` : ""}
      <div style="margin-top:16px;text-align:center;">
        <button type="button" id="btn-ver-fila" class="link-btn">Ver minha posição completa na fila →</button>
      </div>
    `;
    const btn = App.qs("#btn-ver-fila");
    if (btn) btn.addEventListener("click", () => App.goTo("classificacao.html"));
  }

  async function carregar() {
    root.innerHTML = App.loadingHtml("Verificando o status da matrícula...");
    try {
      const status = await Api.buscarStatusMatricula(criancaId);

      if (status.status === "selecionado" || status.status === "matriculado") {
        renderSelecionado(status);
        return;
      }

      // aguardando: tenta enriquecer com a melhor posição atual (não obrigatório pelo contrato)
      let resumo = null;
      try {
        const classificacao = await Api.buscarClassificacao(criancaId);
        if (classificacao.classificacoes && classificacao.classificacoes.length > 0) {
          resumo = classificacao.classificacoes.slice().sort((a, b) => a.posicao - b.posicao)[0];
        }
      } catch (_) { /* sem resumo, tudo bem — a tela ainda funciona */ }

      renderAguardando(resumo);
    } catch (err) {
      root.innerHTML = App.erroHtml(App.mensagemErroAmigavel(err), true);
      App.qs('[data-acao="retentar"]').addEventListener("click", carregar);
    }
  }

  carregar();
};
