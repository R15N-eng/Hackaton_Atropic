"""Funcao 4 -- reclassificar.

Quando uma vaga muda de mao (desistencia na confirmacao, impossibilidade de
contato, ou a SME mexe na capacidade), roda o Deferred Acceptance de novo sobre o
estado atualizado e diz quem subiu.

Rodar o DA inteiro em vez de "chamar o proximo da fila" nao e desperdicio: uma
desistencia libera uma vaga que pode ser preenchida por alguem que hoje esta
numa opcao pior, e essa pessoa libera a vaga dela, que puxa outra. A cascata e o
resultado que importa, e o DA e o que garante que ela termina num estado estavel.

Pura: nao muta as entradas, devolve `Reclassificacao` com antes e depois.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Iterable, Mapping, Optional

from .deferred_acceptance import deferred_acceptance
from .fila import posicao_na_fila
from .modelos import (
    Alocacao,
    Candidato,
    Movimento,
    Programa,
    Reclassificacao,
    chave_de_prioridade,
)


def reclassificar(
    alocacao: Alocacao,
    *,
    desistencias: Iterable = (),
    saidas: Iterable[str] = (),
    vagas: Optional[Mapping[str, int]] = None,
    delta_vagas: Optional[Mapping[str, int]] = None,
    novos_candidatos: Iterable[Candidato] = (),
    prioridade: Callable[[Candidato], tuple] = chave_de_prioridade,
) -> Reclassificacao:
    """Reclassifica a partir de um snapshot, aplicando o que mudou.

    desistencias: `(crianca_id, programa_id)` ou `crianca_id`. A crianca recusa
        aquele programa especifico -- ele sai da lista de preferencias dela e ela
        volta a concorrer nas outras opcoes. Passando so o `crianca_id`, a recusa
        vale para a alocacao atual dela.
    saidas: `crianca_id` que deixa o processo por inteiro (transferencia, perda
        de prazo). Diferente de desistir de uma opcao.
    vagas: `{programa_id: vagas}` -- capacidade absoluta nova.
    delta_vagas: `{programa_id: +/-n}` -- ajuste relativo. Aplicado depois de
        `vagas`. Capacidade nunca fica negativa.
    novos_candidatos: inscricoes que entraram depois do corte.

    Retorna `Reclassificacao`: nova alocacao, a anterior, e os movimentos
    separados em `subiram`, `sairam`, `desistiram` e `desceram`. `desceram` sao
    terceiros que pioraram -- vazio sempre que a mudanca so libera vaga.
    """
    candidatos, desistentes = _aplicar_desistencias(alocacao, desistencias, saidas)
    for candidato in novos_candidatos:
        if candidato.crianca_id in candidatos:
            raise ValueError(
                f"{candidato.crianca_id!r} ja esta na alocacao -- use `vagas`/"
                "`desistencias` para mexer em quem ja concorre"
            )
        candidatos[candidato.crianca_id] = candidato

    programas = _aplicar_vagas(alocacao, vagas, delta_vagas)

    nova = deferred_acceptance(
        candidatos.values(), programas, prioridade=prioridade
    )
    return _comparar(alocacao, nova, desistentes)


# ---------------------------------------------------------------------------
def _aplicar_desistencias(
    alocacao: Alocacao, desistencias: Iterable, saidas: Iterable[str]
) -> tuple:
    candidatos = dict(alocacao.candidatos)
    desistentes: set = set()

    for item in desistencias:
        if isinstance(item, str):
            crianca_id, programa_id = item, alocacao.alocacao_de(item)
        else:
            crianca_id, programa_id = item

        candidato = candidatos.get(crianca_id)
        if candidato is None:
            raise KeyError(f"crianca fora da alocacao: {crianca_id!r}")
        if programa_id is None:
            # desistiu sem ter vaga: nada a liberar
            continue

        preferencias = tuple(p for p in candidato.preferencias if p != programa_id)
        candidatos[crianca_id] = replace(candidato, preferencias=preferencias)
        desistentes.add(crianca_id)

    for crianca_id in saidas:
        if crianca_id not in candidatos:
            raise KeyError(f"crianca fora da alocacao: {crianca_id!r}")
        del candidatos[crianca_id]

    return candidatos, desistentes


def _aplicar_vagas(
    alocacao: Alocacao,
    vagas: Optional[Mapping[str, int]],
    delta_vagas: Optional[Mapping[str, int]],
) -> list:
    programas = {
        programa_id: alocado.programa
        for programa_id, alocado in alocacao.programas.items()
    }

    for fonte, relativo in ((vagas, False), (delta_vagas, True)):
        for programa_id, valor in (fonte or {}).items():
            programa = programas.get(programa_id)
            if programa is None:
                raise KeyError(f"programa desconhecido: {programa_id!r}")
            novo = programa.vagas + valor if relativo else valor
            programas[programa_id] = replace(programa, vagas=max(0, int(novo)))

    return list(programas.values())


def _comparar(
    anterior: Alocacao, nova: Alocacao, desistentes: set = frozenset()
) -> Reclassificacao:
    """Diferenca entre dois snapshots, do ponto de vista de cada crianca."""
    subiram: list = []
    sairam: list = []
    desistiram: list = []
    desceram: list = []

    for crianca_id in anterior.candidatos.keys() | nova.candidatos.keys():
        de = anterior.alocacao_de(crianca_id)
        para = nova.alocacao_de(crianca_id)
        if de == para:
            continue

        # a lista de preferencias de referencia e a do estado anterior, para que
        # "subiu da 3ª para a 1ª opcao" seja lido na numeracao que a familia viu
        base = anterior.candidatos.get(crianca_id) or nova.candidatos[crianca_id]
        de_rank = base.rank_da_preferencia(de)
        para_rank = base.rank_da_preferencia(para)

        posicao_antes = None
        if de is None and para is not None and para in anterior.programas:
            posicao_antes = posicao_na_fila(crianca_id, anterior.programa(para))

        movimento = Movimento(
            crianca_id=crianca_id,
            de=de,
            para=para,
            score=int(base.score),
            de_opcao=None if de_rank is None else de_rank + 1,
            para_opcao=None if para_rank is None else para_rank + 1,
            posicao_na_fila_anterior=posicao_antes,
        )

        if para is None:
            # desistente que ficou sem nada nao "perdeu" a vaga: recusou
            (desistiram if crianca_id in desistentes else sairam).append(movimento)
        elif de is None or (para_rank is not None and de_rank is not None
                            and para_rank < de_rank):
            subiram.append(movimento)
        elif crianca_id in desistentes:
            # recusou a propria vaga e caiu para uma opcao pior: e o efeito
            # pretendido, nao uma regressao imposta pelo motor
            desistiram.append(movimento)
        else:
            desceram.append(movimento)

    ordenar = lambda ms: tuple(sorted(ms, key=lambda m: (-m.score, m.crianca_id)))
    return Reclassificacao(
        alocacao=nova,
        anterior=anterior,
        subiram=ordenar(subiram),
        sairam=ordenar(sairam),
        desistiram=ordenar(desistiram),
        desceram=ordenar(desceram),
    )
