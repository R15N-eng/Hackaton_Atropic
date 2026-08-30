"""Motor de rodadas do processo -- ciclo de classificacao com pontuacao por
vulnerabilidade + distancia (`vulnerabilidade.calcular_score`), diferente do
`deferred_acceptance.py` da regua oficial (que usa `Score.total`, uma
prioridade IGUAL em qualquer programa, porque nao depende de distancia).

Cuidado com o nome: "rodada" aqui e o ciclo do processo (ex.: 5 dias de
inscricao, fecha, quem entrou e notificado, quem nao entrou vai pra rodada
seguinte com preferencias novas) -- NAO e a mesma coisa que `Alocacao.rodadas`
ou o `max_rodadas` de `deferred_acceptance`, que contam iteracoes internas do
algoritmo de propor-e-rejeitar dentro de uma UNICA chamada.

O que este modulo NAO faz: decidir quando abre/fecha uma rodada (calendario),
notificar quem foi classificado (WhatsApp), ou guardar estado entre chamadas.
Cada rodada e uma chamada pura; quem orquestra o calendario e quantas rodadas
existem e responsabilidade de quem chama (o backend).

Fluxo de uma rodada:
    1. Candidatos desta rodada = quem sobrou da rodada anterior
       (`Alocacao.nao_alocados`, com preferencias NOVAS) + quem se inscreveu
       hoje. Programas = `programas_para_proxima_rodada(alocacao_anterior)`
       (vagas = vagas_livres), ou a capacidade cheia na rodada 1.
    2. `deferred_acceptance_por_pontuacao(candidatos, programas)` -> Alocacao.
    3. Ao fechar a janela: `alocacao.matches` = quem classificou (notificar);
       `alocacao.nao_alocados` = quem vai pra proxima rodada.
    4. Na ULTIMA rodada, quem ainda sobrar entra em
       `alocar_vagas_remanescentes` -- preenche por proximidade, ignorando a
       lista de preferencias (o objetivo deixa de ser "respeitar a escolha",
       vira "nao deixar vaga vazia").

Exige `Candidato.localizacoes` e `Programa.localizacao` preenchidos -- ainda
None nos dados reais (falta a ponte de geocodificacao, ver README).
"""

from __future__ import annotations

import heapq
import random
from dataclasses import replace
from typing import Callable, Iterable, Mapping, Optional

from .modelos import Alocacao, Candidato, Programa, ProgramaAlocado
from .vulnerabilidade import calcular_score, pontuacao_vulnerabilidade


def programas_para_proxima_rodada(alocacao: Alocacao) -> tuple[Programa, ...]:
    """Os mesmos `Programa` da rodada que fechou, com `vagas` = vagas_livres.

    Quem ja foi classificado nao compete de novo -- so a capacidade que
    sobrou em cada programa entra na proxima rodada.
    """
    return tuple(
        replace(p.programa, vagas=p.vagas_livres) for p in alocacao.programas.values()
    )


