"""Serviço do motor real (Deferred Acceptance) — Match Carioca.

Envolve o motor da Pessoa 1 (`pessoa_1/`, na raiz do repo -- Deferred
Acceptance com os critérios reais de desempate da SME + antiguidade da
inscrição, não só sorteio) e expõe os três objetos do contrato acordado com
o front: criança, programa e evento de notificação.

Antes deste módulo usava `backend/engine/deferred_acceptance.py` (motor
próprio, mais simples, desempate só por loteria) sobre
`backend/data/*.parquet` (pipeline próprio, só 2025, sem os critérios de
desempate por pergunta). Trocado pelo motor da Pessoa 1 porque:

* os critérios reais de desempate (irmão na creche, mãe adolescente) só
  existem no parquet gerado por `pessoa_1/build_data.py` -- o outro pipeline
  só preserva o score somado, não quais perguntas específicas foram
  respondidas 'Sim';
* o motor da Pessoa 1 tem 164 testes (unitários + contra os 5 processos
  reais), incluindo a descoberta de que uma desistência pode deslocar um
  terceiro (não é monotônica) -- o motor antigo não cobria esse caso.

Regras que valem para todo este módulo:

* **Nenhum campo inventado.** Só sai daqui o que existe nos parquets ou é
  derivado deles de forma explícita e documentada. Não há tempo de espera,
  distância exata nem renda — esses dados não existem na base.
* **`cadunico` é derivado, não é coluna.** Não existe coluna `cadunico` nos
  parquets. Na régua de 2025 a pergunta do CadÚnico vale 51 dos 100 pontos
  possíveis, e é a única que vale ≥ 51 — então `score >= 51` identifica quem
  declarou CadÚnico. É um proxy exato para 2025, não uma estimativa; se a régua
  mudar de ano, esta derivação precisa mudar junto (ver `PESO_CADUNICO_2025`).
* **`unidade_nome` vem de fora dos parquets** (a base de endereços da SME) e
  casa em ~58% das unidades. Onde não casa, fica `None` e o front mostra o
  código — em vez de inventar um nome.
* **`programa` (a chave usada na API) não tem o ano.** O motor da Pessoa 1
  usa `programa_id = "ano|unidade|grupamento|horario"` (para caber vários
  anos no mesmo parquet); este serviço tira o prefixo do ano em
  `_sem_ano`, porque a API e o front já publicados usam
  `unidade|grupamento|turno` sem ano -- só existe 2025 aqui (`ANO`), então
  o prefixo não carrega informação nova neste contexto.
* **A alocação é calculada uma vez e mantida em memória.** O DA é
  determinístico: mesma entrada, mesma saída (não depende de sorteio para
  decidir quem entra -- os critérios de desempate são reais; sorteio só
  entra se dois candidatos empatarem em score E em todos os critérios E na
  data de inscrição, o que não ocorre nos dados reais).
"""

from __future__ import annotations

import os
import sys
import datetime as dt
from collections import Counter, defaultdict
from functools import lru_cache

import pandas as pd

# pessoa_1/ é irmã de backend/ na raiz do repo
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pessoa_1 import carga as motor_carga  # noqa: E402
from pessoa_1 import fila as motor_fila  # noqa: E402
from pessoa_1.deferred_acceptance import deferred_acceptance as rodar_deferred_acceptance  # noqa: E402

# base de nomes de unidade (fora dos parquets, casamento parcial)
_UNIDADES_CSV = os.path.join(
    _REPO_ROOT, "dadoscreche-main",
    "Bases IC_ ClassificadoseFila", "04_UnidadesEscolaresComEndereco.csv",
)

ANO = 2025
MAX_OPCOES = 5

# Peso da pergunta do CadÚnico na régua oficial de 2025 (Query C da SME).
# É a única pergunta que vale ≥ 51, por isso serve de identificador.
PESO_CADUNICO_2025 = 51

STATUS_DENTRO = "dentro_do_corte"
STATUS_ESPERA = "lista_de_espera"
STATUS_FORA = "fora"


def _sem_ano(programa_id: str) -> str:
    """`"2025|0716601|Maternal II|Integral"` -> `"0716601|Maternal II|Integral"`.

    Ver nota no docstring do módulo -- o contrato externo não tem o ano.
    """
    return programa_id.split("|", 1)[1]


