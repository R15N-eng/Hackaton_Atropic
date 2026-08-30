/* ============================================================
   app.js — utilidades compartilhadas + lógica de cada tela.
   Depende de api.js (Api, MOCK_UNIDADES, GRUPAMENTOS, TURNOS,
   MOCK_PERGUNTAS) já carregado antes deste arquivo.
   ============================================================ */

const App = {};

/* ---------------------------- utilidades gerais ---------------------------- */

App.qs = (sel, root) => (root || document).querySelector(sel);
App.qsa = (sel, root) => Array.from((root || document).querySelectorAll(sel));

// o id da criança nunca vai para a URL/link — fica só no localStorage deste
// aparelho, para não vazar em histórico do navegador, print de tela ou link
// compartilhado (ex: WhatsApp). Quem precisa acompanhar de outro aparelho usa
// o login por telefone (App.initLogin), não um link com o id embutido.
App.getCriancaId = () => localStorage.getItem("creche_crianca_id") || null;

App.setCriancaId = (id) => localStorage.setItem("creche_crianca_id", id);

App.goTo = (page) => {
  window.location.href = page;
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
      let label = labelKey ? item[labelKey] : item;
      if (valueKey && item.capacidade) label += ` (${item.capacidade} vagas)`;
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
      App.goTo("verificacao.html");
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
        <p class="section-sub">Leve os documentos que comprovem cada um — eles entram no cálculo da sua posição na fila.</p>
        <div class="stack-tight">
          ${criterios.map((c) => `
            <div class="pref-row" style="display:flex;align-items:center;gap:10px;">
              <span style="font-size:13.5px;">${c.texto}</span>
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
      App.goTo("classificacao.html");
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
  let unidadesCatalogo = null;
  let novaSelecao = { unidade: "", grupamento: "", turno: "" };
  let previewResultado = null;

  function badgeStatus(status) {
    return `<span class="badge badge-${status}">${STATUS_LABEL[status] || status}</span>`;
  }

  function cardClassificacao(item, idx) {
    const dias = App.diasRestantes(item.pode_trocar_ate);
    const podeTrocar = dias > 0;
    const vagas = item.capacidade != null ? item.capacidade : item.total_fila;
    return `
      <div class="card">
        <p class="small-caps">${item.programa.nome_unidade} · ${item.programa.grupamento} · ${item.programa.turno}</p>
        <div class="position-hero">
          <div class="num">${App.ordinal(item.posicao)}</div>
          <p class="of">Você está no lugar ${item.posicao} de ${vagas}</p>
        </div>
        ${item.total_fila != null ? `<p class="section-sub" style="text-align:center;margin-top:-6px;">${item.total_fila} famílias concorrendo a ${vagas} vagas</p>` : ""}
        <div style="display:flex;justify-content:center;margin:10px 0 14px;">${badgeStatus(item.status)}</div>
        <div style="text-align:center;">
          ${podeTrocar
            ? `<span class="countdown">⏳ Você pode trocar sua escolha por mais ${dias} dia${dias === 1 ? "" : "s"}</span>`
            : `<span class="countdown expired">Prazo para troca encerrado em ${App.formatDatePt(item.pode_trocar_ate)}</span>`}
        </div>
      </div>
    `;
  }

  function previewHtml(resultado) {
    return `
      ${App.bannerHtml("info", `Nessa unidade, hoje você entraria na posição <b>${resultado.posicao}</b> de <b>${resultado.capacidade}</b> vagas.`)}
      <button type="button" class="btn btn-primary btn-sm btn-block" style="margin-top:8px;" data-acao="adicionar-lista">Adicionar essa unidade à lista</button>
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
          <button type="button" id="btn-trocar" class="btn btn-secondary btn-block">Gerenciar minhas opções</button>
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

  async function abrirModoTroca(classificacoes) {
    modoTroca = true;
    ordemEmEdicao = classificacoes.map((c) => ({ ...c.programa }));
    novaSelecao = { unidade: "", grupamento: "", turno: "" };
    previewResultado = null;

    const area = App.qs("#area-troca");
    if (area) area.innerHTML = App.loadingHtml("Carregando lista de unidades...");
    try {
      if (!unidadesCatalogo) unidadesCatalogo = await Api.listarUnidades();
    } catch (_) {
      unidadesCatalogo = [];
    }
    renderModoTroca();
  }

  function renderModoTroca() {
    const area = App.qs("#area-troca");
    if (!area) return;

    const disponiveis = (unidadesCatalogo || []).filter(
      (u) => !ordemEmEdicao.some((p) => String(p.unidade) === String(u.unidade))
    );
    const podeAdicionarMais = ordemEmEdicao.length < 5;

    area.innerHTML = `
      <div class="card">
        <p class="section-title">Reordenar ou remover suas opções</p>
        <p class="section-sub">Use as setas para mudar a ordem, ou remova uma opção. A 1ª opção é a que a família mais quer.</p>
        <div class="stack-tight" id="lista-reordenar">
          ${ordemEmEdicao.map((p, i) => `
            <div class="pref-row" style="display:flex;align-items:center;justify-content:space-between;gap:10px;" data-i="${i}">
              <span class="pref-badge"><span class="n">${i + 1}</span> ${p.nome_unidade}</span>
              <span class="reorder-btns">
                <button type="button" data-mover="cima" ${i === 0 ? "disabled" : ""} aria-label="Mover para cima">↑</button>
                <button type="button" data-mover="baixo" ${i === ordemEmEdicao.length - 1 ? "disabled" : ""} aria-label="Mover para baixo">↓</button>
                ${ordemEmEdicao.length > 1 ? `<button type="button" data-remover="${i}" aria-label="Remover opção">✕</button>` : ""}
              </span>
            </div>
          `).join("")}
        </div>

        <hr class="divider">
        <p class="section-title">Adicionar uma nova unidade</p>
        ${!podeAdicionarMais
          ? `<p class="section-sub">Você já tem 5 opções na lista (o máximo permitido). Remova uma para adicionar outra.</p>`
          : disponiveis.length === 0
          ? `<p class="section-sub">Não há mais unidades disponíveis para adicionar.</p>`
          : `
          <div class="pref-grid">
            <div class="field full" style="margin-bottom:0;">
              <label>Unidade / creche</label>
              <select class="input" id="nova-unidade">
                <option value="" disabled ${!novaSelecao.unidade ? "selected" : ""}>Escolha a unidade</option>
                ${disponiveis.map((u) => `<option value="${u.unidade}" ${String(u.unidade) === String(novaSelecao.unidade) ? "selected" : ""}>${u.nome_unidade}${u.capacidade ? ` (${u.capacidade} vagas)` : ""}</option>`).join("")}
              </select>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Turma</label>
              <select class="input" id="nova-grupamento">
                <option value="" disabled ${!novaSelecao.grupamento ? "selected" : ""}>Turma</option>
                ${GRUPAMENTOS.map((g) => `<option value="${g}" ${g === novaSelecao.grupamento ? "selected" : ""}>${g}</option>`).join("")}
              </select>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Turno</label>
              <select class="input" id="nova-turno">
                <option value="" disabled ${!novaSelecao.turno ? "selected" : ""}>Turno</option>
                ${TURNOS.map((t) => `<option value="${t}" ${t === novaSelecao.turno ? "selected" : ""}>${t}</option>`).join("")}
              </select>
            </div>
          </div>
          <div style="margin-top:10px;">
            <button type="button" id="btn-ver-vaga" class="btn btn-secondary btn-sm btn-block">Ver em qual vaga eu ficaria</button>
          </div>
          <div id="preview-resultado" style="margin-top:10px;">${previewResultado ? previewHtml(previewResultado) : ""}</div>
          `
        }

        <div id="troca-banner" style="margin-top:12px;"></div>
        <div style="display:flex;gap:10px;margin-top:14px;">
          <button type="button" id="btn-cancelar-troca" class="btn btn-ghost" style="flex:1;">Cancelar</button>
          <button type="button" id="btn-confirmar-troca" class="btn btn-primary" style="flex:1;">Confirmar alterações</button>
        </div>
      </div>
    `;

    App.qs("#lista-reordenar").addEventListener("click", (e) => {
      const moverBtn = e.target.closest("[data-mover]");
      if (moverBtn) {
        const row = moverBtn.closest("[data-i]");
        const i = Number(row.dataset.i);
        const alvo = moverBtn.dataset.mover === "cima" ? i - 1 : i + 1;
        if (alvo < 0 || alvo >= ordemEmEdicao.length) return;
        [ordemEmEdicao[i], ordemEmEdicao[alvo]] = [ordemEmEdicao[alvo], ordemEmEdicao[i]];
        renderModoTroca();
        return;
      }
      const removerBtn = e.target.closest("[data-remover]");
      if (removerBtn) {
        ordemEmEdicao.splice(Number(removerBtn.dataset.remover), 1);
        renderModoTroca();
      }
    });

    const selUnidade = App.qs("#nova-unidade");
    if (selUnidade) {
      const selGrupamento = App.qs("#nova-grupamento");
      const selTurno = App.qs("#nova-turno");
      const sincronizarSelecao = () => {
        novaSelecao = { unidade: selUnidade.value, grupamento: selGrupamento.value, turno: selTurno.value };
        previewResultado = null;
        App.qs("#preview-resultado").innerHTML = "";
      };
      selUnidade.addEventListener("change", sincronizarSelecao);
      selGrupamento.addEventListener("change", sincronizarSelecao);
      selTurno.addEventListener("change", sincronizarSelecao);
    }

    const btnVerVaga = App.qs("#btn-ver-vaga");
    if (btnVerVaga) {
      btnVerVaga.addEventListener("click", async () => {
        if (!novaSelecao.unidade || !novaSelecao.grupamento || !novaSelecao.turno) {
          App.qs("#preview-resultado").innerHTML = App.bannerHtml("error", "Escolha a unidade, a turma e o turno antes de ver a vaga.");
          return;
        }
        btnVerVaga.disabled = true;
        btnVerVaga.textContent = "Calculando...";
        try {
          previewResultado = await Api.preverPosicao(criancaId, novaSelecao.unidade, novaSelecao.grupamento, novaSelecao.turno);
          App.qs("#preview-resultado").innerHTML = previewHtml(previewResultado);
        } catch (err) {
          App.qs("#preview-resultado").innerHTML = App.bannerHtml("error", App.mensagemErroAmigavel(err));
        } finally {
          btnVerVaga.disabled = false;
          btnVerVaga.textContent = "Ver em qual vaga eu ficaria";
        }
      });
    }

    const containerPreview = App.qs("#preview-resultado");
    if (containerPreview) {
      containerPreview.addEventListener("click", (e) => {
        if (!e.target.closest('[data-acao="adicionar-lista"]')) return;
        const infoUnidade = (unidadesCatalogo || []).find((u) => String(u.unidade) === String(novaSelecao.unidade));
        ordemEmEdicao.push({
          unidade: novaSelecao.unidade,
          nome_unidade: infoUnidade ? infoUnidade.nome_unidade : novaSelecao.unidade,
          grupamento: novaSelecao.grupamento,
          turno: novaSelecao.turno,
        });
        novaSelecao = { unidade: "", grupamento: "", turno: "" };
        previewResultado = null;
        renderModoTroca();
      });
    }

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

        // mantém o cache local de preferências em sincronia (usado para
        // mostrar turma/turno corretos após reordenar/adicionar/remover)
        const inscricaoCacheKey = "creche_inscricao_" + criancaId;
        const inscricaoCache = JSON.parse(localStorage.getItem(inscricaoCacheKey) || "null") || {};
        inscricaoCache.preferencias = ordemEmEdicao;
        localStorage.setItem(inscricaoCacheKey, JSON.stringify(inscricaoCache));

        modoTroca = false;
        renderNormal(dadosAtualizados, agora, false);
        root.insertAdjacentHTML("afterbegin", App.bannerHtml("success", "Suas opções foram atualizadas."));
      } catch (err) {
        App.qs("#troca-banner").innerHTML = App.bannerHtml("error", App.mensagemErroAmigavel(err));
        btn.disabled = false;
        btn.textContent = "Confirmar alterações";
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

/* ============================================================
   TELA — Entrar (login por telefone + código via WhatsApp)
   Para a família voltar depois, de outro aparelho, sem depender do
   crianca_id salvo no localStorage deste aparelho de quando fez a inscrição.
   ============================================================ */

App.initLogin = function () {
  const root = App.qs("#conteudo-login");
  let telefoneDigitado = "";

  function renderPedirTelefone(mensagemErro) {
    root.innerHTML = `
      ${mensagemErro ? App.bannerHtml("error", mensagemErro) : ""}
      <div class="card">
        <div class="field" style="margin-bottom:0;">
          <label for="login-telefone">Telefone (WhatsApp) cadastrado na inscrição</label>
          <input class="input" id="login-telefone" type="tel" placeholder="+5521999999999" autocomplete="off" value="${telefoneDigitado}">
        </div>
      </div>
      <div class="sticky-cta">
        <button type="button" id="btn-enviar-codigo" class="btn btn-primary btn-block">Enviar código por WhatsApp</button>
      </div>
    `;
    App.qs("#btn-enviar-codigo").addEventListener("click", async (e) => {
      const btn = e.target;
      const telefone = App.qs("#login-telefone").value.trim();
      if (!telefone) {
        renderPedirTelefone("Informe o telefone cadastrado na inscrição.");
        return;
      }
      telefoneDigitado = telefone;
      btn.disabled = true;
      btn.textContent = "Enviando...";
      try {
        await Api.solicitarCodigo(telefone);
        renderPedirCodigo(telefone);
      } catch (err) {
        renderPedirTelefone(App.mensagemErroAmigavel(err));
      }
    });
  }

  function renderPedirCodigo(telefone, mensagemErro) {
    root.innerHTML = `
      ${mensagemErro ? App.bannerHtml("error", mensagemErro) : App.bannerHtml("info", `Enviamos um código de 6 dígitos por WhatsApp para ${telefone}.`)}
      <div class="card">
        <div class="field" style="margin-bottom:0;">
          <label for="login-codigo">Código recebido</label>
          <input class="input" id="login-codigo" type="text" inputmode="numeric" placeholder="000000" maxlength="6" autocomplete="off">
        </div>
      </div>
      <div style="margin-top:12px;text-align:center;">
        <button type="button" id="btn-trocar-telefone" class="link-btn">Usar outro número</button>
      </div>
      <div class="sticky-cta">
        <button type="button" id="btn-confirmar-codigo" class="btn btn-primary btn-block">Entrar</button>
      </div>
    `;
    App.qs("#btn-trocar-telefone").addEventListener("click", () => renderPedirTelefone());
    App.qs("#btn-confirmar-codigo").addEventListener("click", async (e) => {
      const btn = e.target;
      const codigo = App.qs("#login-codigo").value.trim();
      if (!codigo) {
        renderPedirCodigo(telefone, "Digite o código recebido.");
        return;
      }
      btn.disabled = true;
      btn.textContent = "Entrando...";
      try {
        await Api.verificarCodigo(telefone, codigo);
        await carregarInscricoes();
      } catch (err) {
        renderPedirCodigo(telefone, App.mensagemErroAmigavel(err));
      }
    });
  }

  async function carregarInscricoes() {
    root.innerHTML = App.loadingHtml("Buscando suas inscrições...");
    try {
      const inscricoes = await Api.minhasInscricoes();
      if (inscricoes.length === 0) {
        root.innerHTML = App.emptyHtml("Não encontramos nenhuma inscrição para esse número.") +
          `<div style="margin-top:16px;text-align:center;"><a class="link-btn" href="inscricao.html">Fazer uma nova inscrição →</a></div>`;
        return;
      }
      if (inscricoes.length === 1) {
        App.setCriancaId(inscricoes[0].id);
        App.goTo("classificacao.html");
        return;
      }
      root.innerHTML = `
        <p class="section-title">Qual inscrição você quer acompanhar?</p>
        <div class="stack-tight" id="lista-inscricoes">
          ${inscricoes.map((i) => `
            <button type="button" class="pref-row" style="width:100%;text-align:left;cursor:pointer;" data-id="${i.id}">
              <b>${i.nome}</b><br>
              <span class="section-sub" style="margin:2px 0 0;">Status: ${i.status}</span>
            </button>
          `).join("")}
        </div>
      `;
      App.qs("#lista-inscricoes").addEventListener("click", (e) => {
        const btn = e.target.closest("[data-id]");
        if (!btn) return;
        App.setCriancaId(btn.dataset.id);
        App.goTo("classificacao.html");
      });
    } catch (err) {
      root.innerHTML = App.erroHtml(App.mensagemErroAmigavel(err), true);
      App.qs('[data-acao="retentar"]').addEventListener("click", carregarInscricoes);
    }
  }

  renderPedirTelefone();
};