def deferred_acceptance_por_pontuacao(
    candidatos: Iterable[Candidato],
    programas: Iterable[Programa],
    *,
    pontuacao: Callable[[Candidato, Programa], float] = calcular_score,
    semente: Optional[int] = None,
    max_iteracoes: Optional[int] = None,
) -> Alocacao:
    """Deferred Acceptance com prioridade por PAR (candidato, programa), nao
    por candidato so -- necessario porque a pontuacao (vulnerabilidade +
    distancia) muda de programa para programa, diferente do score da regua.

    Mesmo algoritmo de `deferred_acceptance.deferred_acceptance` (criancas
    propoem, programa reteem os melhores e devolve o excedente), mas sem o
    atalho do rank global: como a pontuacao depende de qual programa esta
    sendo disputado, cada proposta e comparada com a pontuacao calculada
    naquele momento, para aquele par.

    Empate (mesma pontuacao) e resolvido por sorteio -- mesma convencao de
    `vulnerabilidade.classificar_programa`. `semente` fixa o sorteio para
    reproduzir o resultado; sem ela, cada chamada pode sortear diferente.

    `pontuacao` e plugavel: o default e `vulnerabilidade.calcular_score` (com
    os pesos default dela). Passe uma `functools.partial` para outros pesos,
    ou uma funcao propria.
    """
    por_id: dict = {}
    for programa in programas:
        if programa.programa_id in por_id:
            raise ValueError(f"programa_id duplicado: {programa.programa_id!r}")
        por_id[programa.programa_id] = programa

    inscritos: dict = {}
    for candidato in candidatos:
        if candidato.crianca_id in inscritos:
            raise ValueError(f"crianca_id duplicado: {candidato.crianca_id!r}")
        inscritos[candidato.crianca_id] = candidato

    sorteio = random.Random(semente)
    retidos: dict = {pid: [] for pid in por_id}
    proxima: dict = {cid: 0 for cid in inscritos}

    pendentes = list(inscritos.keys())
    iteracoes = 0
    teto = max_iteracoes if max_iteracoes is not None else len(inscritos) + 2

    while pendentes:
        iteracoes += 1
        if iteracoes > teto:
            raise RuntimeError("DA nao convergiu -- verifique as preferencias/vagas")

        rejeitados: list = []
        for crianca_id in pendentes:
            candidato = inscritos[crianca_id]
            programa_id = _proxima_opcao_valida(candidato, proxima, crianca_id, por_id)
            if programa_id is None:
                continue  # esgotou as opcoes: fica sem vaga

            programa = por_id[programa_id]
            chave = (pontuacao(candidato, programa), sorteio.random(), crianca_id)
            grupo = retidos[programa_id]
            heapq.heappush(grupo, chave)
            if len(grupo) > programa.vagas:
                pior = heapq.heappop(grupo)
                rejeitados.append(pior[2])

        pendentes = rejeitados

    admitidos_por_programa = {
        programa_id: [item[2] for item in sorted(grupo, key=lambda item: (-item[0], item[1]))]
        for programa_id, grupo in retidos.items()
    }

    matches: dict = {}
    for programa_id, grupo in admitidos_por_programa.items():
        for crianca_id in grupo:
            matches[crianca_id] = programa_id

    filas = _montar_filas_por_pontuacao(inscritos, matches, por_id, pontuacao, sorteio)

    programas_alocados = {}
    for programa_id, programa in por_id.items():
        grupo = admitidos_por_programa.get(programa_id, [])
        espera = filas.get(programa_id, ())
        scores = {
            cid: pontuacao(inscritos[cid], programa) for cid in (*grupo, *espera)
        }
        programas_alocados[programa_id] = ProgramaAlocado(
            programa=programa,
            admitidos=tuple(inscritos[cid] for cid in grupo),
            fila=tuple(inscritos[cid] for cid in espera),
            scores=scores,
        )

    return Alocacao(
        candidatos=inscritos,
        programas=programas_alocados,
        matches=matches,
        rodadas=iteracoes,
    )


def _proxima_opcao_valida(
    candidato: Candidato,
    proxima: dict,
    crianca_id: str,
    por_id: Mapping[str, Programa],
) -> Optional[str]:
    indice = proxima[crianca_id]
    preferencias = candidato.preferencias
    while indice < len(preferencias):
        programa_id = preferencias[indice]
        indice += 1
        if programa_id in por_id:
            proxima[crianca_id] = indice
            return programa_id
    proxima[crianca_id] = indice
    return None


def _montar_filas_por_pontuacao(
    candidatos: Mapping[str, Candidato],
    matches: Mapping[str, str],
    por_id: Mapping[str, Programa],
    pontuacao: Callable[[Candidato, Programa], float],
    sorteio: random.Random,
) -> dict:
    """Fila de espera de cada programa, ordenada pela pontuacao NAQUELE
    programa (nao um rank global -- aqui cada programa tem sua propria
    ordem, dado que a pontuacao depende do par)."""
    filas: dict = {}
    for crianca_id, candidato in candidatos.items():
        atual = matches.get(crianca_id)
        limite = (
            len(candidato.preferencias)
            if atual is None
            else candidato.rank_da_preferencia(atual)
        )
        for programa_id in candidato.preferencias[:limite]:
            if programa_id in por_id:
                filas.setdefault(programa_id, []).append(crianca_id)

    for programa_id, espera in filas.items():
        programa = por_id[programa_id]
        espera.sort(
            key=lambda cid: (-pontuacao(candidatos[cid], programa), sorteio.random())
        )
    return filas


