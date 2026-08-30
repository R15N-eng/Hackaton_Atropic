/* ============================================================
   api.js — única fronteira com o backend.
   Troque USE_MOCK para false e preencha API_BASE quando o Back B
   publicar a URL. Nenhuma outra tela/arquivo deve mudar.
   ============================================================ */

const USE_MOCK = true;
const API_BASE = ""; // ex: "https://api.creche.rio/v1"

/* ------------------------------------------------------------
   Catálogo mock de unidades/programas — só usado quando USE_MOCK.
   Serve para o formulário de inscrição e para gerar respostas
   plausíveis e consistentes nas telas seguintes.
   ------------------------------------------------------------ */

const MOCK_UNIDADES = [
  { unidade: "010134", nome_unidade: "Creche Cantinho Feliz de Santa Teresa", bairro: "Santa Teresa" },
  { unidade: "010055", nome_unidade: "Creche do Tuiuti", bairro: "Benfica" },
  { unidade: "020441", nome_unidade: "Creche Municipal Abrigo Teresa de Jesus", bairro: "Tijuca" },
  { unidade: "030112", nome_unidade: "Creche Municipal Vila Kennedy", bairro: "Vila Kennedy" },
  { unidade: "040287", nome_unidade: "Creche Municipal Praça Seca", bairro: "Praça Seca" },
  { unidade: "050063", nome_unidade: "Creche Municipal Bangu", bairro: "Bangu" },
  { unidade: "060198", nome_unidade: "Creche Municipal Campo Grande", bairro: "Campo Grande" },
  { unidade: "070045", nome_unidade: "Creche Municipal Ilha do Governador", bairro: "Ilha do Governador" },
];

const GRUPAMENTOS = ["Berçário", "Maternal I", "Maternal II"];
const TURNOS = ["Integral", "Parcial"];

// perguntas de vulnerabilidade — texto placeholder, Back A envia o texto oficial depois
const MOCK_PERGUNTAS = [
  { perg_id: "p1", texto: "Família inscrita no CadÚnico (Cadastro Único)?" },
  { perg_id: "p2", texto: "A criança tem alguma deficiência?" },
  { perg_id: "p3", texto: "Família recebe Bolsa Família ou possui Cartão Carioca?" },
  { perg_id: "p4", texto: "Já houve alguma situação de violência doméstica envolvendo a criança ou a família?" },
  { perg_id: "p5", texto: "Algum membro da família faz uso abusivo de álcool ou drogas?" },
  { perg_id: "p6", texto: "A criança ou algum familiar tem doença crônica grave?" },
  { perg_id: "p7", texto: "Algum responsável está preso ou foi preso nos últimos 5 anos?" },
  { perg_id: "p8", texto: "A criança é refugiada ou imigrante recente?" },
  { perg_id: "p9", texto: "A família é monoparental (só um responsável presente)?" },
  { perg_id: "p10", texto: "A criança ficou em fila de espera no ano anterior sem ser atendida?" },
];

// peso mock de cada pergunta — só para o front ter um score plausível;
// a régua oficial é responsabilidade do Back A
const MOCK_PONTUACAO = { p1: 40, p2: 25, p3: 15, p4: 10, p5: 8, p6: 6, p7: 4, p8: 4, p9: 3, p10: 3 };

/* ------------------------------------------------------------
   Utilidades determinísticas (nada de Math.random em dado que
   precisa ser igual em recarregamentos)
   ------------------------------------------------------------ */

function hashString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function seededInt(seed, min, max) {
  const h = hashString(String(seed));
  return min + (h % (max - min + 1));
}