def _ou_none(valor):
    """`None` tanto para `None` quanto para `NaN` -- pandas usa `NaN` (nao
    `None`) para numero ausente ao ler parquet, e `int(NaN)` levanta erro."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return valor


class MotorState:
    """Estado carregado do motor: opções, capacidades, alocação e índices."""

    def __init__(self) -> None:
        candidatos, programas = motor_carga.carregar_ano(ANO)
        self._por_programa_id = {p.programa_id: p for p in programas}

        # Metadados de exibição direto do parquet (bairro/CRE/geo, demanda) --
        # não passam pelos dataclasses do motor porque não são entrada do
        # algoritmo, só informação para a tela.
        tabela_programas = pd.read_parquet(motor_carga.DIR_DADOS / "programas.parquet")
        tabela_programas = tabela_programas[tabela_programas["ano"] == ANO]
        self.programas = {}
        for linha in tabela_programas.to_dict("records"):
            prog = _sem_ano(linha["programa_id"])
            self.programas[prog] = {
                "unidade": linha.get("unidade"),
                "grupamento": linha.get("grupamento"),
                "turno": linha.get("horario"),
                "capacidade": int(linha.get("vagas") or 0),
                # NaN (nao None) quando a unidade nao geocodificou -- pandas
                # representa "sem valor" numerico como NaN, nao None
                "bairro_unidade": _ou_none(linha.get("bairro_unidade")),
                "CRE": _ou_none(linha.get("cre")),
                "lat": _ou_none(linha.get("lat")),
                "lon": _ou_none(linha.get("lon")),
            }
        self.capacidades = {p: info["capacidade"] for p, info in self.programas.items()}

        self.nomes_unidade = self._carregar_nomes()

        # score por criança e preferências ordenadas -- direto dos objetos do
        # motor, sem reler o parquet (Candidato já agrega multi-inscrição
        # pegando o maior score, mesma regra de antes).
        #
        # Sem limite de 5 aqui de propósito: o algoritmo (`motor_da`, abaixo)
        # usa `candidato.preferencias` inteira, sem cortar -- exibir só as 5
        # primeiras faria a tela mentir sobre o que o motor considerou. Para
        # a maioria das crianças são <=5 mesmo (uma inscrição, até 5 opções);
        # passa disso só nos ~13% de multi-inscrição no ano (preferências de
        # duas inscrições concatenadas, ver `carga.carregar_candidatos`).
        self.score = {c.crianca_id: float(int(c.score)) for c in candidatos}
        self.prefs = {
            c.crianca_id: [_sem_ano(p) for p in c.preferencias] for c in candidatos
        }
        self.pref_de = {
            (c.crianca_id, _sem_ano(p)): i + 1
            for c in candidatos
            for i, p in enumerate(c.preferencias)
        }

        # demanda: quantas opções/crianças distintas listaram cada programa.
        # Nota: como Candidato agrega multi-inscrição num só (ver
        # carregar_candidatos), demanda_opcoes == demanda_criancas aqui,
        # diferente do pipeline anterior (que contava por inscrição, não por
        # criança) -- diferença so nos ~8.000 casos de multi-inscrição/ano,
        # e so afeta esses dois numeros de exibicao, nao o algoritmo.
        self.demanda_opcoes = Counter()
        self.demanda_criancas = Counter()
        for prefs in self.prefs.values():
            for prog in set(prefs):
                self.demanda_opcoes[prog] += 1
                self.demanda_criancas[prog] += 1

        # --- motor real: Deferred Acceptance da Pessoa 1 -----------------
        alocacao = rodar_deferred_acceptance(candidatos, programas)
        self._alocacao_motor = alocacao
        self.alocacao = {cr: _sem_ano(pid) for cr, pid in alocacao.matches.items()}

        self._indexar()

    def _carregar_nomes(self) -> dict:
        """Nomes de unidade da base de endereços da SME. Casamento parcial —
        onde não casa, a unidade fica sem nome (o front mostra o código)."""
        if not os.path.exists(_UNIDADES_CSV):
            return {}
        try:
            df = motor_carga.consultar_duckdb(
                f"""
                select column1 as esc_codigo, column2 as nome
                from read_csv_auto('{_UNIDADES_CSV.replace(os.sep, '/')}',
                                   delim=';', header=false, encoding='utf-8')
                """
            )
            return dict(zip(df.esc_codigo.astype(str), df.nome))
        except Exception:
            # base de nomes é acessório: sem ela o motor continua funcionando
            return {}

    def _indexar(self) -> None:
        """Índices derivados da alocação atual: ocupação, corte e fila.

        `nota_corte`/`lista_espera` vem direto do resultado do motor
        (`ProgramaAlocado.admitidos`/`.fila`), já ordenados pelos critérios
        reais de desempate (não recalculados aqui com um score+loteria
        aproximado, como antes).
        """
        self.ocupadas = defaultdict(list)
        for cr, prog in self.alocacao.items():
            self.ocupadas[prog].append(cr)

        self.nota_corte = {}
        self.lista_espera = {}
        for programa_id, programa_alocado in self._alocacao_motor.programas.items():
            prog = _sem_ano(programa_id)
            # só reporta corte se o programa de fato lotou -- com vaga
            # sobrando o "menor score admitido" não é uma barreira real
            # (mesma ressalva de `fila.nota_corte_atual`)
            self.nota_corte[prog] = (
                motor_fila.nota_corte_atual(programa_alocado)
                if programa_alocado.lotado
                else None
            )
            self.lista_espera[prog] = [c.crianca_id for c in programa_alocado.fila]


_STATE: MotorState | None = None


def estado() -> MotorState:
    """Carrega o motor na primeira chamada e reaproveita depois."""
    global _STATE
    if _STATE is None:
        _STATE = MotorState()
    return _STATE


# ---------------------------------------------------------------------------
# Serialização — os objetos do contrato
# ---------------------------------------------------------------------------

def _nome_unidade(st: MotorState, codigo_unidade: str):
    return st.nomes_unidade.get(str(codigo_unidade))


def _eh_cadunico(score: float) -> bool:
    """Derivado, não é coluna — ver docstring do módulo."""
    return score >= PESO_CADUNICO_2025


def serializar_crianca(aluno_anon: str) -> dict | None:
    """Objeto `criança` do contrato. None se a criança não existe na base.

    Sobre `posicao_na_lista_espera`: uma criança pode ter vaga numa opção
    menos preferida E continuar na fila de uma opção melhor. Nesse caso o
    status é `dentro_do_corte` (ela tem vaga — é o fato mais importante para
    a família), mas a posição reportada é a da melhor opção em que ela ainda
    espera. Sem isso a tela diria "você tem vaga" e esconderia justamente o
    que a família quer saber.

    Os campos `pref_atendida` e `esperando_por` são derivados dos mesmos
    dados (nº da preferência atendida e filas das opções melhores) e existem
    para a tela Família poder explicar o "por quê" sem recalcular nada.
    """
    st = estado()
    if aluno_anon not in st.prefs:
        return None

    score = st.score.get(aluno_anon, 0.0)
    alocado = st.alocacao.get(aluno_anon)
    opcoes = list(st.prefs[aluno_anon])

    pref_atendida = st.pref_de.get((aluno_anon, alocado)) if alocado else None

    # opções que a família prefere sobre o que conseguiu (ou todas, se não
    # conseguiu nada), com a posição atual dela na fila de cada uma
    limite = pref_atendida if pref_atendida is not None else len(opcoes) + 1
    esperando_por = []
    for prog in opcoes:
        pref = st.pref_de.get((aluno_anon, prog))
        if pref is None or pref >= limite:
            continue
        fila = st.lista_espera.get(prog, [])
        if aluno_anon in fila:
            esperando_por.append({
                "programa": prog,
                "pref": pref,
                "posicao": fila.index(aluno_anon) + 1,
                "total_na_fila": len(fila),
                "nota_de_corte_atual": st.nota_corte.get(prog),
            })

    if alocado:
        status = STATUS_DENTRO
    elif esperando_por:
        status = STATUS_ESPERA
    else:
        status = STATUS_FORA

    posicao = esperando_por[0]["posicao"] if esperando_por else None

    return {
        "aluno_anon": aluno_anon,
        "score": score,
        "cadunico": _eh_cadunico(score),
        "opcoes": opcoes,
        "status": status,
        "programa_alocado": alocado,
        "posicao_na_lista_espera": posicao,
        # --- derivados, para a explicação em linguagem simples ---
        "pref_atendida": pref_atendida,
        "esperando_por": esperando_por,
    }


def analise_por_programa(programa: str, limite_fila: int = 50) -> dict | None:
    """Objeto `programa` do contrato: corte atual, ocupação e lista de espera
    ordenada por score desc. None se o programa não existe."""
    st = estado()
    if programa not in st.programas:
        return None

    info = st.programas[programa]
    ocupadas = st.ocupadas.get(programa, [])
    fila = st.lista_espera.get(programa, [])

    return {
        "esc_codigo": str(info["unidade"]),
        "programa": programa,
        "unidade_nome": _nome_unidade(st, info["unidade"]),
        "grupamento": info["grupamento"],
        "turno": info["turno"],
        "bairro_unidade": info.get("bairro_unidade"),
        "CRE": int(info["CRE"]) if info.get("CRE") is not None else None,
        "capacidade": int(info["capacidade"]),
        "ocupadas": len(ocupadas),
        "nota_de_corte_atual": st.nota_corte.get(programa),
        "demanda_criancas": int(st.demanda_criancas.get(programa, 0)),
        "total_lista_de_espera": len(fila),
        # quem ocupa as vagas hoje, da menor para a maior pontuação — é desta
        # lista que sai o candidato a "não confirmou" na tela de reclassificação
        "alocadas": [
            {
                "aluno_anon": cr,
                "score": st.score.get(cr, 0.0),
                "cadunico": _eh_cadunico(st.score.get(cr, 0.0)),
                "pref_atendida": st.pref_de.get((cr, programa)),
            }
            for cr in sorted(ocupadas, key=lambda c: st.score.get(c, 0.0))
        ],
        "lista_de_espera": [
            {
                "aluno_anon": cr,
                "score": st.score.get(cr, 0.0),
                "cadunico": _eh_cadunico(st.score.get(cr, 0.0)),
                "posicao": i + 1,
            }
            for i, cr in enumerate(fila[:limite_fila])
        ],
    }


def listar_programas(busca: str = "", limite: int = 100) -> list[dict]:
    """Lista enxuta de programas para o seletor do painel SME."""
    st = estado()
    termo = (busca or "").strip().lower()
    saida = []
    for prog, info in st.programas.items():
        nome = _nome_unidade(st, info["unidade"]) or ""
        if termo and termo not in prog.lower() and termo not in nome.lower():
            continue
        saida.append({
            "programa": prog,
            "esc_codigo": str(info["unidade"]),
            "unidade_nome": nome or None,
            "grupamento": info["grupamento"],
            "turno": info["turno"],
            "bairro_unidade": info.get("bairro_unidade"),
            "capacidade": int(info["capacidade"]),
            "ocupadas": len(st.ocupadas.get(prog, [])),
            "nota_de_corte_atual": st.nota_corte.get(prog),
            "total_lista_de_espera": len(st.lista_espera.get(prog, [])),
        })
        if len(saida) >= limite:
            break
    return saida


# ---------------------------------------------------------------------------
# Reclassificação — quem sobe quando uma vaga é liberada
# ---------------------------------------------------------------------------

def reclassificar_sem(aluno_anon: str) -> dict:
    """Simula 'a criança não confirmou': remove a criança do processo, roda
    o motor de novo e devolve o diff entre a alocação antiga e a nova.

    Usa `pessoa_1.reclassificar` com `saidas=[aluno_anon]` -- saída completa
    do processo, não desistência de uma opção específica (essa distinção
    importa: desistir de UMA opção pode deslocar um terceiro sem liberar
    vaga alguma, ver `pessoa_1/README.md`; aqui é sempre saída total, que É
    monotônica -- nunca piora a situação de terceiros).

    Não altera o estado global — a alocação base continua intacta, para a
    demo poder rodar o mesmo cenário várias vezes.
    """
    st = estado()
    if aluno_anon not in st.prefs:
        return {"erro": "crianca_nao_encontrada", "aluno_anon": aluno_anon}

    from pessoa_1.reclassificar import reclassificar as rodar_reclassificar

    programa_liberado = st.alocacao.get(aluno_anon)
    resultado = rodar_reclassificar(st._alocacao_motor, saidas=[aluno_anon])
    nova = {cr: _sem_ano(pid) for cr, pid in resultado.alocacao.matches.items()}

    movimentos = [
        {
            "aluno_anon": m.crianca_id,
            "score": float(m.score),
            "cadunico": _eh_cadunico(float(m.score)),
            "de": _sem_ano(m.de) if m.de else None,
            "para": _sem_ano(m.para) if m.para else None,
            "de_posicao": m.posicao_na_fila_anterior,
            "para_posicao": "alocada",
            "tipo": "subiu_da_lista_de_espera" if m.de is None else "trocou_de_programa",
        }
        for m in resultado.subiram
    ]
    perderam = [m.crianca_id for m in resultado.sairam if m.crianca_id != aluno_anon]

    return {
        "aluno_anon_removido": aluno_anon,
        "programa_liberado": programa_liberado,
        "alocadas_antes": len(st.alocacao),
        "alocadas_depois": len(nova),
        "total_movimentos": len(movimentos),
        "movimentos": movimentos[:50],
        "perderam_vaga": perderam[:50],
        "gerado_em": dt.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Amostra para o seletor da tela Família (não há login real)
# ---------------------------------------------------------------------------

def amostra_criancas(limite: int = 12) -> list[dict]:
    """Identificadores de exemplo cobrindo os três status, para a banca poder
    testar cada caso sem adivinhar um `aluno_anon` válido."""
    st = estado()
    por_status: dict[str, list[dict]] = {
        STATUS_DENTRO: [], STATUS_ESPERA: [], STATUS_FORA: [],
    }
    cota = max(1, limite // 3)

    for cr in st.prefs:
        if all(len(v) >= cota for v in por_status.values()):
            break
        c = serializar_crianca(cr)
        if c and len(por_status[c["status"]]) < cota:
            por_status[c["status"]].append({
                "aluno_anon": c["aluno_anon"],
                "score": c["score"],
                "cadunico": c["cadunico"],
                "status": c["status"],
                "programa_alocado": c["programa_alocado"],
                "posicao_na_lista_espera": c["posicao_na_lista_espera"],
            })

    saida = []
    for status in (STATUS_DENTRO, STATUS_ESPERA, STATUS_FORA):
        saida.extend(por_status[status])
    return saida[:limite]


# ---------------------------------------------------------------------------
# Notificações — SIMULADAS (Twilio sem credencial neste ambiente)
# ---------------------------------------------------------------------------

def timeline_notificacoes(limite: int = 20) -> dict:
    """Timeline de envios. **Dados simulados.**

    O Twilio existe no backend mas não tem credencial configurada aqui, então
    nenhuma mensagem real foi enviada. Esta função monta a timeline a partir de
    dados REAIS do motor (quem foi alocado, em qual programa, com que score) e
    simula apenas o *envio* — horário e status de confirmação. A resposta
    carrega `mock: true` para a tela avisar o usuário, em vez de misturar
    simulação com dado real sem sinalizar.
    """
    st = estado()
    agora = dt.datetime.utcnow()

    # ordem determinística: maior score primeiro (é a ordem em que a SME
    # convocaria), para a timeline não mudar a cada recarga da página
    alocadas = sorted(
        st.alocacao.items(),
        key=lambda kv: (-st.score.get(kv[0], 0.0), kv[0]),
    )[:limite]

    ciclo = ["confirmado", "aguardando", "expirado"]
    eventos = []
    for i, (cr, prog) in enumerate(alocadas):
        info = st.programas.get(prog, {})
        nome = _nome_unidade(st, info.get("unidade", "")) or str(info.get("unidade", ""))
        enviado = agora - dt.timedelta(hours=i * 3 + 1)
        eventos.append({
            "aluno_anon": cr,
            "programa": prog,
            "unidade_nome": nome,
            "canal": "whatsapp",
            "enviado_em": enviado.isoformat() + "Z",
            "texto": (
                f"Prefeitura do Rio / SME: sua vaga de creche foi definida em "
                f"{nome}. Compareca a unidade com os documentos para confirmar "
                f"a matricula."
            ),
            "status_confirmacao": ciclo[i % len(ciclo)],
        })

    return {
        "mock": True,
        "aviso": (
            "Envios simulados: o Twilio nao tem credencial configurada neste "
            "ambiente. Criancas, programas e scores sao dados reais do motor; "
            "horario de envio e status de confirmacao sao simulados."
        ),
        "total": len(eventos),
        "eventos": eventos,
    }


# ---------------------------------------------------------------------------
# Métricas gerais (para o cabeçalho do painel SME)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def metricas_gerais() -> dict:
    st = estado()
    total_criancas = len(st.prefs)
    colocadas = len(st.alocacao)

    prefs_atendidas = [
        st.pref_de.get((cr, prog)) for cr, prog in st.alocacao.items()
    ]
    prefs_atendidas = [p for p in prefs_atendidas if p is not None]
    primeira = sum(1 for p in prefs_atendidas if p == 1)

    vuln = [cr for cr in st.prefs if _eh_cadunico(st.score.get(cr, 0.0))]
    vuln_col = sum(1 for cr in vuln if cr in st.alocacao)
    nao_vuln = [cr for cr in st.prefs if not _eh_cadunico(st.score.get(cr, 0.0))]
    nao_vuln_col = sum(1 for cr in nao_vuln if cr in st.alocacao)

    return {
        "total_criancas": total_criancas,
        "total_programas": len(st.programas),
        "capacidade_total": sum(st.capacidades.values()),
        "criancas_colocadas": colocadas,
        "pct_primeira_opcao": round(100 * primeira / max(colocadas, 1), 1),
        "preferencia_media": round(sum(prefs_atendidas) / max(len(prefs_atendidas), 1), 2),
        "pct_vulneraveis_colocadas": round(100 * vuln_col / max(len(vuln), 1), 1),
        "pct_nao_vulneraveis_colocadas": round(100 * nao_vuln_col / max(len(nao_vuln), 1), 1),
        "semente": "motor-pessoa1-deterministico",
        "max_opcoes": MAX_OPCOES,
    }
