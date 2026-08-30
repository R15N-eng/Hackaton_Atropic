"""Score por vulnerabilidade + proximidade -- linha de trabalho separada da
regua oficial da SME (`score.py`, que usa a Query C e responde por `Score`,
o tipo consumido pelo Deferred Acceptance).

Aqui o objetivo e outro: medir modularmente vulnerabilidade (sem peso de
regua) e distancia ate o programa, uma peca por vez, para depois decidir --
via um contrato externo ainda nao definido -- se/como isso se combina com o
score oficial no ranking do Deferred Acceptance.

`Candidato` e `Programa` sao os mesmos tipos usados no motor da regua
(`modelos.py`). Ate pouco atras este modulo tinha os seus proprios -- um
`Candidato` com um dict de flags guardando a mesma informacao que `Score` ja
guarda (ver `pontuacao_vulnerabilidade` abaixo), e um `Escola` (identidade +
localizacao + vagas) representando a mesma nocao de "onde a vaga existe" que
`Programa` ja representa. `Programa.localizacao` e o unico campo que so esta
linha usa -- o motor da regua oficial nunca olha para ele.

Ranquear por `Programa` (nao por escola inteira) tambem é mais correto: vagas
sao por grupamento/turno, nao por predio -- a mesma unidade tem fila separada
para Bercario Integral e Maternal II Parcial.

`calcular_score` daqui devolve so o numero (`float`), como pedido -- sem
detalhe, sem desempate. Pesos e alcance sao parametros com default, nao um
contrato fixo; e o proximo passo trocar por configuracao externa.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from .localizacao import distancia_km
from .modelos import Candidato, Programa  # re-exportados -- imports existentes continuam validos


def pontuacao_vulnerabilidade(candidato: Candidato) -> float:
    """Conta quantas perguntas de vulnerabilidade a familia respondeu 'Sim',
    sem peso -- cada uma vale 1 ponto aqui, diferente de `candidato.score.total`
    (que usa o peso da regua da SME).

    Deriva do `Score`, nao guarda um dict proprio: `score.detalhe` tem as
    perguntas que pontuaram na regua, `score.desempates` as marcadas so como
    criterio (0 ponto na regua). A uniao das duas e toda pergunta de
    vulnerabilidade que a familia confirmou -- e o que se soma aqui, contando
    perguntas, nao pontos.
    """
    return float(len(candidato.score.detalhe) + len(candidato.score.desempates))


def menor_distancia_km(candidato: Candidato, programa: Programa) -> float:
    """A menor das duas distancias candidato-programa.

    E essa que entra na pontuacao: usamos a localizacao que favorece a
    crianca, nao uma media -- ter um endereco mais proximo do programa conta a
    favor dela.

    Levanta erro se o candidato nao tiver `localizacoes`, ou o programa nao
    tiver `localizacao` -- endereco ainda nao geocodificado dos dois lados.
    Nao ha como calcular distancia sem eles, e inventar uma (ex.: 0 ou
    infinito) esconderia o problema em vez de avisar.
    """
    if candidato.localizacoes is None:
        raise ValueError(
            f"{candidato.crianca_id!r} sem localizacoes -- nao e possivel "
            "calcular distancia"
        )
    if programa.localizacao is None:
        raise ValueError(
            f"{programa.programa_id!r} sem localizacao -- nao e possivel "
            "calcular distancia"
        )
    return min(distancia_km(loc, programa.localizacao) for loc in candidato.localizacoes)


def pontuacao_distancia(distancia: float, *, alcance_km: float = 5.0) -> float:
    """Pontuacao de proximidade: 1.0 na porta do programa, cai linearmente e
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
    programa: Programa,
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
) -> float:
    """Pontuacao da crianca para este programa: soma ponderada de
    vulnerabilidade e proximidade.

        score = peso_vulnerabilidade * vulnerabilidade
              + peso_distancia       * pontuacao_distancia(menor_distancia)

    Retorna so o numero -- sem Score, sem detalhe, sem desempate. Os pesos e o
    alcance sao parametros abertos: nao ha, por ora, um contrato externo que
    fixe os valores oficiais.
    """
    vulnerabilidade = pontuacao_vulnerabilidade(candidato)
    distancia = menor_distancia_km(candidato, programa)
    proximidade = pontuacao_distancia(distancia, alcance_km=alcance_km)
    return peso_vulnerabilidade * vulnerabilidade + peso_distancia * proximidade


