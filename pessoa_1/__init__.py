"""Motor de classificacao de vagas de creche -- funcoes puras.

As quatro funcoes do escopo:
    calcular_score(respostas, regua_do_ano)   -> Score
    nota_corte_atual(programa)                -> int | None
    posicao_na_fila(crianca_id, programa)     -> int | None
    reclassificar(alocacao, ...)              -> Reclassificacao

Sem banco e sem API: o unico modulo com I/O e `carga`, e ele nao e importado
por nenhuma das quatro.
"""

from .deferred_acceptance import deferred_acceptance
from .fila import detalhar_posicao, nota_corte_atual, posicao_na_fila
from .modelos import (
    Alocacao,
    Candidato,
    Movimento,
    Pergunta,
    Programa,
    ProgramaAlocado,
    Reclassificacao,
    ReguaDoAno,
    Score,
    chave_de_prioridade,
)
from .reclassificar import reclassificar
from .score import calcular_score

__all__ = [
    "calcular_score",
    "nota_corte_atual",
    "posicao_na_fila",
    "reclassificar",
    "deferred_acceptance",
    "detalhar_posicao",
    "chave_de_prioridade",
    "Alocacao",
    "Candidato",
    "Movimento",
    "Pergunta",
    "Programa",
    "ProgramaAlocado",
    "Reclassificacao",
    "ReguaDoAno",
    "Score",
]
