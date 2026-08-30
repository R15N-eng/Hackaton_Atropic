/* ==========================================================================
   motor-api.js — única fronteira com os endpoints do motor real.

   Consome /motor/* do backend (Deferred Acceptance sobre os parquets de 2025).
   Não há mock aqui de propósito: as duas telas novas (/familia e /sme) só
   existem para mostrar dado real do motor. Se a API cair, as telas mostram
   estado de erro com botão de tentar de novo — não inventam número.
   ========================================================================== */

/* Base da API.
   Local: o front é servido em :8080 e o backend em :8000, então aponta pra 8000.
   Deploy: front no GitHub Pages e backend no Render — origens diferentes, então
   NÃO pode cair em "mesma origem" (buscaria a API no Pages e falharia).
   Mesmo valor usado em api.js, para os dois ficarem em sincronia. */
const MOTOR_API_PUBLICA = "https://hackaton-atropic-api.onrender.com";

const MOTOR_BASE = (() => {
  const host = window.location.hostname || "127.0.0.1";
  if (host === "127.0.0.1" || host === "localhost") return `http://${host}:8000`;
  return MOTOR_API_PUBLICA;
})();

async function motorFetch(caminho) {
  let res;
  try {
    res = await fetch(MOTOR_BASE + caminho, { headers: { Accept: "application/json" } });
  } catch (e) {
    const err = new Error(
      "Não conseguimos falar com o servidor. Verifique se a API está no ar."
    );
    err.status = 0;
    throw err;
  }
  if (!res.ok) {
    let msg = `Erro inesperado (${res.status}).`;
    try {
      const corpo = await res.json();
      if (typeof corpo?.detail === "string") msg = corpo.detail;
    } catch (_) { /* sem json no corpo */ }
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

const Motor = {
  metricas: () => motorFetch("/motor/metricas"),
  programas: (busca = "", limite = 200) =>
    motorFetch(`/motor/programas?busca=${encodeURIComponent(busca)}&limite=${limite}`),
  programa: (programa, limiteFila = 50) =>
    motorFetch(`/motor/programa?programa=${encodeURIComponent(programa)}&limite_fila=${limiteFila}`),
  crianca: (alunoAnon) => motorFetch(`/motor/crianca/${encodeURIComponent(alunoAnon)}`),
  criancasExemplo: (limite = 12) => motorFetch(`/motor/criancas-exemplo?limite=${limite}`),
  reclassificar: (alunoAnon) =>
    fetch(`${MOTOR_BASE}/motor/reclassificar/${encodeURIComponent(alunoAnon)}`, { method: "POST" })
      .then(async (res) => {
        if (!res.ok) {
          let msg = `Erro inesperado (${res.status}).`;
          try { const c = await res.json(); if (typeof c?.detail === "string") msg = c.detail; } catch (_) {}
          const err = new Error(msg); err.status = res.status; throw err;
        }
        return res.json();
      })
      .catch((e) => {
        if (e.status === undefined) { const err = new Error("Não conseguimos falar com o servidor."); err.status = 0; throw err; }
        throw e;
      }),
  notificacoes: (limite = 20) => motorFetch(`/motor/notificacoes?limite=${limite}`),
};

/* -------------------------- utilidades de tela -------------------------- */

const UI = {
  qs: (s, r) => (r || document).querySelector(s),
  qsa: (s, r) => Array.from((r || document).querySelectorAll(s)),

  /** Programa usado como exemplo padrão em toda a demo.
   *  Escolhido porque é o caso mais eloquente do problema: 6 vagas,
   *  343 famílias na fila, corte de 59 pontos sob o Deferred Acceptance. */
  PROGRAMA_DEMO: "0716601|Maternal II|Integral",

  num(v, casas = 0) {
    if (v === null || v === undefined) return "—";
    return Number(v).toLocaleString("pt-BR", {
      minimumFractionDigits: casas, maximumFractionDigits: casas,
    });
  },

  /** "0716601|Maternal II|Integral" -> "Maternal II · Integral" */
  rotuloTurma(programa) {
    const p = String(programa || "").split("|");
    return p.length >= 3 ? `${p[1]} · ${p[2]}` : String(programa || "—");
  },

  codigoDe(programa) {
    return String(programa || "").split("|")[0] || "—";
  },

  /** nome da unidade quando existe; senão o código, sem inventar nome */
  nomeOuCodigo(nome, codigo) {
    return nome || `Unidade ${codigo}`;
  },

  dataHora(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      });
    } catch (_) { return "—"; }
  },

  carregando(texto = "Carregando…") {
    return `<div class="estado"><div class="marcador">···</div><p>${texto}</p></div>`;
  },

  vazio(titulo, texto) {
    return `<div class="estado"><div class="marcador">—</div>
      <h3>${titulo}</h3><p>${texto}</p></div>`;
  },

  erro(mensagem, comRetentar = true) {
    return `<div class="estado"><div class="marcador">!</div>
      <h3>Não foi possível carregar</h3><p>${mensagem}</p>
      ${comRetentar ? '<button class="botao botao-vazado botao-pequeno" data-acao="retentar">Tentar de novo</button>' : ""}
    </div>`;
  },

  mensagemErro(err) {
    if (!err) return "Algo deu errado.";
    if (err.status === 0) return err.message || "Sem conexão com o servidor.";
    if (err.status === 404) return err.message || "Registro não encontrado.";
    return err.message || "Algo deu errado do nosso lado.";
  },
};
