"""Funcoes 2 e 3 -- nota de corte e posicao na fila.

Puras: leem so o snapshot recebido.
"""

from __future__ import annotations

from typing import Optional, Union

from .modelos import Alocacao, Candidato, ProgramaAlocado

Programa = Union[ProgramaAlocado, "Alocacao"]


def _resolver(programa, alocacao: Optional[Alocacao] = None) -> ProgramaAlocado:
    """Aceita `ProgramaAlocado` ou `programa_id` + `alocacao`."""
    if isinstance(programa, ProgramaAlocado):
        return programa
    if alocacao is None:
        raise TypeError(
            "passe um ProgramaAlocado (alocacao.programa(id)) ou o par "
            "(programa_id, alocacao=...)"
        )
    return alocacao.programa(str(programa))


def nota_corte_atual(
    programa: Programa, alocacao: Optional[Alocacao] = None
) -> Optional[int]:
    """Menor score entre os admitidos no programa.

    None quando ninguem foi admitido -- nao existe corte, a vaga esta aberta.

    Cuidado ao interpretar: se `programa.vagas_livres > 0`, o programa nao
    esgotou a capacidade e esse numero e apenas o menor score de quem entrou, nao
    uma barreira de entrada. Quem quiser so o corte real deve checar
    `programa.lotado` antes.
    """
    alocado = _resolver(programa, alocacao)
    if not alocado.admitidos:
        return None
    # admitidos vem ordenado do melhor ao pior classificado, mas o minimo e
    # calculado explicitamente: melhor classificado != menor score quando ha
    # desempate envolvido.
    return min(int(candidato.score) for candidato in alocado.admitidos)


def posicao_na_fila(
    crianca_id: str, programa: Programa, alocacao: Optional[Alocacao] = None
) -> Optional[int]:
    """Posicao 1-based da crianca na fila de espera do programa.

    None em tres casos distintos, que o chamador costuma querer separar:
      - a crianca ja esta admitida nesse programa;
      - ela nao listou o programa entre as opcoes;
      - ela ja esta numa opcao que prefere a esta, entao nao subiria se abrisse
        vaga aqui.

    Use `detalhar_posicao` quando precisar saber qual dos tres.
    """
    alocado = _resolver(programa, alocacao)
    for posicao, candidato in enumerate(alocado.fila, start=1):
        if candidato.crianca_id == crianca_id:
            return posicao
    return None


def detalhar_posicao(
    crianca_id: str, programa: Programa, alocacao: Optional[Alocacao] = None
) -> dict:
    """Mesma pergunta que `posicao_na_fila`, com o porque -- para a tela da
    familia ("voce e o 34º; a nota de corte hoje e 210").
    """
    alocado = _resolver(programa, alocacao)
    posicao = posicao_na_fila(crianca_id, alocado)
    admitido = any(c.crianca_id == crianca_id for c in alocado.admitidos)

    candidato: Optional[Candidato] = (
        alocacao.candidatos.get(crianca_id) if alocacao is not None else None
    )
    if candidato is None:
        candidato = next(
            (c for c in alocado.admitidos + alocado.fila if c.crianca_id == crianca_id),
            None,
        )

    if admitido:
        situacao = "admitido"
    elif posicao is not None:
        situacao = "na_fila"
    elif (
        candidato is None
        or candidato.rank_da_preferencia(alocado.programa_id) is None
    ):
        situacao = "nao_inscrito_no_programa"
    else:
        situacao = "alocado_em_opcao_melhor"

    return {
        "crianca_id": crianca_id,
        "programa_id": alocado.programa_id,
        "situacao": situacao,
        "posicao": posicao,
        "tamanho_da_fila": len(alocado.fila),
        "vagas": alocado.vagas,
        "vagas_livres": alocado.vagas_livres,
        "nota_corte_atual": nota_corte_atual(alocado),
        "score": int(candidato.score) if candidato is not None else None,
    }
