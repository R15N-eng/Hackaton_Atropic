"""Tipos de dominio. Todos imutaveis: as funcoes do pacote sao puras e
devolvem novos objetos em vez de mutar os recebidos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, Optional

from .contrato import DESEMPATE_ORDEM
from .localizacao import Localizacao

# datetime sentinela para inscricao sem data: perde o desempate por antiguidade.
SEM_DATA = datetime.max


# ---------------------------------------------------------------------------
# Regua de pontuacao (Query C)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Pergunta:
    """Uma linha da Query C: a pergunta como ela existiu num ano especifico."""

    ich_perg_id: int   # instancia da pergunta no ano -> junta com a Query B
    perg_id: int       # chave estavel no catalogo -> comparavel entre anos
    pontuacao: int
    criterio: bool     # True = desempate, nao soma pontos
    texto: str = ""
    ordem: int = 0


@dataclass(frozen=True)
class ReguaDoAno:
    """A regua de um processo. `perg_pontuacao` mudou entre anos (perg_id=2 saiu
    de 100 para 25 pontos em 2024), por isso a regua e sempre por ano."""

    ano: int
    perguntas: Mapping[int, Pergunta]  # ich_perg_id -> Pergunta

    @property
    def pontuacao_maxima(self) -> int:
        return sum(p.pontuacao for p in self.perguntas.values())

    def por_perg_id(self, perg_id: int) -> Optional[Pergunta]:
        for p in self.perguntas.values():
            if p.perg_id == perg_id:
                return p
        return None

    @classmethod
    def de_linhas_queryc(cls, ano: int, linhas: Iterable[Mapping]) -> "ReguaDoAno":
        """Constroi a regua direto das linhas da Query C (dicts ou Series)."""
        perguntas: dict[int, Pergunta] = {}
        for linha in linhas:
            if int(linha["ano"]) != int(ano):
                continue
            pontuacao = int(linha["perg_pontuacao"] or 0)
            bruto = str(linha.get("perg_criterio") or "").strip().lower()
            perguntas[int(linha["ich_perg_id"])] = Pergunta(
                ich_perg_id=int(linha["ich_perg_id"]),
                perg_id=int(linha["perg_id"]),
                pontuacao=pontuacao,
                # criterio = marcado como tal OU vale zero ponto (equivalentes
                # na extracao: as 10 linhas coincidem)
                criterio=bruto.startswith("s") or pontuacao == 0,
                texto=str(linha.get("pergunta_texto") or "").strip(),
                ordem=int(linha.get("perg_ordemVisualizacao") or 0),
            )
        return cls(ano=int(ano), perguntas=perguntas)


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Score:
    """Resultado de `calcular_score`. Compara por `total`, para poder ser
    confrontado direto com uma nota de corte."""

    total: int
    detalhe: Mapping[int, int] = field(default_factory=dict)        # perg_id -> pontos
    desempates: frozenset = field(default_factory=frozenset)        # perg_id
    ano: Optional[int] = None
    pontuacao_maxima: Optional[int] = None
    ignoradas: frozenset = field(default_factory=frozenset)         # ich_perg_id fora da regua

    @property
    def pct_maxima(self) -> Optional[float]:
        if not self.pontuacao_maxima:
            return None
        return round(self.total / self.pontuacao_maxima * 100, 2)

    def __int__(self) -> int:
        return self.total

    def __lt__(self, outro) -> bool:
        return self.total < _total(outro)

    def __le__(self, outro) -> bool:
        return self.total <= _total(outro)

    def __gt__(self, outro) -> bool:
        return self.total > _total(outro)

    def __ge__(self, outro) -> bool:
        return self.total >= _total(outro)


def _total(valor) -> int:
    return valor.total if isinstance(valor, Score) else int(valor)


# ---------------------------------------------------------------------------
# Candidato e programa
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Candidato:
    """Uma crianca inscrita: score, preferencias e (quando disponivel) as
    localizacoes usadas na linha de distancia. Classe unica -- ate pouco
    atras `vulnerabilidade.py` tinha o seu proprio `Candidato`, com um dict
    de flags separado guardando a mesma informacao que `score` ja guarda.

    `score` e a UNICA fonte de verdade sobre quais perguntas a familia
    respondeu 'Sim': tanto para o motor da regua oficial (`score.total`)
    quanto para a contagem de vulnerabilidade sem peso, usada na linha de
    distancia (`vulnerabilidade.pontuacao_vulnerabilidade`, que le
    `score.detalhe` + `score.desempates` -- a uniao das duas e toda pergunta
    de vulnerabilidade que a familia confirmou, pontuada ou so criterio).

    `preferencias` vem da coluna `opcao` (1 = primeira escolha). E a lista de
    preferencias do lado das familias no Deferred Acceptance.

    `localizacoes` e opcional (`None` por padrao): so existe pra quem ja tem
    endereco geocodificado. `None` significa "sem dado" -- funcoes que
    precisam de distancia (ex.: `vulnerabilidade.menor_distancia_km`) levantam
    erro claro se chamadas com um candidato sem localizacoes, em vez de
    silenciosamente inventar uma distancia.
    """

    crianca_id: str
    score: Score
    preferencias: tuple = ()          # programa_id, da mais desejada para a menos
    localizacoes: Optional[tuple[Localizacao, Localizacao]] = None
    data_criacao: datetime = SEM_DATA
    ipl_id: Optional[int] = None
    ano: Optional[int] = None

    def __post_init__(self) -> None:
        if self.localizacoes is not None and len(self.localizacoes) != 2:
            raise ValueError(
                f"localizacoes precisa ter exatamente 2 (ou None), recebeu "
                f"{len(self.localizacoes)}"
            )

    def rank_da_preferencia(self, programa_id: Optional[str]) -> Optional[int]:
        """0 para a primeira opcao. None se o programa nao esta na lista."""
        if programa_id is None:
            return None
        try:
            return self.preferencias.index(programa_id)
        except ValueError:
            return None

    def prefere(self, programa_id: str, ao_inves_de: Optional[str]) -> bool:
        """True se `programa_id` e estritamente melhor que a alocacao atual."""
        novo = self.rank_da_preferencia(programa_id)
        if novo is None:
            return False
        atual = self.rank_da_preferencia(ao_inves_de)
        return atual is None or novo < atual


@dataclass(frozen=True)
class Programa:
    """Uma vaga-tipo: (ano, unidade, grupamento, horario) e sua capacidade.

    Classe unica -- ate pouco atras `vulnerabilidade.py` tinha o seu proprio
    `Escola` (identidade + localizacao + vagas), a mesma nocao de "onde a
    vaga existe" representada de outro jeito. `localizacao` e opcional
    (`None` por padrao, "sem geocodificacao ainda"): so
    `vulnerabilidade.menor_distancia_km` usa esse campo -- o motor da regua
    oficial nunca olha para ele.

    `vagas` default 0 de proposito, igual ao `Escola` que unificou aqui:
    "nao informei capacidade" deve significar "ninguem admitido ainda",
    nunca "capacidade ilimitada".
    """

    programa_id: str
    vagas: int = 0
    ano: Optional[int] = None
    unidade: Optional[str] = None
    nome_unidade: Optional[str] = None
    grupamento: Optional[str] = None
    horario: Optional[str] = None
    localizacao: Optional[Localizacao] = None

    def __post_init__(self) -> None:
        if self.vagas < 0:
            raise ValueError(f"vagas nao pode ser negativo: {self.vagas!r}")


@dataclass(frozen=True)
class ProgramaAlocado:
    """Programa + o resultado da classificacao. E o objeto que
    `nota_corte_atual` e `posicao_na_fila` recebem."""

    programa: Programa
    admitidos: tuple = ()  # Candidato, do melhor classificado ao pior
    fila: tuple = ()       # Candidato, ordenados por prioridade

    @property
    def programa_id(self) -> str:
        return self.programa.programa_id

    @property
    def vagas(self) -> int:
        return self.programa.vagas

    @property
    def vagas_ocupadas(self) -> int:
        return len(self.admitidos)

    @property
    def vagas_livres(self) -> int:
        return max(0, self.vagas - self.vagas_ocupadas)

    @property
    def lotado(self) -> bool:
        return self.vagas_ocupadas >= self.vagas


# ---------------------------------------------------------------------------
# Alocacao (saida do Deferred Acceptance)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Alocacao:
    """Snapshot completo de uma classificacao."""

    candidatos: Mapping[str, Candidato]          # crianca_id -> Candidato
    programas: Mapping[str, ProgramaAlocado]     # programa_id -> ProgramaAlocado
    matches: Mapping[str, str]                   # crianca_id -> programa_id
    rodadas: int = 0

    def programa(self, programa_id: str) -> ProgramaAlocado:
        try:
            return self.programas[programa_id]
        except KeyError:
            raise KeyError(f"programa desconhecido: {programa_id!r}") from None

    def alocacao_de(self, crianca_id: str) -> Optional[str]:
        return self.matches.get(crianca_id)

    @property
    def nao_alocados(self) -> tuple:
        return tuple(sorted(c for c in self.candidatos if c not in self.matches))


# ---------------------------------------------------------------------------
# Reclassificacao
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Movimento:
    """Uma crianca que mudou de lugar entre duas alocacoes."""

    crianca_id: str
    de: Optional[str]                    # programa_id anterior (None = fora)
    para: Optional[str]                  # programa_id novo (None = saiu)
    score: int
    de_opcao: Optional[int] = None       # 1-based, como na coluna `opcao`
    para_opcao: Optional[int] = None
    posicao_na_fila_anterior: Optional[int] = None

    @property
    def subiu(self) -> bool:
        if self.para is None:
            return False
        if self.de is None:
            return True
        return (self.para_opcao or 0) < (self.de_opcao or 0)


@dataclass(frozen=True)
class Reclassificacao:
    """Antes/depois de `reclassificar`."""

    alocacao: Alocacao                   # a nova
    anterior: Alocacao
    subiram: tuple = ()                  # Movimento
    sairam: tuple = ()                   # Movimento -- perderam a vaga
    desistiram: tuple = ()               # Movimento de quem recusou a propria vaga
    # `desceram` sao TERCEIROS que pioraram. So pode encher quando a capacidade
    # cai ou entra candidato novo -- serve de sentinela para bug no motor.
    desceram: tuple = ()

    @property
    def notas_de_corte_alteradas(self) -> dict:
        """programa_id -> (corte_antes, corte_depois), so onde mudou."""
        from .fila import nota_corte_atual

        mudancas: dict = {}
        for programa_id, novo in self.alocacao.programas.items():
            velho = self.anterior.programas.get(programa_id)
            antes = nota_corte_atual(velho) if velho is not None else None
            depois = nota_corte_atual(novo)
            if antes != depois:
                mudancas[programa_id] = (antes, depois)
        return mudancas


# ---------------------------------------------------------------------------
# Prioridade
# ---------------------------------------------------------------------------
def chave_de_prioridade(candidato: Candidato) -> tuple:
    """Ordem de classificacao do lado do programa. Menor tupla = melhor colocado.

    1. score decrescente
    2. criterios de desempate na ordem de `DESEMPATE_ORDEM`
    3. inscricao mais antiga
    4. crianca_id -- so para tornar o resultado deterministico
    """
    desempates = tuple(
        0 if perg_id in candidato.score.desempates else 1
        for perg_id in DESEMPATE_ORDEM
    )
    return (
        -candidato.score.total,
        *desempates,
        candidato.data_criacao or SEM_DATA,
        candidato.crianca_id,
    )
