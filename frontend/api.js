/* ============================================================
   api.js — única fronteira com o backend.
   Troque USE_MOCK para false e preencha API_BASE quando o Back B
   publicar a URL. Nenhuma outra tela/arquivo deve mudar.
   ============================================================ */

const USE_MOCK = false;
const API_BASE = "http://localhost:8000"; // ex: "https://api.creche.rio/v1"

/* ------------------------------------------------------------
   Catálogo mock de unidades/programas — só usado quando USE_MOCK.
   Serve para o formulário de inscrição e para gerar respostas
   plausíveis e consistentes nas telas seguintes.
   ------------------------------------------------------------ */

// 30 unidades reais que de fato estão na fila 2025, concentradas nos bairros
// com pior taxa de atendimento (Caju, Tijuca, Cordovil, Maré, Jacarepaguá,
// Taquara, Praça Seca, Curicica, Anil, Cidade de Deus). lat/lon reais, ainda
// não usados no cálculo de distância (a distância continua por texto de
// bairro — ver distanciaMockKm — porque o formulário só coleta bairro/CEP,
// não geolocalização da família).
const UNIDADES_2025 = [
  { unidade: "0101601", nome_unidade: "Creche Municipal Ladeira dos Funcionários", bairro: "Caju", lat: -22.879151, lon: -43.224306, CRE: 1 },
  { unidade: "0101602", nome_unidade: "Creche Municipal Virgínia Lemos", bairro: "Caju", lat: -22.886423, lon: -43.233212, CRE: 1 },
  { unidade: "0101603", nome_unidade: "Creche Municipal Senninha", bairro: "Caju", lat: -22.882989, lon: -43.228696, CRE: 1 },
  { unidade: "0208601", nome_unidade: "Creche Municipal Casa Branca - Professor Paulo Freire", bairro: "Tijuca", lat: -22.936602, lon: -43.248803, CRE: 2 },
  { unidade: "0208603", nome_unidade: "Creche Municipal Raízes do Salgueiro", bairro: "Tijuca", lat: -22.928219, lon: -43.225674, CRE: 2 },
  { unidade: "0208604", nome_unidade: "Creche Municipal Tia Bela", bairro: "Tijuca", lat: -22.93817, lon: -43.243002, CRE: 2 },
  { unidade: "0431601", nome_unidade: "Creche Municipal Luís Carlos de Oliveira Câmara", bairro: "Cordovil", lat: -22.81681, lon: -43.290269, CRE: 4 },
  { unidade: "0431603", nome_unidade: "Creche Municipal Chico Mendes", bairro: "Cordovil", lat: -22.818898, lon: -43.292015, CRE: 4 },
  { unidade: "0004005", nome_unidade: "CP Casa de Joel", bairro: "Cordovil", lat: -22.8298666, lon: -43.30749742, CRE: 4 },
  { unidade: "0004049", nome_unidade: "CP Instituto Josefa Laurentino", bairro: "Maré", lat: -22.84825182, lon: -43.24773693, CRE: 4 },
  { unidade: "0430809", nome_unidade: "Espaço de Desenvolvimento Infantil Medalhista Olímpico Luiz Felipe Marques Fonteles", bairro: "Maré", lat: -22.87059, lon: -43.234365, CRE: 4 },
  { unidade: "0430810", nome_unidade: "Espaço de Desenvolvimento Infantil Medalhista Olímpico Evandro Motta Marcondes Guerra", bairro: "Maré", lat: -22.870255, lon: -43.234242, CRE: 4 },
  { unidade: "0716601", nome_unidade: "Creche Municipal Otávio Henrique de Oliveira", bairro: "Jacarepaguá", lat: -22.974934, lon: -43.331015, CRE: 7 },
  { unidade: "0716602", nome_unidade: "Creche Municipal Tia Tereza", bairro: "Taquara", lat: -22.910162, lon: -43.371421, CRE: 7 },
  { unidade: "0716603", nome_unidade: "Creche Municipal Criança do Futuro", bairro: "Jacarepaguá", lat: -22.944254, lon: -43.384456, CRE: 7 },
  { unidade: "0716604", nome_unidade: "Creche Municipal Germinio de Souza Estrela", bairro: "Jacarepaguá", lat: -22.960454, lon: -43.352685, CRE: 7 },
  { unidade: "0716607", nome_unidade: "Creche Municipal Emília Joana da Fonseca Marques", bairro: "Praça Seca", lat: -22.907555, lon: -43.353033, CRE: 7 },
  { unidade: "0716608", nome_unidade: "Creche Municipal Irmã Dulce", bairro: "Praça Seca", lat: -22.900935, lon: -43.362466, CRE: 7 },
  { unidade: "0716610", nome_unidade: "Creche Municipal Tia Malu", bairro: "Taquara", lat: -22.918418, lon: -43.410069, CRE: 7 },
  { unidade: "0716614", nome_unidade: "Creche Municipal Augusto de Carvalho Torres Filho", bairro: "Curicica", lat: -22.955267, lon: -43.390377, CRE: 7 },
  { unidade: "0734601", nome_unidade: "Creche Municipal Luzes do Amanhã", bairro: "Cidade de Deus", lat: -22.952939, lon: -43.364891, CRE: 7 },
  { unidade: "0734602", nome_unidade: "Creche Municipal Margarida Gabinal", bairro: "Cidade de Deus", lat: -22.950792, lon: -43.355759, CRE: 7 },
  { unidade: "0734603", nome_unidade: "Creche Municipal Sempre Vida Josué", bairro: "Cidade de Deus", lat: -22.942892, lon: -43.363848, CRE: 7 },
  { unidade: "0007039", nome_unidade: "CP Creche Jardim Clarice", bairro: "Anil", lat: -22.96408, lon: -43.33653, CRE: 7 },
  { unidade: "0716802", nome_unidade: "Espaço de Desenvolvimento Infantil Arthur Bispo do Rosário", bairro: "Curicica", lat: -22.93725, lon: -43.390376, CRE: 7 },
  { unidade: "0716803", nome_unidade: "Espaço de Desenvolvimento Infantil Compositor Roberto Ribeiro", bairro: "Anil", lat: -22.957616, lon: -43.331432, CRE: 7 },
  { unidade: "0716804", nome_unidade: "Espaço de Desenvolvimento Infantil Rodrigo Lopes da Silva - Tikinho", bairro: "Curicica", lat: -22.945659, lon: -43.378626, CRE: 7 },
  { unidade: "0716806", nome_unidade: "Espaço de Desenvolvimento Infantil Professora Edília Coelho Garcia", bairro: "Taquara", lat: -22.912042, lon: -43.419526, CRE: 7 },
  { unidade: "0716809", nome_unidade: "Espaço de Desenvolvimento Infantil Professor Roberto Luiz Pereira", bairro: "Praça Seca", lat: -22.904538, lon: -43.34563, CRE: 7 },
  { unidade: "0716819", nome_unidade: "Espaço de Desenvolvimento Infantil Professora Norma Andrade Nogueira", bairro: "Anil", lat: -22.96226, lon: -43.343769, CRE: 7 },
];