def nota_corte_atual(programa_alocado: ProgramaAlocado) -> Optional[float]:
    """Menor pontuacao entre os admitidos, NESTE motor (por par candidato-
    programa) -- nao confundir com `fila.nota_corte_atual`, que le
    `Score.total` da regua. Le `programa_alocado.scores`, guardado no momento
    da classificacao; nao recalcula (evita o corte "mentir" se alguem chamar
    com uma `pontuacao` diferente da usada para montar a alocacao).

    None quando ninguem foi admitido. Levanta `ValueError` se
    `programa_alocado.scores` for `None` -- sinal de que veio do motor da
    regua (`deferred_acceptance.py`), nao deste modulo.
    """
    if programa_alocado.scores is None:
        raise ValueError(
            "ProgramaAlocado sem scores -- veio de deferred_acceptance.py "
            "(regua), nao de rodadas.deferred_acceptance_por_pontuacao"
        )
    if not programa_alocado.admitidos:
        return None
    return min(
        programa_alocado.scores[c.crianca_id] for c in programa_alocado.admitidos
    )


def posicao_na_fila(crianca_id: str, programa_alocado: ProgramaAlocado) -> Optional[int]:
    """Posicao 1-based na fila deste programa, neste motor. None se a
    crianca nao esta na fila (admitida, nunca listou, ou prefere onde esta)."""
    for posicao, candidato in enumerate(programa_alocado.fila, start=1):
        if candidato.crianca_id == crianca_id:
            return posicao
    return None


def alocar_vagas_remanescentes(
    candidatos: Iterable[Candidato],
    programas: Iterable[Programa],
    *,
    semente: Optional[int] = None,
) -> dict:
    """Ultima rodada: aloca cada candidato remanescente ao programa com vaga
    mais proximo, IGNORANDO `Candidato.preferencias` -- o objetivo aqui e
    preencher toda vaga vazia, nao respeitar a lista de escolha da familia
    (que ja foi tentada nas rodadas anteriores, sem sucesso).

    Ordem de atendimento: `pontuacao_vulnerabilidade` decrescente (quem tem
    mais criterios de vulnerabilidade e atendido primeiro), empate por
    sorteio. Cada candidato fica com o programa de MENOR distancia entre os
    que ainda tem vaga NO MOMENTO em que ele e atendido -- greedy, sem troca
    depois (nao e um Deferred Acceptance, nao ha estabilidade a garantir
    quando as preferencias sao ignoradas).

    Exige `localizacoes`/`localizacao` preenchidos -- levanta o mesmo erro de
    `vulnerabilidade.menor_distancia_km` se faltar em algum par considerado.

    Retorna `{crianca_id: programa_id}` -- so quem conseguiu vaga aparece.
    Quando a demanda excede a soma das vagas, o restante fica de fora (dict
    nao tem entrada para eles); quem chama decide o que fazer com esses.
    """
    from .vulnerabilidade import menor_distancia_km

    candidatos = list(candidatos)
    programas_por_id = {p.programa_id: p for p in programas}
    vagas_livres = {pid: p.vagas for pid, p in programas_por_id.items()}

    sorteio = random.Random(semente)
    ordem = sorted(
        candidatos,
        key=lambda c: (-pontuacao_vulnerabilidade(c), sorteio.random()),
    )

    alocados: dict = {}
    for candidato in ordem:
        disponiveis = [pid for pid, restante in vagas_livres.items() if restante > 0]
        if not disponiveis:
            break  # nao ha mais vaga em lugar nenhum
        melhor = min(
            disponiveis,
            key=lambda pid: menor_distancia_km(candidato, programas_por_id[pid]),
        )
        alocados[candidato.crianca_id] = melhor
        vagas_livres[melhor] -= 1
    return alocados
