"""Funcao 1 -- calcular_score.

Reaproveita a regua da Query C: `perg_pontuacao` e o que a pergunta vale, e
`perg_criterio = 'Sim'` (equivalente a `perg_pontuacao = 0`) marca desempate.
O score e a soma dos pontos das perguntas respondidas 'Sim'.

Pura: nao le arquivo, nao consulta banco, nao usa relogio.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Union

from .modelos import ReguaDoAno, Score

# 'Sim' e o valor gravado em ICH_PerguntaResposta.resp_perg = 1.
_AFIRMATIVAS = frozenset({"sim", "s", "1", "true", "t", "yes", "y"})
_NEGATIVAS = frozenset({"nao", "não", "n", "0", "false", "f", "no", ""})

Respostas = Union[Mapping[int, object], Iterable]


def _e_sim(valor) -> bool:
    """Aceita as formas em que a resposta chega: 'Sim'/'Nao' (Query B), 1/2,
    bool do pandas, None."""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        # resp_perg no banco e 1 = Sim, 2 = Nao. 0 tratado como Nao.
        return int(valor) == 1
    texto = str(valor).strip().lower()
    if texto in _AFIRMATIVAS:
        return True
    if texto in _NEGATIVAS:
        return False
    raise ValueError(f"resposta nao reconhecida: {valor!r}")


def _normalizar(respostas: Respostas) -> dict:
    """-> {ich_perg_id: bool}. Aceita dict, lista de (id, resposta) ou lista de
    dicts no formato longo da Query B."""
    if isinstance(respostas, Mapping):
        return {int(k): _e_sim(v) for k, v in respostas.items()}

    saida: dict = {}
    for item in respostas:
        if isinstance(item, Mapping):
            perg_id = int(item["ich_perg_id"])
            saida[perg_id] = _e_sim(item.get("resposta"))
        else:
            perg_id, valor = item
            saida[int(perg_id)] = _e_sim(valor)
    return saida


def calcular_score(respostas: Respostas, regua_do_ano: ReguaDoAno) -> Score:
    """Pontuacao de uma inscricao segundo a regua do seu ano.

    respostas: `{ich_perg_id: 'Sim'|'Nao'}`, `[(ich_perg_id, resposta), ...]` ou
        `[{'ich_perg_id': .., 'resposta': ..}, ...]` (formato longo da Query B).
        Pergunta ausente conta como 'Nao' -- e assim que a extracao se comporta:
        a Query B so traz respostas ativas (`resp_situacao = 1`).
    regua_do_ano: a `ReguaDoAno` do processo. Regua de outro ano da o numero
        errado -- os pesos foram reescalonados entre 2023 e 2024.

    Retorna `Score` com total, detalhe por `perg_id`, desempates acionados e as
    perguntas respondidas que nao existem na regua (`ignoradas`).
    """
    if regua_do_ano is None or not regua_do_ano.perguntas:
        raise ValueError("regua_do_ano vazia: nao da para pontuar")

    normalizadas = _normalizar(respostas)

    total = 0
    detalhe: dict = {}
    desempates: set = set()
    ignoradas: set = set()

    for ich_perg_id, marcou_sim in normalizadas.items():
        pergunta = regua_do_ano.perguntas.get(ich_perg_id)
        if pergunta is None:
            # pergunta de outro ano/processo: nao pontua, mas registra para o
            # chamador poder detectar regua trocada
            ignoradas.add(ich_perg_id)
            continue
        if not marcou_sim:
            continue
        if pergunta.criterio:
            desempates.add(pergunta.perg_id)
            continue
        total += pergunta.pontuacao
        detalhe[pergunta.perg_id] = detalhe.get(pergunta.perg_id, 0) + pergunta.pontuacao

    return Score(
        total=total,
        detalhe=detalhe,
        desempates=frozenset(desempates),
        ano=regua_do_ano.ano,
        pontuacao_maxima=regua_do_ano.pontuacao_maxima,
        ignoradas=frozenset(ignoradas),
    )