// mantém o nome antigo funcionando (usado no formulário de inscrição)
const MOCK_UNIDADES = UNIDADES_2025;

const GRUPAMENTOS = ["Berçário", "Maternal I", "Maternal II"];
const TURNOS = ["Integral", "Parcial"];

/* ------------------------------------------------------------
   Régua oficial de classificação 2025 (13 perguntas, teto de 100
   pontos) — Query C do dataset da SME. Texto, pontuação e critério
   de desempate são reais, não placeholder. `criterio: true` marca
   pergunta que só serve para desempate (vale 0 ponto na soma).
   ------------------------------------------------------------ */

const PERGUNTAS_2025 = [
  { perg_id: 28, texto: "Criança cuja família seja inscrita no CadÚnico (Cadastro Único para Programas Sociais)?", pontos: 51, criterio: false },
  { perg_id: 31, texto: "A criança é público-alvo da educação especial?", pontos: 25, criterio: false },
  { perg_id: 17, texto: "A criança e/ou familiar do seu convívio diário é vitima de violência doméstica?", pontos: 4, criterio: false },
  { perg_id: 20, texto: "A criança pertence a família monoparental?", pontos: 4, criterio: false },
  { perg_id: 25, texto: "Candidato tem pais ou responsáveis deficientes?", pontos: 3, criterio: false },
  { perg_id: 18, texto: "A criança e/ou alguém do núcleo familiar apresentam doenças crônicas graves?", pontos: 3, criterio: false },
  { perg_id: 6, texto: "Faz parte do programa bolsa família ou possui Cartão Carioca?", pontos: 2, criterio: false },
  { perg_id: 16, texto: "Existe algum membro do núcleo familiar que faz uso abusivo de drogas e/ou alcoól?", pontos: 2, criterio: false },
  { perg_id: 12, texto: "Existe algum membro do núcleo familiar que é presidiário ou ex-presidiário nos últimos 5 anos?", pontos: 2, criterio: false },
  { perg_id: 23, texto: "O candidato é refugiado?", pontos: 2, criterio: false },
  { perg_id: 27, texto: "Criança aguardou em fila de espera no ano anterior sem ter sido atendida?", pontos: 2, criterio: false },
  { perg_id: 29, texto: "O Candidato possui irmão matriculado na rede pública ou parceria?", pontos: 0, criterio: true },
  { perg_id: 30, texto: "O Candidato possui pais ou responsáveis com idade menor que 18 anos?", pontos: 0, criterio: true },
];

