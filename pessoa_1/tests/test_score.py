"""calcular_score -- funcao 1."""

from __future__ import annotations

import pytest

from pessoa_1 import ReguaDoAno, calcular_score

from .conftest import LINHAS_QUERYC_2021


def test_regua_2021_bate_com_a_query_c(regua_2021):
    assert len(regua_2021.perguntas) == 13
    assert regua_2021.pontuacao_maxima == 465
    assert regua_2021.por_perg_id(2).pontuacao == 100


def test_soma_apenas_as_respostas_sim(regua_2021):
    score = calcular_score(
        {95: "Sim", 96: "Sim", 97: "Nao", 121: "Sim"}, regua_2021
    )
    assert score.total == 210  # 100 deficiencia + 10 nutricional + 100 bolsa
    assert score.detalhe == {2: 100, 7: 10, 11: 100}


def test_pergunta_ausente_conta_como_nao(regua_2021):
    # a Query B so traz `resp_situacao = 1`; ausencia e "nao respondeu"
    assert calcular_score({}, regua_2021).total == 0
    assert calcular_score({95: "Sim"}, regua_2021).total == 100


def test_criterio_nao_pontua_e_vai_para_desempates(regua_2021):
    score = calcular_score({123: "Sim", 124: "Sim", 95: "Sim"}, regua_2021)
    assert score.total == 100
    assert score.desempates == frozenset({26, 1})  # irmao, mae adolescente
    assert 26 not in score.detalhe


def test_teto_da_regua(regua_2021):
    todos_sim = {p.ich_perg_id: "Sim" for p in regua_2021.perguntas.values()}
    score = calcular_score(todos_sim, regua_2021)
    assert score.total == 465
    assert score.pct_maxima == 100.0


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("Sim", 100), ("sim", 100), (1, 100), (True, 100),
        ("Nao", 0), ("Não", 0), (2, 0), (False, 0), (None, 0), ("", 0),
    ],
)
def test_aceita_as_formas_em_que_a_resposta_chega(regua_2021, valor, esperado):
    assert calcular_score({95: valor}, regua_2021).total == esperado


def test_resposta_lixo_falha_alto(regua_2021):
    with pytest.raises(ValueError, match="resposta nao reconhecida"):
        calcular_score({95: "talvez"}, regua_2021)


def test_formato_longo_da_query_b(regua_2021):
    linhas = [
        {"ich_perg_id": 95, "resposta": "Sim"},
        {"ich_perg_id": 121, "resposta": "Sim"},
        {"ich_perg_id": 122, "resposta": "Nao"},
    ]
    assert calcular_score(linhas, regua_2021).total == 200
    assert calcular_score([(95, "Sim"), (121, "Sim")], regua_2021).total == 200


def test_pergunta_de_outro_ano_nao_pontua_e_e_sinalizada(regua_2021):
    # 142 e o ich_perg_id da mesma pergunta em 2022
    score = calcular_score({142: "Sim", 95: "Sim"}, regua_2021)
    assert score.total == 100
    assert score.ignoradas == frozenset({142})


def test_regua_de_outro_ano_da_numero_diferente():
    """perg_id=2 valia 100 pontos ate 2023 e caiu para 25 em 2024. E o motivo de
    a regua ser sempre por ano."""
    r2021 = ReguaDoAno.de_linhas_queryc(2021, LINHAS_QUERYC_2021)
    r2024 = ReguaDoAno.de_linhas_queryc(
        2024,
        [{"ano": 2024, "ich_perg_id": 95, "perg_id": 2, "perg_pontuacao": 25,
          "perg_criterio": "Não"}],
    )
    assert calcular_score({95: "Sim"}, r2021).total == 100
    assert calcular_score({95: "Sim"}, r2024).total == 25


def test_regua_vazia_falha_alto():
    with pytest.raises(ValueError, match="regua_do_ano vazia"):
        calcular_score({95: "Sim"}, ReguaDoAno(ano=2021, perguntas={}))


def test_score_compara_com_int(regua_2021):
    score = calcular_score({95: "Sim"}, regua_2021)
    assert score >= 100 and score > 99 and not score > 100
    assert int(score) == 100
