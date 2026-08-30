"""Deferred Acceptance -- criancas propoem, programas aceitam provisoriamente.

Substituivel: se o `deferred_acceptance.py` do pipeline for canonico, troque
`deferred_acceptance` por um adaptador que devolva a mesma `Alocacao`. Todo o
resto do pacote depende apenas do tipo de retorno.

Pura: recebe candidatos e programas, devolve uma `Alocacao` nova.
"""

from __future__ import annotations

import heapq
from typing import Callable, Iterable, Mapping, Optional

from .modelos import (
    Alocacao,
    Candidato,
    Programa,
    ProgramaAlocado,
    chave_de_prioridade,
)


def deferred_acceptance(
    candidatos: Iterable[Candidato],
    programas: Iterable[Programa],
    *,
    prioridade: Callable[[Candidato], tuple] = chave_de_prioridade,
    max_rodadas: Optional[int] = None,
) -> Alocacao:
    """Roda o DA e devolve a alocacao estavel.

    Cada crianca propoe a sua opcao 1; o programa retem os melhores classificados
    ate a capacidade e devolve o excedente, que propoe a opcao seguinte. Termina
    quando ninguem mais tem opcao a propor. O resultado e estavel e otimo para o
    lado que propoe (as familias).

    Opcao apontando para programa fora de `programas` e ignorada -- a Query A tem
    unidades que nao casam com todo catalogo.
    """
    por_id: dict = {}
    for programa in programas:
        if programa.programa_id in por_id:
            raise ValueError(f"programa_id duplicado: {programa.programa_id!r}")
        por_id[programa.programa_id] = programa

    inscritos: dict = {}
    for candidato in candidatos:
        if candidato.crianca_id in inscritos:
            raise ValueError(
                f"crianca_id duplicado: {candidato.crianca_id!r}. Uma crianca por "
                "processo -- agregue as opcoes em `preferencias` antes de chamar."
            )
        inscritos[candidato.crianca_id] = candidato

    # Rank inteiro: 0 = melhor classificado. Comparar int e muito mais barato que
    # comparar a tupla de desempate a cada proposta, e o resultado e o mesmo.
    ordem = sorted(inscritos.values(), key=prioridade)
    rank: dict = {c.crianca_id: i for i, c in enumerate(ordem)}

    # retidos[programa_id]: max-heap por rank (guarda -rank, raiz = pior retido)
    retidos: dict = {pid: [] for pid in por_id}
    proxima: dict = {cid: 0 for cid in inscritos}  # indice da proxima opcao

    pendentes = [c.crianca_id for c in ordem]
    rodadas = 0
    teto = max_rodadas if max_rodadas is not None else len(inscritos) + 2

    while pendentes:
        rodadas += 1
        if rodadas > teto:
            raise RuntimeError(
                "DA nao convergiu -- verifique se `prioridade` e uma ordem total"
            )

        rejeitados: list = []
        for crianca_id in pendentes:
            programa_id = _proxima_opcao_valida(
                inscritos[crianca_id], proxima, crianca_id, por_id
            )
            if programa_id is None:
                continue  # esgotou as opcoes: fica sem vaga

            grupo = retidos[programa_id]
            heapq.heappush(grupo, (-rank[crianca_id], crianca_id))
            if len(grupo) > por_id[programa_id].vagas:
                _, expulso = heapq.heappop(grupo)
                rejeitados.append(expulso)

        pendentes = sorted(rejeitados, key=lambda cid: rank[cid])

    admitidos_por_programa = {
        programa_id: [cid for _, cid in sorted(grupo, key=lambda par: -par[0])]
        for programa_id, grupo in retidos.items()
    }

    matches: dict = {}
    for programa_id, grupo in admitidos_por_programa.items():
        for crianca_id in grupo:
            matches[crianca_id] = programa_id

    filas = _montar_filas(inscritos, matches, rank, por_id)

    programas_alocados = {
        programa_id: ProgramaAlocado(
            programa=por_id[programa_id],
            admitidos=tuple(inscritos[cid] for cid in grupo),
            fila=tuple(inscritos[cid] for cid in filas.get(programa_id, ())),
        )
        for programa_id, grupo in admitidos_por_programa.items()
    }

    return Alocacao(
        candidatos=inscritos,
        programas=programas_alocados,
        matches=matches,
        rodadas=rodadas,
    )


def _proxima_opcao_valida(
    candidato: Candidato,
    proxima: dict,
    crianca_id: str,
    por_id: Mapping[str, Programa],
) -> Optional[str]:
    """Consome a lista de preferencias ate achar um programa do catalogo."""
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


def _montar_filas(
    candidatos: Mapping[str, Candidato],
    matches: Mapping[str, str],
    rank: Mapping[str, int],
    por_id: Mapping[str, Programa],
) -> dict:
    """Fila de espera de cada programa, num unico passo pelos candidatos.

    Nem todo mundo que listou o programa entra na fila: quem ja ficou numa opcao
    mais desejada nao sobe se abrir vaga aqui. A fila e exatamente o conjunto que
    aceitaria a vaga -- quem prefere este programa a sua alocacao atual (ou nao
    tem alocacao nenhuma) -- ordenado por prioridade.

    Pela estabilidade do DA, todo mundo nessa fila foi de fato rejeitado por este
    programa, que esta lotado com candidatos melhor classificados.
    """
    filas: dict = {}
    for crianca_id, candidato in candidatos.items():
        atual = matches.get(crianca_id)
        limite = (
            len(candidato.preferencias)
            if atual is None
            else candidato.rank_da_preferencia(atual)
        )
        # so as opcoes estritamente melhores que a alocacao atual
        for programa_id in candidato.preferencias[:limite]:
            if programa_id in por_id:
                filas.setdefault(programa_id, []).append(crianca_id)

    for programa_id, espera in filas.items():
        espera.sort(key=lambda cid: rank[cid])
    return filas