# ---------------------------------------------------------------------------
# Classificacao por programa
# ---------------------------------------------------------------------------
# Espelha modelos.Programa/ProgramaAlocado: o Programa sabe sua capacidade
# (`vagas`), mas nao sabe quem se candidatou a ele. Quem cruza os dois e este
# tipo companheiro, montado por uma funcao pura -- mesmo padrao usado pelo
# Deferred Acceptance no motor principal.
@dataclass(frozen=True)
class ProgramaClassificado:
    """Um Programa e os candidatos que o listaram, ja ordenados pelo score de
    vulnerabilidade + distancia (melhor primeiro), com o score de cada um
    guardado em `scores` (crianca_id -> score usado para ordenar).

    Guardar o score em vez de so a ordem evita recalcula-lo -- e faria isso
    com os pesos errados se alguem chamar `nota_corte_atual` com pesos
    diferentes dos usados aqui. As primeiras `programa.vagas` posicoes sao
    `admitidos`; o resto e `fila`. Ainda nao ha o conceito de "quem aceitaria
    a vaga" que a fila do motor principal tem (isso exigiria um candidato
    conhecer preferencias entre varios programas, que nao existe nesta linha)
    -- aqui fila e simplesmente "listou e nao teve vaga".
    """

    programa: Programa
    candidatos: tuple[Candidato, ...]           # TODOS que listaram, ordenados
    scores: Mapping[str, float]                 # crianca_id -> score na ordenacao

    @property
    def programa_id(self) -> str:
        return self.programa.programa_id

    @property
    def vagas(self) -> int:
        return self.programa.vagas

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

        Caso de borda intencional: programa com `vagas=0` e `lotado=True`
        mesmo com `admitidos=()` -- 0 vagas ocupando 0 de capacidade e "sem
        vaga livre", nao "com vaga livre". Mesma regra de
        `modelos.ProgramaAlocado`.
        """
        return self.vagas_ocupadas >= self.vagas


def classificar_programa(
    programa: Programa,
    candidatos: Iterable[Candidato],
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
    semente: Optional[int] = None,
) -> ProgramaClassificado:
    """Ordena os candidatos que listaram `programa` pelo score de
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
            programa,
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
    return ProgramaClassificado(
        programa=programa,
        candidatos=tuple(candidato for candidato, _ in pares),
        scores=scores,
    )


def adicionar_candidato(
    programa_classificado: ProgramaClassificado,
    candidato: Candidato,
    *,
    peso_vulnerabilidade: float = 1.0,
    peso_distancia: float = 1.0,
    alcance_km: float = 5.0,
    semente: Optional[int] = None,
) -> ProgramaClassificado:
    """Coloca um candidato na classificacao existente, na posicao que o score
    dele determina -- refaz o ranking com ele incluido.

    Por que refazer em vez de so calcular a posicao dele e inserir: o sorteio
    de empate decide a ordem so entre quem esta sendo sorteado junto, e nao
    guardamos o sorteio de cada candidato que ja estava na lista. Se o novo
    candidato empatar com algum deles, a unica forma correta de decidir e
    resortear o grupo empatado -- nao ha sorteio antigo para reaproveitar.
    No tamanho tipico de um programa (nao milhoes de candidatos), refazer o
    ranking e barato; a alternativa (achar a posicao e so inserir) economiza
    tempo mas so funciona tratando empate como caso especial, o que abre
    espaco para o mesmo tipo de bug sutil que ja vimos em `reclassificar`.

    Falha se `candidato.crianca_id` ja estiver na classificacao -- mesma
    crianca nao pode aparecer duas vezes na lista de um programa.
    """
    if any(
        c.crianca_id == candidato.crianca_id for c in programa_classificado.candidatos
    ):
        raise ValueError(
            f"{candidato.crianca_id!r} ja esta na classificacao de "
            f"{programa_classificado.programa_id!r}"
        )
    return classificar_programa(
        programa_classificado.programa,
        (*programa_classificado.candidatos, candidato),
        peso_vulnerabilidade=peso_vulnerabilidade,
        peso_distancia=peso_distancia,
        alcance_km=alcance_km,
        semente=semente,
    )


def remover_candidato(
    programa_classificado: ProgramaClassificado, crianca_id: str
) -> ProgramaClassificado:
    """Tira uma crianca da classificacao (desistencia, saida do processo).

    Diferente de `adicionar_candidato`, remover nao precisa resortear nada: a
    ordem relativa de quem fica parado nao muda quando alguem sai -- so filtra.

    Falha se `crianca_id` nao estiver na classificacao.
    """
    restantes = tuple(
        c for c in programa_classificado.candidatos if c.crianca_id != crianca_id
    )
    if len(restantes) == len(programa_classificado.candidatos):
        raise KeyError(
            f"{crianca_id!r} nao esta na classificacao de "
            f"{programa_classificado.programa_id!r}"
        )
    scores = {
        cid: score
        for cid, score in programa_classificado.scores.items()
        if cid != crianca_id
    }
    return ProgramaClassificado(
        programa=programa_classificado.programa, candidatos=restantes, scores=scores
    )


def nota_corte_atual(programa_classificado: ProgramaClassificado) -> Optional[float]:
    """Menor score entre os admitidos (as primeiras `programa.vagas` posicoes).

    None quando ninguem foi admitido -- vaga aberta, sem corte.

    Cuidado ao interpretar: se `vagas_livres > 0`, o programa nao esgotou a
    capacidade e este numero e so o menor score de quem entrou, nao uma
    barreira de entrada -- mesma ressalva do `nota_corte_atual` da regua
    oficial (ver `fila.py`). Confira `programa_classificado.lotado` antes de
    tratar este valor como corte real.
    """
    if not programa_classificado.admitidos:
        return None
    return min(
        programa_classificado.scores[c.crianca_id]
        for c in programa_classificado.admitidos
    )


def posicao_na_fila(
    crianca_id: str, programa_classificado: ProgramaClassificado
) -> Optional[int]:
    """Posicao 1-based do candidato na classificacao do programa.

    None se ele nao esta na lista -- ou nunca listou este programa, ou nao
    foi incluido em `classificar_programa`.
    """
    for posicao, candidato in enumerate(programa_classificado.candidatos, start=1):
        if candidato.crianca_id == crianca_id:
            return posicao
    return None
