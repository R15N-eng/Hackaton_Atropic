"""Serviço do motor real (Deferred Acceptance) — Match Carioca.

Envolve `engine/deferred_acceptance.py` e os dois parquets agregados em
`backend/data/`, e expõe os três objetos do contrato acordado com o front:
criança, programa e evento de notificação.

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
* **A alocação é calculada uma vez e mantida em memória.** O DA é
  determinístico: mesma entrada, mesma semente, mesma saída.
"""

from __future__ import annotations

import os
import sys
import datetime as dt
from collections import defaultdict
from functools import lru_cache

import duckdb

# engine/ é irmã de app/ dentro de backend/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_BACKEND_DIR, "engine"))

from deferred_acceptance import deferred_acceptance, _loteria  # noqa: E402

DATA_DIR = os.path.join(_BACKEND_DIR, "data")
OPCOES_PARQUET = os.path.join(DATA_DIR, "opcoes.parquet")
PROGRAMAS_PARQUET = os.path.join(DATA_DIR, "programas.parquet")

# base de nomes de unidade (fora dos parquets, casamento parcial)
_UNIDADES_CSV = os.path.join(
    _BACKEND_DIR, "..", "dadoscreche-main",
    "Bases IC_ ClassificadoseFila", "04_UnidadesEscolaresComEndereco.csv",
)

SEMENTE = "rio2025"
MAX_OPCOES = 5

# Peso da pergunta do CadÚnico na régua oficial de 2025 (Query C da SME).
# É a única pergunta que vale ≥ 51, por isso serve de identificador.
PESO_CADUNICO_2025 = 51

STATUS_DENTRO = "dentro_do_corte"
STATUS_ESPERA = "lista_de_espera"
STATUS_FORA = "fora"