// mantém o nome antigo funcionando (usado no formulário de inscrição)
const MOCK_PERGUNTAS = PERGUNTAS_2025;

const PONTOS_POR_PERGUNTA = Object.fromEntries(PERGUNTAS_2025.map((p) => [p.perg_id, p.pontos]));
const SCORE_MAXIMO_2025 = PERGUNTAS_2025.reduce((soma, p) => soma + p.pontos, 0); // 100

// devolve, entre as respostas "Sim" da família, os critérios declarados —
// usado na tela de verificação para mostrar o que será conferido na
// comprovação e o que vale cada um
function criteriosDeclarados(respostas) {
  return PERGUNTAS_2025
    .filter((p) => (respostas || {})[p.perg_id] === true)
    .sort((a, b) => b.pontos - a.pontos);
}

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
    if (valor) score += PONTOS_POR_PERGUNTA[pergId] || 0;
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

// Amostra real de 2025: capacidade = confirmações reais, demanda = total de
// opções recebidas naquele programa, nota_corte_atual = menor score entre os
// confirmados (0 = a pontuação não foi o critério decisivo nesse programa —
// coube por ordem/critério de desempate, não por pontos).
// Ex.: 0716601 Maternal II Integral — corte 2, 483 famílias para 6 vagas.
//      0716603 Maternal I Integral — corte 53, só 2 vagas.
// Uma família com score 51 (típico de quem só tem CadÚnico) fica FORA da
// primeira e DENTRO da segunda — por isso a posição é sempre por programa,
// nunca por escola inteira.
const PROGRAMAS_REAIS_2025 = {
  "0007039|Maternal I|Integral": { capacidade: 61, demanda: 121, nota_corte_atual: 0 },
  "0007039|Maternal II|Integral": { capacidade: 15, demanda: 102, nota_corte_atual: 0 },
  "0101601|Maternal I|Parcial": { capacidade: 35, demanda: 84, nota_corte_atual: 0 },
  "0101601|Maternal II|Parcial": { capacidade: 16, demanda: 39, nota_corte_atual: 0 },
  "0101602|Maternal I|Integral": { capacidade: 31, demanda: 44, nota_corte_atual: 0 },
  "0101602|Maternal II|Integral": { capacidade: 9, demanda: 14, nota_corte_atual: 0 },
  "0431601|Maternal II|Integral": { capacidade: 16, demanda: 25, nota_corte_atual: 0 },
  "0431603|Berçário|Integral": { capacidade: 26, demanda: 65, nota_corte_atual: 0 },
  "0431603|Maternal I|Integral": { capacidade: 21, demanda: 28, nota_corte_atual: 0 },
  "0431603|Maternal II|Integral": { capacidade: 2, demanda: 15, nota_corte_atual: 3 },
  "0716601|Maternal I|Integral": { capacidade: 88, demanda: 430, nota_corte_atual: 0 },
  "0716601|Maternal II|Integral": { capacidade: 6, demanda: 483, nota_corte_atual: 2 },
  "0716602|Maternal I|Parcial": { capacidade: 35, demanda: 86, nota_corte_atual: 0 },
  "0716602|Maternal II|Parcial": { capacidade: 21, demanda: 38, nota_corte_atual: 0 },
  "0716603|Berçário|Integral": { capacidade: 25, demanda: 290, nota_corte_atual: 0 },
  "0716603|Maternal I|Integral": { capacidade: 2, demanda: 259, nota_corte_atual: 53 },
  "0716603|Maternal II|Integral": { capacidade: 11, demanda: 202, nota_corte_atual: 2 },
  "0716607|Berçário|Integral": { capacidade: 34, demanda: 159, nota_corte_atual: 0 },
  "0716607|Maternal I|Integral": { capacidade: 30, demanda: 106, nota_corte_atual: 0 },
  "0716607|Maternal II|Integral": { capacidade: 1, demanda: 60, nota_corte_atual: 53 },
  "0716608|Berçário|Integral": { capacidade: 37, demanda: 132, nota_corte_atual: 0 },
  "0716608|Maternal I|Integral": { capacidade: 45, demanda: 98, nota_corte_atual: 0 },
  "0716608|Maternal II|Integral": { capacidade: 28, demanda: 50, nota_corte_atual: 0 },
  "0716610|Maternal I|Integral": { capacidade: 13, demanda: 169, nota_corte_atual: 0 },
  "0716610|Maternal II|Integral": { capacidade: 34, demanda: 85, nota_corte_atual: 0 },
  "0716614|Berçário|Integral": { capacidade: 31, demanda: 251, nota_corte_atual: 0 },
  "0716614|Maternal I|Integral": { capacidade: 4, demanda: 228, nota_corte_atual: 2 },
  "0716614|Maternal II|Integral": { capacidade: 6, demanda: 172, nota_corte_atual: 0 },
  "0716802|Maternal I|Integral": { capacidade: 53, demanda: 116, nota_corte_atual: 0 },
  "0716802|Maternal II|Integral": { capacidade: 56, demanda: 100, nota_corte_atual: 0 },
  "0716803|Berçário|Integral": { capacidade: 34, demanda: 165, nota_corte_atual: 0 },
  "0716803|Maternal I|Integral": { capacidade: 9, demanda: 91, nota_corte_atual: 0 },
  "0716803|Maternal II|Integral": { capacidade: 21, demanda: 75, nota_corte_atual: 0 },
  "0716804|Maternal I|Integral": { capacidade: 25, demanda: 80, nota_corte_atual: 0 },
  "0716804|Maternal II|Integral": { capacidade: 34, demanda: 73, nota_corte_atual: 0 },
  "0734601|Maternal I|Integral": { capacidade: 44, demanda: 152, nota_corte_atual: 0 },
  "0734601|Maternal II|Integral": { capacidade: 10, demanda: 44, nota_corte_atual: 0 },
  "0734602|Maternal I|Integral": { capacidade: 42, demanda: 109, nota_corte_atual: 0 },
  "0734602|Maternal II|Integral": { capacidade: 3, demanda: 13, nota_corte_atual: 0 },
  "0734603|Maternal I|Integral": { capacidade: 16, demanda: 62, nota_corte_atual: 0 },
  "0734603|Maternal II|Integral": { capacidade: 13, demanda: 22, nota_corte_atual: 0 },
};