function addDays(dateIso, days) {
  const d = new Date(dateIso);
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

function gerarCriancaId() {
  return "crianca_" + Date.now().toString(36) + seededInt(Math.random(), 100, 999);
}

/* ------------------------------------------------------------
   "Banco" mock — persistido em localStorage para sobreviver a
   recarregamentos de página e navegação entre as 4 telas.
   ------------------------------------------------------------ */

const MockStore = {
  key(criancaId) { return "creche_mock_" + criancaId; },
  save(criancaId, data) {
    localStorage.setItem(this.key(criancaId), JSON.stringify(data));
  },
  load(criancaId) {
    const raw = localStorage.getItem(this.key(criancaId));
    return raw ? JSON.parse(raw) : null;
  },
};

function calcularScoreMock(respostas) {
  let score = 0;
  for (const [pergId, valor] of Object.entries(respostas || {})) {
    if (valor) score += MOCK_PONTUACAO[pergId] || 0;
  }
  return score;
}

// distância pseudo-realista entre o bairro digitado e o bairro da unidade
function distanciaMockKm(bairroFamilia, bairroUnidade) {
  const a = (bairroFamilia || "").trim().toLowerCase();
  const b = (bairroUnidade || "").trim().toLowerCase();
  if (a && b && (a === b || a.includes(b) || b.includes(a))) {
    return Number((seededInt(a + "|" + b, 3, 12) / 10).toFixed(1)); // 0.3–1.2km, mesmo bairro
  }
  return Number((seededInt(a + "|" + b, 15, 95) / 10).toFixed(1)); // 1.5–9.5km, bairros diferentes
}

function montarProgramaFromPref(pref) {
  const unidadeInfo = MOCK_UNIDADES.find((u) => u.unidade === pref.unidade) || MOCK_UNIDADES[0];
  return {
    unidade: unidadeInfo.unidade,
    nome_unidade: unidadeInfo.nome_unidade,
    grupamento: pref.grupamento,
    turno: pref.turno,
  };
}

function gerarClassificacaoMock(criancaId, registro) {
  const { preferencias, score, criado_em } = registro;

  const classificacoes = preferencias.map((pref) => {
    const programa = montarProgramaFromPref(pref);
    const chaveProg = `${programa.unidade}|${programa.grupamento}|${programa.turno}`;
    const capacidade = seededInt(chaveProg, 12, 40);
    const totalFila = capacidade + seededInt(chaveProg + "|fila", 15, 140);
    const notaCorte = seededInt(chaveProg + "|corte", 10, 70);

    // score mais alto -> posição melhor (menor número)
    const baseDisputa = seededInt(criancaId + "|" + chaveProg, 1, totalFila);
    const posicao = Math.max(1, Math.round(baseDisputa - score * 0.9));
    const posicaoFinal = Math.min(posicao, totalFila);

    let status;
    if (posicaoFinal <= capacidade) status = "dentro";
    else if (posicaoFinal <= Math.round(capacidade * 1.7)) status = "espera";
    else status = "fora";

    return {
      programa,
      posicao: posicaoFinal,
      total_fila: totalFila,
      status,
      pode_trocar_ate: addDays(criado_em, 7),
      _capacidade: capacidade,
      _nota_corte: notaCorte,
    };
  });

  // sugestões: unidades fora das preferências da família
  const unidadesEscolhidas = new Set(preferencias.map((p) => p.unidade));
  const candidatas = MOCK_UNIDADES.filter((u) => !unidadesEscolhidas.has(u.unidade)).slice(0, 3);

  const sugestoes = candidatas.map((u, i) => {
    const grupamento = preferencias[0] ? preferencias[0].grupamento : GRUPAMENTOS[0];
    const turno = preferencias[0] ? preferencias[0].turno : TURNOS[0];
    const chaveProg = `${u.unidade}|${grupamento}|${turno}`;
    const notaCorte = seededInt(chaveProg + "|corte", 10, 70);
    let chance;
    if (score >= notaCorte) chance = "alta";
    else if (score >= notaCorte - 20) chance = "media";
    else chance = "baixa";
    return { unidade: u.unidade, nome_unidade: u.nome_unidade, grupamento, turno, chance };
  });

  return { classificacoes, sugestoes };
}

function gerarStatusMatriculaMock(registro) {
  const { classificacoes, criado_em } = registro;
  const melhor = classificacoes.slice().sort((a, b) => a.posicao - b.posicao)[0];
  if (melhor && melhor.status === "dentro") {
    return {
      status: "selecionado",
      unidade: melhor.programa.nome_unidade,
      prazo_matricula: addDays(criado_em, 12),
    };
  }
  return { status: "aguardando", unidade: null, prazo_matricula: null };
}

/* ------------------------------------------------------------
   Implementação mock dos 4 endpoints (mesmo formato de resposta
   do contrato real, com atraso de rede simulado)
   ------------------------------------------------------------ */

function delay(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

const MockApi = {
  async inscricao(payload) {
    await delay(500);

    const criancaId = gerarCriancaId();
    const criadoEm = new Date().toISOString();
    const score = calcularScoreMock(payload.respostas);

    // sugere, entre as preferências, a unidade mais perto do bairro/CEP informado
    let sugerida = null;
    let menorDist = Infinity;
    for (const pref of payload.preferencias) {
      const info = MOCK_UNIDADES.find((u) => u.unidade === pref.unidade);
      if (!info) continue;
      const d = distanciaMockKm(payload.bairro_cep, info.bairro);
      if (d < menorDist) { menorDist = d; sugerida = info; }
    }
    if (!sugerida) sugerida = MOCK_UNIDADES[0];

    const registro = {
      crianca_id: criancaId,
      bairro_cep: payload.bairro_cep,
      preferencias: payload.preferencias,
      respostas: payload.respostas,
      score,
      criado_em: criadoEm,
      unidade_comprovacao_sugerida: {
        unidade: sugerida.unidade,
        nome_unidade: sugerida.nome_unidade,
        distancia_km: menorDist === Infinity ? null : menorDist,
      },
    };

    const { classificacoes, sugestoes } = gerarClassificacaoMock(criancaId, registro);
    registro.classificacoes = classificacoes;
    registro.sugestoes = sugestoes;
    registro.status_matricula = gerarStatusMatriculaMock(registro);

    MockStore.save(criancaId, registro);

    return {
      crianca_id: criancaId,
      score,
      unidade_comprovacao_sugerida: registro.unidade_comprovacao_sugerida,
    };
  },

  async classificacao(criancaId) {
    await delay(450);
    const registro = MockStore.load(criancaId);
    if (!registro) {
      const err = new Error("Inscrição não encontrada.");
      err.status = 404;
      throw err;
    }
    return {
      classificacoes: registro.classificacoes,
      sugestoes: registro.sugestoes,
    };
  },

  async trocar(criancaId, novaOrdemPreferencias) {
    await delay(450);
    const registro = MockStore.load(criancaId);
    if (!registro) {
      const err = new Error("Inscrição não encontrada.");
      err.status = 404;
      throw err;
    }
    const janelaAberta = registro.classificacoes.some((c) => new Date(c.pode_trocar_ate) >= new Date());
    if (!janelaAberta) {
      const err = new Error("O prazo de 7 dias para trocar sua ordem de preferência já encerrou.");
      err.status = 422;
      throw err;
    }
    registro.preferencias = novaOrdemPreferencias;
    const { classificacoes, sugestoes } = gerarClassificacaoMock(criancaId, registro);
    registro.classificacoes = classificacoes;
    registro.sugestoes = sugestoes;
    MockStore.save(criancaId, registro);
    return { ok: true, classificacoes };
  },

  async statusMatricula(criancaId) {
    await delay(400);
    const registro = MockStore.load(criancaId);
    if (!registro) {
      const err = new Error("Inscrição não encontrada.");
      err.status = 404;
      throw err;
    }
    return registro.status_matricula;
  },
};

/* ------------------------------------------------------------
   Implementação real — usada quando USE_MOCK = false.
   Mesmos nomes de campo do contrato, sem tradução nenhuma.
   ------------------------------------------------------------ */

async function httpJson(path, options) {
  let res;
  try {
    res = await fetch(API_BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    const err = new Error("Não foi possível conectar ao servidor.");
    err.status = 0;
    throw err;
  }
  if (!res.ok) {
    let msg = "Erro inesperado (" + res.status + ").";
    try {
      const body = await res.json();
      if (body && body.message) msg = body.message;
    } catch (_) { /* corpo sem json, mantém msg padrão */ }
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const RealApi = {
  inscricao(payload) {
    return httpJson("/inscricao", { method: "POST", body: JSON.stringify(payload) });
  },
  classificacao(criancaId) {
    return httpJson(`/classificacao/${encodeURIComponent(criancaId)}`);
  },
  trocar(criancaId, novaOrdemPreferencias) {
    return httpJson(`/classificacao/${encodeURIComponent(criancaId)}/trocar`, {
      method: "POST",
      body: JSON.stringify({ nova_ordem_preferencias: novaOrdemPreferencias }),
    });
  },
  statusMatricula(criancaId) {
    return httpJson(`/status-matricula/${encodeURIComponent(criancaId)}`);
  },
};

/* ------------------------------------------------------------
   Fachada pública — é isso que as telas chamam. Nunca mudam a
   assinatura, só o valor de USE_MOCK muda qual lado é usado.
   ------------------------------------------------------------ */

const Api = {
  enviarInscricao: (payload) => (USE_MOCK ? MockApi.inscricao(payload) : RealApi.inscricao(payload)),
  buscarClassificacao: (criancaId) => (USE_MOCK ? MockApi.classificacao(criancaId) : RealApi.classificacao(criancaId)),
  trocarPreferencias: (criancaId, novaOrdem) => (USE_MOCK ? MockApi.trocar(criancaId, novaOrdem) : RealApi.trocar(criancaId, novaOrdem)),
  buscarStatusMatricula: (criancaId) => (USE_MOCK ? MockApi.statusMatricula(criancaId) : RealApi.statusMatricula(criancaId)),
};