class MotorState:
    """Estado carregado do motor: opções, capacidades, alocação e índices."""

    def __init__(self) -> None:
        con = duckdb.connect()

        self.opcoes = con.sql(
            f"""
            select crianca, programa, pref, score, unidade, grupamento, turno
            from '{OPCOES_PARQUET.replace(os.sep, '/')}'
            where pref <= {MAX_OPCOES}
            """
        ).df().to_dict("records")

        prog_df = con.sql(
            f"""
            select programa, unidade, grupamento, turno, capacidade,
                   demanda_opcoes, demanda_criancas, bairro_unidade, CRE
            from '{PROGRAMAS_PARQUET.replace(os.sep, '/')}'
            """
        ).df()
        self.programas = {r["programa"]: r for r in prog_df.to_dict("records")}
        self.capacidades = {
            r["programa"]: int(r["capacidade"]) for r in prog_df.to_dict("records")
        }

        self.nomes_unidade = self._carregar_nomes(con)
        con.close()

        # score por criança (a maior, se houver mais de uma inscrição)
        self.score = {}
        for o in self.opcoes:
            cr = o["crianca"]
            self.score[cr] = max(self.score.get(cr, 0.0), float(o["score"]))

        # preferências ordenadas por criança
        self.prefs = defaultdict(list)
        for o in self.opcoes:
            self.prefs[o["crianca"]].append((int(o["pref"]), o["programa"]))
        for cr in self.prefs:
            self.prefs[cr] = [p for _, p in sorted(set(self.prefs[cr]))]

        # (crianca, programa) -> pref, para saber a que opção corresponde a vaga
        self.pref_de = {
            (o["crianca"], o["programa"]): int(o["pref"]) for o in self.opcoes
        }

        # alocação base
        self.alocacao = deferred_acceptance(
            [
                {"crianca": o["crianca"], "programa": o["programa"],
                 "pref": int(o["pref"]), "score": float(o["score"])}
                for o in self.opcoes
            ],
            self.capacidades,
            semente=SEMENTE,
        )

        self._indexar()

    def _carregar_nomes(self, con) -> dict:
        """Nomes de unidade da base de endereços da SME. Casamento parcial —
        onde não casa, a unidade fica sem nome (o front mostra o código)."""
        caminho = os.path.abspath(_UNIDADES_CSV)
        if not os.path.exists(caminho):
            return {}
        try:
            df = con.sql(
                f"""
                select column1 as esc_codigo, column2 as nome
                from read_csv_auto('{caminho.replace(os.sep, '/')}',
                                   delim=';', header=false, encoding='utf-8')
                """
            ).df()
            return dict(zip(df.esc_codigo.astype(str), df.nome))
        except Exception:
            # base de nomes é acessório: sem ela o motor continua funcionando
            return {}

    def _indexar(self) -> None:
        """Índices derivados da alocação atual: ocupação, corte e fila."""
        self.ocupadas = defaultdict(list)
        for cr, prog in self.alocacao.items():
            self.ocupadas[prog].append(cr)

        # nota de corte: menor score entre as alocadas — só faz sentido se o
        # programa encheu. Se sobrou vaga, não houve corte (None).
        self.nota_corte = {}
        for prog, crs in self.ocupadas.items():
            cap = self.capacidades.get(prog, 0)
            if crs and len(crs) >= cap:
                self.nota_corte[prog] = min(self.score.get(c, 0.0) for c in crs)
            else:
                self.nota_corte[prog] = None

        # Lista de espera de um programa X: crianças que listaram X, não foram
        # alocadas em X, e cuja alocação atual é PIOR que X (pref maior) ou
        # inexistente — ou seja, aceitariam X se abrisse vaga. Ordenada por
        # prioridade do DA (score desc, depois a loteria única).
        self.lista_espera = defaultdict(list)
        for (cr, prog), pref in self.pref_de.items():
            if self.alocacao.get(cr) == prog:
                continue
            atual = self.alocacao.get(cr)
            pref_atual = self.pref_de.get((cr, atual)) if atual else None
            if atual is None or (pref_atual is not None and pref_atual > pref):
                self.lista_espera[prog].append(cr)
        for prog in self.lista_espera:
            self.lista_espera[prog].sort(
                key=lambda c: (-self.score.get(c, 0.0), -_loteria(c, SEMENTE))
            )


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
        "demanda_criancas": int(info["demanda_criancas"]),
        "total_lista_de_espera": len(fila),
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
    """Simula 'a criança não confirmou': remove todas as opções dela, roda o
    DA de novo e devolve o diff entre a alocação antiga e a nova.

    Não altera o estado global — a alocação base continua intacta, para a
    demo poder rodar o mesmo cenário várias vezes.
    """
    st = estado()
    if aluno_anon not in st.prefs:
        return {"erro": "crianca_nao_encontrada", "aluno_anon": aluno_anon}

    programa_liberado = st.alocacao.get(aluno_anon)

    opcoes_sem = [
        {"crianca": o["crianca"], "programa": o["programa"],
         "pref": int(o["pref"]), "score": float(o["score"])}
        for o in st.opcoes if o["crianca"] != aluno_anon
    ]
    nova = deferred_acceptance(opcoes_sem, st.capacidades, semente=SEMENTE)

    # diff: quem mudou de situação por causa da saída
    movimentos = []
    for cr, prog_novo in nova.items():
        prog_antigo = st.alocacao.get(cr)
        if prog_antigo == prog_novo or cr == aluno_anon:
            continue
        fila_antiga = st.lista_espera.get(prog_novo, [])
        movimentos.append({
            "aluno_anon": cr,
            "score": st.score.get(cr, 0.0),
            "cadunico": _eh_cadunico(st.score.get(cr, 0.0)),
            "de": prog_antigo,
            "para": prog_novo,
            "de_posicao": (fila_antiga.index(cr) + 1) if cr in fila_antiga else None,
            "para_posicao": "alocada",
            "tipo": "subiu_da_lista_de_espera" if prog_antigo is None else "trocou_de_programa",
        })

    perderam = [
        cr for cr, prog in st.alocacao.items()
        if cr != aluno_anon and cr not in nova
    ]

    movimentos.sort(key=lambda m: -m["score"])

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
        "semente": SEMENTE,
        "max_opcoes": MAX_OPCOES,
    }