// Calcula a posição dentro de um programa. Quando existe nota de corte real
// e ela é > 0, a posição é ancorada nela (determinística: acima do corte
// sempre cai dentro da capacidade, abaixo sempre cai fora) — nada de sorteio
// fingindo precisão que o dado real já dá. Quando o corte é 0 (pontuação não
// foi o critério decisivo) ou não há dado real, usa um desempate
// pseudo-aleatório determinístico só para a tela não ficar vazia.
function calcularPosicao({ capacidade, totalFila, notaCorte, comCorteReal }, score, seedKey) {
  if (comCorteReal && notaCorte > 0) {
    if (score >= notaCorte) {
      const faixa = Math.max(1, SCORE_MAXIMO_2025 - notaCorte);
      const margemNorm = Math.min(1, (score - notaCorte) / faixa);
      return Math.max(1, Math.round(capacidade - margemNorm * (capacidade - 1)));
    }
    const deficitNorm = Math.min(1, (notaCorte - score) / Math.max(1, notaCorte));
    const cauda = Math.max(0, totalFila - capacidade - 1);
    return capacidade + 1 + Math.round(deficitNorm * cauda);
  }
  const baseDisputa = seededInt(seedKey, 1, totalFila);
  return Math.max(1, Math.round(baseDisputa - score * 0.9));
}

