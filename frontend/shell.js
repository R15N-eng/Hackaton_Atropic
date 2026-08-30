/* ==========================================================================
   shell.js — cabeçalho, navegação e rodapé compartilhados.

   Antes deste arquivo o site eram 7 páginas soltas: cada uma com seu próprio
   cabeçalho, nenhuma com rodapé, e o alternador de perfil existindo só em
   familia.html/sme.html. Aqui a casca é gerada num lugar só, então as 7 telas
   ficam idênticas por construção — não por eu ter lembrado de repetir o mesmo
   HTML sete vezes.

   Uso: incluir <script src="shell.js"></script> no fim do <body> e declarar
   no <body> o que a tela é:
       data-shell-perfil="familia" | "sme"
       data-shell-etapa="1".."4"        (só no fluxo de 4 etapas)
   ========================================================================== */

(function () {
  const corpo = document.body;
  const perfil = corpo.dataset.shellPerfil || "familia";
  const etapa = corpo.dataset.shellEtapa ? Number(corpo.dataset.shellEtapa) : null;

  const ETAPAS = [
    { n: 1, rotulo: "Inscrição", pagina: "inscricao.html" },
    { n: 2, rotulo: "Verificação", pagina: "verificacao.html" },
    { n: 3, rotulo: "Classificação", pagina: "classificacao.html" },
    { n: 4, rotulo: "Matrícula", pagina: "status.html" },
  ];

  // Navega SEM colocar o crianca_id na URL: o id fica só no localStorage
  // deste aparelho, para não vazar em histórico do navegador, print de tela ou
  // link compartilhado por WhatsApp (decisão do time em app.js:App.getCriancaId).
  // Quem precisa acompanhar de outro aparelho entra por login.html.
  function comId(pagina) {
    return pagina;
  }

  /* ------------------------------ cabeçalho ------------------------------ */

  const cabecalho = `
    <div class="shell-topo">
      <div class="shell-interno">
        <span><b>Prefeitura do Rio</b> · Secretaria Municipal de Educação</span>
        <span class="shell-topo-sel">Protótipo — Claude Impact Lab 2026</span>
      </div>
    </div>
    <header class="shell-cabecalho">
      <div class="shell-interno">
        <a class="shell-marca" href="index.html">
          <span class="shell-traco" aria-hidden="true"></span>
          <span><span class="shell-match">Match</span><span class="shell-carioca">Carioca</span></span>
        </a>
        <nav class="shell-perfis" aria-label="Perfil de acesso">
          <a href="inscricao.html"${perfil === "familia" ? ' aria-current="page"' : ""}>Família</a>
          <a href="sme.html"${perfil === "sme" ? ' aria-current="page"' : ""}>SME / CRE</a>
        </nav>
      </div>
    </header>`;

  /* ------------------- trilha de etapas (fluxo da família) ------------------- */

  let trilha = "";
  if (etapa) {
    const atual = ETAPAS.find((e) => e.n === etapa);
    trilha = `
      <div class="shell-trilha">
        <div class="shell-interno">
          <ol class="shell-passos">
            ${ETAPAS.map((e, i) => {
              const estado = e.n < etapa ? "feito" : e.n === etapa ? "atual" : "";
              // etapas já concluídas são navegáveis; as futuras, não — a família
              // não pode pular para a classificação antes de se inscrever
              const conteudo = `<span class="shell-bola">${e.n < etapa ? "✓" : e.n}</span><span class="shell-rotulo">${e.rotulo}</span>`;
              const item = e.n < etapa
                ? `<a href="${comId(e.pagina)}">${conteudo}</a>`
                : `<span>${conteudo}</span>`;
              return `${i > 0 ? '<li class="shell-liga" aria-hidden="true"></li>' : ""}
                      <li class="shell-passo ${estado}">${item}</li>`;
            }).join("")}
          </ol>
          <p class="shell-etapa-texto">Etapa ${etapa} de 4 — ${atual ? atual.rotulo : ""}</p>
        </div>
      </div>`;
  }

  /* -------------------------------- rodapé -------------------------------- */

  const rodape = `
    <footer class="shell-rodape">
      <div class="shell-interno shell-rodape-grade">
        <div>
          <b>Sobre os dados</b>
          Base anonimizada pela SME (aleatorização, generalização e supressão).
          <span class="shell-destaque">Os indicadores não representam a realidade</span> —
          ilustram a dinâmica do processo de inscrição em creche de 2021 a 2025.
        </div>
        <div>
          <b>Match Carioca</b>
          Protótipo do Claude Impact Lab Rio #2, inspirado na identidade visual da
          Prefeitura do Rio. Não é serviço oficial nem extensão do site matricula.rio.
        </div>
      </div>
    </footer>`;

  /* ------------------------------ montagem ------------------------------ */

  // substitui o cabeçalho antigo da página, se houver, para não duplicar
  const antigos = document.querySelectorAll(
    "header.app-header, .stepper-bar, header.cabecalho, .barra-topo"
  );
  antigos.forEach((el) => el.remove());

  corpo.insertAdjacentHTML("afterbegin", cabecalho + trilha);
  corpo.insertAdjacentHTML("beforeend", rodape);
})();
