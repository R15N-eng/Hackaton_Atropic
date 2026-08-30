"""Score por vulnerabilidade + proximidade -- linha de trabalho separada da
regua oficial da SME (`score.py`, que usa a Query C e responde por `Score`,
o tipo consumido pelo Deferred Acceptance).

Aqui o objetivo e outro: media modularmente vulnerabilidade (variaveis 0/1,
sem peso de régua) e distancia ate a escola, uma peca por vez, para depois
decidir -- via um contrato externo ainda nao definido -- se/como isso se
combina com o score oficial. Por isso os tipos `Candidato` e `Escola` deste
modulo sao proprios, distintos de `modelos.Candidato`/`modelos.Programa`: nao
tem `preferencias`, `data_criacao` nem vagas, so o que a conta de hoje precisa.

`calcular_score` daqui devolve so o numero (`float`), como pedido -- sem
detalhe, sem desempate. Pesos e alcance sao parametros com default, nao um
contrato fixo; e o proximo passo trocar por configuracao externa.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from .localizacao import Localizacao, distancia_km


@dataclass(frozen=True)
class Candidato:
    """Vista da crianca para este calculo: flags de vulnerabilidade (0/1) e
    as DUAS localizacoes candidatas (ex.: endereco do responsavel 1 e do
    responsavel 2) -- usa-se a que estiver mais perto da escola.
    """

    crianca_id: str
    vulnerabilidade: Mapping[str, int]          # nome do criterio -> 0 ou 1
    localizacoes: tuple[Localizacao, Localizacao]

    def __post_init__(self) -> None:
        if len(self.localizacoes) != 2:
            raise ValueError(
                f"Candidato precisa de exatamente 2 localizacoes, recebeu "
                f"{len(self.localizacoes)}"
            )
        invalidas = {k: v for k, v in self.vulnerabilidade.items() if v not in (0, 1)}
        if invalidas:
            raise ValueError(f"vulnerabilidade so aceita 0/1: {invalidas!r}")


@dataclass(frozen=True)
class Escola:
    """A escola: identidade, localizacao e capacidade.

    `vagas` default 0 de proposito -- "nao informei capacidade" deve significar
    "ninguem admitido ainda", nunca "capacidade ilimitada". So importa para
    `classificar_escola`/`nota_corte_atual`; quem so quer `calcular_score` pode
    ignorar e deixar o default.
    """

    escola_id: str
    localizacao: Localizacao
    vagas: int = 0

    def __post_init__(self) -> None:
        if self.vagas < 0:
            raise ValueError(f"vagas nao pode ser negativo: {self.vagas!r}")


def pontuacao_vulnerabilidade(candidato: Candidato) -> float:
    """Soma das flags de vulnerabilidade (0/1). Sem peso -- cada criterio
    marcado vale 1 ponto, diferente da regua da SME em `score.py`."""
    return float(sum(candidato.vulnerabilidade.values()))


def menor_distancia_km(candidato: Candidato, escola: Escola) -> float:
    """A menor das duas distancias candidato-escola.

    E essa que entra na pontuacao: usamos a localizacao que favorece a
    crianca, nao uma media -- ter um endereco mais proximo da escola conta a
    favor dela.
    """
    return min(distancia_km(loc, escola.localizacao) for loc in candidato.localizacoes)


def pontuacao_distancia(distancia: float, *, alcance_km: float = 5.0) -> float:
    """Pontuacao de proximidade: 1.0 na porta da escola, cai linearmente e
    satura em 0.0 a partir de `alcance_km`.

    E a curva mais simples que cumpre "mais perto pontua mais" sem inventar
    parametro extra. `alcance_km` e o raio a partir do qual a distancia deixa
    de fazer diferenca -- valor provisorio, deve vir de configuracao real
    (ex.: raio de abrangencia da unidade) quando o contrato externo definir.
    """
    if distancia < 0:
        raise ValueError(f"distancia nao pode ser negativa: {distancia!r}")
    if alcance_km <= 0:
        raise ValueError(f"alcance_km precisa ser positivo: {alcance_km!r}")
    return max(0.0, 1.0 - distancia / alcance_km)


def calcular_score(
    candidato: Candidato,
    escola: Escola,
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
) -> float:
    """Pontuacao da crianca para esta escola: soma ponderada de vulnerabilidade
    e proximidade.

        score = peso_vulnerabilidade * vulnerabilidade
              + peso_distancia       * pontuacao_distancia(menor_distancia)

    Retorna so o numero -- sem Score, sem detalhe, sem desempate. Os pesos e o
    alcance sao parametros abertos: nao ha, por ora, um contrato externo que
    fixe os valores oficiais.
    """
    vulnerabilidade = pontuacao_vulnerabilidade(candidato)
    distancia = menor_distancia_km(candidato, escola)
    proximidade = pontuacao_distancia(distancia, alcance_km=alcance_km)
    return peso_vulnerabilidade * vulnerabilidade + peso_distancia * proximidade


# ---------------------------------------------------------------------------
# Classificacao por escola
# ---------------------------------------------------------------------------
# Espelha modelos.Programa/ProgramaAlocado: a Escola sabe sua capacidade
# (`vagas`), mas nao sabe quem se candidatou a ela. Quem cruza os dois e este
# tipo companheiro, montado por uma funcao pura -- mesmo padrao usado pelo
# Deferred Acceptance no motor principal.
@dataclass(frozen=True)
class EscolaClassificada:
    """Uma Escola e os candidatos que a listaram, ja ordenados pelo score de
    vulnerabilidade + distancia (melhor primeiro), com o score de cada um
    guardado em `scores` (crianca_id -> score usado para ordenar).

    Guardar o score em vez de so a ordem evita recalcula-lo -- e faria isso
    com os pesos errados se alguem chamar `nota_corte_atual` com pesos
    diferentes dos usados aqui. As primeiras `escola.vagas` posicoes sao
    `admitidos`; o resto e `fila`. Ainda nao ha o conceito de "quem aceitaria
    a vaga" que a fila do motor principal tem (isso exigiria um candidato
    conhecer preferencias entre varias escolas, que nao existe nesta linha) --
    aqui fila e simplesmente "listou e nao teve vaga".
    """

    escola: Escola
    candidatos: tuple[Candidato, ...]           # TODOS que listaram, ordenados
    scores: Mapping[str, float]                 # crianca_id -> score na ordenacao

    @property
    def escola_id(self) -> str:
        return self.escola.escola_id

    @property
    def vagas(self) -> int:
        return self.escola.vagas

    @property
    def admitidos(self) -> tuple[Candidato, ...]:
        return self.candidatos[: self.vagas]

    @property
    def fila(self) -> tuple[Candidato, ...]:
        return self.candidatos[self.vagas :]

    @property
    def vagas_ocupadas(self) -> int:
        return len(self.admitidos)

    @property
    def vagas_livres(self) -> int:
        return max(0, self.vagas - self.vagas_ocupadas)

    @property
    def lotado(self) -> bool:
        """True quando nao ha mais vaga livre.

        Caso de borda intencional: escola com `vagas=0` e `lotado=True` mesmo
        com `admitidos=()` -- 0 vagas ocupando 0 de capacidade e "sem vaga
        livre", nao "com vaga livre". Mesma regra de `modelos.ProgramaAlocado`.
        """
        return self.vagas_ocupadas >= self.vagas


def classificar_escola(
    escola: Escola,
    candidatos: Iterable[Candidato],
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
    semente: Optional[int] = None,
) -> EscolaClassificada:
    """Ordena os candidatos que listaram `escola` pelo score de
    vulnerabilidade + distancia -- maior score primeiro.

    Empate (mesmo score) e resolvido por sorteio -- esta linha de trabalho
    ainda nao tem um criterio de desempate proprio como o da regua oficial
    (ver `modelos.chave_de_prioridade`); se ela deveria valer aqui tambem e
    parte do contrato externo ainda pendente.

    `semente` fixa o sorteio: mesma lista + mesma semente sempre devolve a
    mesma ordem, o que permite testar a funcao. Sem `semente`, cada chamada
    pode sortear uma ordem diferente entre os empatados -- ela deixa de ser
    determinística de proposito, entao nao chame sem semente onde precisar
    reproduzir o resultado (ex.: comparar antes/depois de uma reclassificacao).

    Falha se a mesma `crianca_id` aparecer duas vezes -- mesma regra do motor
    principal (`deferred_acceptance`): uma crianca, uma entrada na lista.
    """
    candidatos = list(candidatos)
    vistas: set = set()
    for candidato in candidatos:
        if candidato.crianca_id in vistas:
            raise ValueError(f"crianca_id duplicado: {candidato.crianca_id!r}")
        vistas.add(candidato.crianca_id)

    sorteio = random.Random(semente)
    scores = {
        candidato.crianca_id: calcular_score(
            candidato,
            escola,
            peso_vulnerabilidade=peso_vulnerabilidade,
            peso_distancia=peso_distancia,
            alcance_km=alcance_km,
        )
        for candidato in candidatos
    }
    pares = [
        (
            candidato,
            (
                -scores[candidato.crianca_id],
                sorteio.random(),  # desempate: um sorteio por candidato, nesta ordem
            ),
        )
        for candidato in candidatos
    ]
    pares.sort(key=lambda par: par[1])
    return EscolaClassificada(
        escola=escola,
        candidatos=tuple(candidato for candidato, _ in pares),
        scores=scores,
    )


def adicionar_candidato(
    escola_classificada: EscolaClassificada,
    candidato: Candidato,
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
    semente: Optional[int] = None,
) -> EscolaClassificada:
    """Coloca um candidato na classificacao existente, na posicao que o score
    dele determina -- refaz o ranking com ele incluido.

    Por que refazer em vez de so calcular a posicao dele e inserir: o sorteio
    de empate decide a ordem so entre quem esta sendo sorteado junto, e nao
    guardamos o sorteio de cada candidato que ja estava na lista. Se o novo
    candidato empatar com algum deles, a unica forma correta de decidir e
    resortear o grupo empatado -- nao ha sorteio antigo para reaproveitar.
    No tamanho tipico de uma escola (nao milhoes de candidatos), refazer o
    ranking e barato; a alternativa (achar a posicao e so inserir) economiza
    tempo mas so funciona tratando empate como caso especial, o que abre
    espaco para o mesmo tipo de bug sutil que ja vimos em `reclassificar`.

    Falha se `candidato.crianca_id` ja estiver na classificacao -- mesma
    crianca nao pode aparecer duas vezes na lista de uma escola.
    """
    if any(
        c.crianca_id == candidato.crianca_id for c in escola_classificada.candidatos
    ):
        raise ValueError(
            f"{candidato.crianca_id!r} ja esta na classificacao de "
            f"{escola_classificada.escola_id!r}"
        )
    return classificar_escola(
        escola_classificada.escola,
        (*escola_classificada.candidatos, candidato),
        peso_vulnerabilidade=peso_vulnerabilidade,
        peso_distancia=peso_distancia,
        alcance_km=alcance_km,
        semente=semente,
    )


def remover_candidato(
    escola_classificada: EscolaClassificada, crianca_id: str
) -> EscolaClassificada:
    """Tira uma crianca da classificacao (desistencia, saida do processo).

    Diferente de `adicionar_candidato`, remover nao precisa resortear nada: a
    ordem relativa de quem fica parado nao muda quando alguem sai -- so filtra.

    Falha se `crianca_id` nao estiver na classificacao.
    """
    restantes = tuple(
        c for c in escola_classificada.candidatos if c.crianca_id != crianca_id
    )
    if len(restantes) == len(escola_classificada.candidatos):
        raise KeyError(
            f"{crianca_id!r} nao esta na classificacao de "
            f"{escola_classificada.escola_id!r}"
        )
    scores = {
        cid: score
        for cid, score in escola_classificada.scores.items()
        if cid != crianca_id
    }
    return EscolaClassificada(
        escola=escola_classificada.escola, candidatos=restantes, scores=scores
    )


def nota_corte_atual(escola_classificada: EscolaClassificada) -> Optional[float]:
    """Menor score entre os admitidos (as primeiras `escola.vagas` posicoes).

    None quando ninguem foi admitido -- vaga aberta, sem corte.

    Cuidado ao interpretar: se `vagas_livres > 0`, a escola nao esgotou a
    capacidade e este numero e so o menor score de quem entrou, nao uma
    barreira de entrada -- mesma ressalva do `nota_corte_atual` da regua
    oficial (ver `fila.py`). Confira `escola_classificada.lotado` antes de
    tratar este valor como corte real.
    """
    if not escola_classificada.admitidos:
        return None
    return min(
        escola_classificada.scores[c.crianca_id]
        for c in escola_classificada.admitidos
    )


def posicao_na_fila(
    crianca_id: str, escola_classificada: EscolaClassificada
) -> Optional[int]:
    """Posicao 1-based do candidato na classificacao da escola.

    None se ele nao esta na lista -- ou nunca listou esta escola, ou nao foi
    incluido em `classificar_escola`.
    """
    for posicao, candidato in enumerate(escola_classificada.candidatos, start=1):
        if candidato.crianca_id == crianca_id:
            return posicao
    return None