function gerarClassificacaoMock(criancaId, registro) {
  const { preferencias, score, criado_em } = registro;

  const classificacoes = preferencias.map((pref) => {
    const programa = montarProgramaFromPref(pref);
    const chaveProg = `${programa.unidade}|${programa.grupamento}|${programa.turno}`;
    const real = PROGRAMAS_REAIS_2025[chaveProg];

    const capacidade = real ? real.capacidade : seededInt(chaveProg, 12, 40);
    const totalFila = real ? real.demanda : capacidade + seededInt(chaveProg + "|fila", 15, 140);
    const notaCorte = real ? real.nota_corte_atual : seededInt(chaveProg + "|corte", 10, SCORE_MAXIMO_2025);

    const posicao = calcularPosicao(
      { capacidade, totalFila, notaCorte, comCorteReal: !!real },
      score,
      criancaId + "|" + chaveProg
    );
    const posicaoFinal = Math.min(Math.max(1, posicao), totalFila);

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
    const real = PROGRAMAS_REAIS_2025[chaveProg];
    const notaCorte = real ? real.nota_corte_atual : seededInt(chaveProg + "|corte", 10, SCORE_MAXIMO_2025);

    let chance;
    if (real && notaCorte === 0) {
      // corte real, mas pontuação não decidiu esse programa — não fingimos confiança
      chance = "media";
    } else if (score >= notaCorte) {
      chance = "alta";
    } else if (score >= notaCorte - (real ? 15 : 20)) {
      chance = "media";
    } else {
      chance = "baixa";
    }
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

  async confirmarUnidade(_criancaId, _programaId) {
    await delay(150);
    return { ok: true };
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

/* ------------------------------------------------------------
   RealApi fala com o contrato de verdade do Back B (ver
   backend/app/schemas.py e backend/app/main.py) — diferente do
   contrato assumido pelo mock nesta tela. Toda tradução de forma
   (nomes de campo, granularidade unidade/programa) fica aqui, para
   as telas em app.js não precisarem saber a diferença.
   ------------------------------------------------------------ */

let _unidadesCache = null;

async function _carregarUnidades() {
  if (_unidadesCache) return _unidadesCache;
  const lista = await httpJson("/programas");
  _unidadesCache = lista.map((p) => ({ unidade: p.id, nome_unidade: p.nome, bairro: p.bairro }));
  return _unidadesCache;
}

function _prefsLocais(criancaId) {
  const cache = JSON.parse(localStorage.getItem("creche_inscricao_" + criancaId) || "null");
  return (cache && cache.preferencias) || [];
}

function _achaPrefLocal(criancaId, programaId) {
  return _prefsLocais(criancaId).find((p) => String(p.unidade) === String(programaId)) || {};
}

const RealApi = {
  async inscricao(payload) {
    const unidades = await _carregarUnidades();
    const body = {
      nome: payload.nome,
      data_nascimento: payload.data_nascimento,
      responsavel_nome: payload.responsavel_nome,
      responsavel_telefone: payload.responsavel_telefone,
      bairro: payload.bairro_cep,
      cep: "",
      preferencias: payload.preferencias.map((p) => ({
        programa_id: Number(p.unidade),
        faixa_etaria: p.grupamento,
        turno: p.turno,
      })),
      respostas_vulnerabilidade: payload.respostas,
    };
    const resp = await httpJson("/inscricao", { method: "POST", body: JSON.stringify(body) });

    // sugere, entre as preferências, a unidade mais perto do bairro informado
    // (mesma heurística por texto de bairro do modo mock — o back ainda não
    // calcula distância geográfica real, ver backend/README.md "Limitações").
    let sugerida = null;
    let menorDist = Infinity;
    for (const pref of payload.preferencias) {
      const info = unidades.find((u) => String(u.unidade) === String(pref.unidade));
      if (!info) continue;
      const d = distanciaMockKm(payload.bairro_cep, info.bairro);
      if (d < menorDist) { menorDist = d; sugerida = info; }
    }
    if (!sugerida) sugerida = unidades[0];

    return {
      crianca_id: resp.id,
      score: resp.score,
      unidade_comprovacao_sugerida: sugerida ? {
        unidade: sugerida.unidade,
        nome_unidade: sugerida.nome_unidade,
        distancia_km: menorDist === Infinity ? null : menorDist,
      } : null,
    };
  },

  confirmarUnidade(criancaId, programaId) {
    return httpJson(`/verificacao_documentos/${encodeURIComponent(criancaId)}?programa_id=${Number(programaId)}`, {
      method: "POST",
    });
  },

  async classificacao(criancaId) {
    const info = await httpJson(`/classificacao/${encodeURIComponent(criancaId)}`);

    const classificacoes = [];
    if (info.programa_escolhido_id != null) {
      const prog = await httpJson(`/programa/${info.programa_escolhido_id}`);
      const pref = _achaPrefLocal(criancaId, info.programa_escolhido_id);
      const capacidade = prog.capacidade || 1;
      let status = "espera";
      if (info.posicao_na_fila != null) {
        if (info.posicao_na_fila <= capacidade) status = "dentro";
        else if (info.posicao_na_fila <= Math.round(capacidade * 1.7)) status = "espera";
        else status = "fora";
      }
      classificacoes.push({
        programa: {
          unidade: info.programa_escolhido_id,
          nome_unidade: info.programa_escolhido_nome,
          grupamento: pref.grupamento || "",
          turno: pref.turno || "",
        },
        posicao: info.posicao_na_fila,
        total_fila: info.total_na_fila,
        status,
        pode_trocar_ate: info.pode_alterar_ate,
      });
    }

    const registro = JSON.parse(localStorage.getItem("creche_inscricao_" + criancaId) || "null");
    const score = registro ? registro.score : null;
    const sugestoes = (info.sugestoes || []).map((s) => {
      const pref = _achaPrefLocal(criancaId, s.programa_id);
      let chance = "media";
      if (s.nota_corte_atual != null && score != null) {
        if (score >= s.nota_corte_atual) chance = "alta";
        else if (score >= s.nota_corte_atual - 15) chance = "media";
        else chance = "baixa";
      }
      return {
        unidade: s.programa_id,
        nome_unidade: s.programa_nome,
        grupamento: pref.grupamento || "",
        turno: pref.turno || "",
        chance,
      };
    });

    return { classificacoes, sugestoes };
  },

  async trocar(criancaId, novaOrdemPreferencias) {
    const primeira = novaOrdemPreferencias[0];
    await httpJson(`/escolher_unidade?crianca_id=${encodeURIComponent(criancaId)}&programa_id=${Number(primeira.unidade)}`, {
      method: "POST",
    });
    const dados = await RealApi.classificacao(criancaId);
    return { ok: true, classificacoes: dados.classificacoes };
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
  listarUnidades: () => (USE_MOCK ? Promise.resolve(MOCK_UNIDADES) : _carregarUnidades()),
  enviarInscricao: (payload) => (USE_MOCK ? MockApi.inscricao(payload) : RealApi.inscricao(payload)),
  confirmarUnidade: (criancaId, unidade) => (USE_MOCK ? MockApi.confirmarUnidade(criancaId, unidade) : RealApi.confirmarUnidade(criancaId, unidade)),
  buscarClassificacao: (criancaId) => (USE_MOCK ? MockApi.classificacao(criancaId) : RealApi.classificacao(criancaId)),
  trocarPreferencias: (criancaId, novaOrdem) => (USE_MOCK ? MockApi.trocar(criancaId, novaOrdem) : RealApi.trocar(criancaId, novaOrdem)),
  buscarStatusMatricula: (criancaId) => (USE_MOCK ? MockApi.statusMatricula(criancaId) : RealApi.statusMatricula(criancaId)),
};
