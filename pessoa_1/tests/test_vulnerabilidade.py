"""score_calc por vulnerabilidade + distancia -- linha de trabalho separada da
regua oficial (ver test_score.py para a regua da SME)."""

from __future__ import annotations

import pytest

from pessoa_1.localizacao import Localizacao, distancia_km
from pessoa_1.modelos import Score
from pessoa_1.vulnerabilidade import (
    Candidato,
    Programa,
    calcular_score,
    menor_distancia_km,
    pontuacao_distancia,
    pontuacao_vulnerabilidade,
)

# ~1 grau de latitude no equador = ~111,19 km (raio da Terra usado no modulo).
UM_GRAU_LAT_KM = 111.19


def localizacao(lat=0.0, lon=0.0) -> Localizacao:
    return Localizacao(latitude=lat, longitude=lon)


def candidato(vulnerabilidade=None, localizacoes=None) -> Candidato:
    """`vulnerabilidade` e so uma forma legivel de dizer quantas perguntas
    contam como 'Sim' -- os nomes das chaves nao importam (Candidato.score
    usa perg_id inteiro por dentro), so quantas tem valor truthy.
    `localizacoes=None` fica None de proposito -- e o default do Candidato."""
    marcadas = sum(1 for v in (vulnerabilidade or {}).values() if v)
    score = Score(total=0, detalhe={i: 1 for i in range(marcadas)})
    return Candidato(
        crianca_id="c1",
        score=score,
        localizacoes=localizacoes if localizacoes is not None else (localizacao(), localizacao()),
    )


# --- distancia_km (haversine) ----------------------------------------------
def test_distancia_entre_pontos_iguais_e_zero():
    p = localizacao(-22.9, -43.2)
    assert distancia_km(p, p) == pytest.approx(0.0, abs=1e-9)


def test_distancia_um_grau_de_latitude_no_equador():
    a, b = localizacao(0.0, 0.0), localizacao(1.0, 0.0)
    assert distancia_km(a, b) == pytest.approx(UM_GRAU_LAT_KM, rel=1e-3)


def test_distancia_e_simetrica():
    a, b = localizacao(-22.9, -43.2), localizacao(-22.8, -43.1)
    assert distancia_km(a, b) == pytest.approx(distancia_km(b, a))


def test_localizacao_fora_do_intervalo_falha_alto():
    with pytest.raises(ValueError, match="latitude"):
        Localizacao(latitude=91, longitude=0)
    with pytest.raises(ValueError, match="longitude"):
        Localizacao(latitude=0, longitude=181)


# --- pontuacao_vulnerabilidade ----------------------------------------------
def test_soma_as_flags_de_vulnerabilidade():
    c = candidato({"bolsa_familia": 1, "deficiencia": 0, "cartao_carioca": 1})
    assert pontuacao_vulnerabilidade(c) == 2.0


def test_sem_flags_da_zero():
    assert pontuacao_vulnerabilidade(candidato({})) == 0.0


def test_pontuacao_vulnerabilidade_conta_perguntas_nao_pontos():
    """Cada pergunta pontuada conta 1, nao importa quantos pontos ela vale na
    regua -- pontuacao_vulnerabilidade NAO e o mesmo numero que score.total.
    E o motivo de derivar de Score.detalhe/desempates em vez de um dict
    proprio: a mesma fonte serve pra dois calculos diferentes."""
    score = Score(total=151, detalhe={28: 51, 31: 100})  # 2 perguntas, 151 pontos
    c = Candidato(crianca_id="c1", score=score, localizacoes=(localizacao(), localizacao()))
    assert pontuacao_vulnerabilidade(c) == 2.0
    assert c.score.total == 151


def test_pontuacao_vulnerabilidade_soma_pontuadas_e_desempates():
    score = Score(total=51, detalhe={28: 51}, desempates=frozenset({29, 30}))
    c = Candidato(crianca_id="c1", score=score, localizacoes=(localizacao(), localizacao()))
    assert pontuacao_vulnerabilidade(c) == 3.0  # 1 pontuada + 2 de criterio


def test_candidato_exige_exatamente_duas_localizacoes_ou_nenhuma():
    with pytest.raises(ValueError, match="exatamente 2"):
        Candidato(crianca_id="c1", score=Score(total=0), localizacoes=(localizacao(),))


def test_candidato_aceita_localizacoes_none():
    c = Candidato(crianca_id="c1", score=Score(total=0), localizacoes=None)
    assert c.localizacoes is None


def test_menor_distancia_falha_sem_localizacoes_do_candidato():
    c = Candidato(crianca_id="c1", score=Score(total=0), localizacoes=None)
    programa = Programa(programa_id="E1", localizacao=localizacao())
    with pytest.raises(ValueError, match="sem localizacoes"):
        menor_distancia_km(c, programa)


def test_menor_distancia_falha_sem_localizacao_do_programa():
    c = candidato()
    programa = Programa(programa_id="E1")  # sem localizacao (default None)
    with pytest.raises(ValueError, match="sem localizacao"):
        menor_distancia_km(c, programa)


# --- menor_distancia_km -----------------------------------------------------
def test_usa_a_localizacao_mais_proxima_do_programa():
    perto = localizacao(0.0, 0.0)
    longe = localizacao(10.0, 10.0)
    c = candidato(localizacoes=(longe, perto))
    programa = Programa(programa_id="E1", localizacao=localizacao(0.0, 0.0))
    assert menor_distancia_km(c, programa) == pytest.approx(0.0, abs=1e-6)


def test_menor_distancia_nao_depende_da_ordem():
    a = localizacao(0.0, 0.0)
    b = localizacao(1.0, 0.0)
    programa = Programa(programa_id="E1", localizacao=a)
    c1 = candidato(localizacoes=(a, b))
    c2 = candidato(localizacoes=(b, a))
    assert menor_distancia_km(c1, programa) == menor_distancia_km(c2, programa)


# --- pontuacao_distancia (decaimento) ---------------------------------------
def test_pontuacao_maxima_na_porta_do_programa():
    assert pontuacao_distancia(0.0, alcance_km=5.0) == 1.0


def test_pontuacao_zero_no_limite_do_alcance():
    assert pontuacao_distancia(5.0, alcance_km=5.0) == 0.0


def test_pontuacao_decai_linearmente_no_meio_do_alcance():
    assert pontuacao_distancia(2.5, alcance_km=5.0) == pytest.approx(0.5)


def test_pontuacao_satura_em_zero_alem_do_alcance():
    assert pontuacao_distancia(50.0, alcance_km=5.0) == 0.0


def test_distancia_negativa_falha_alto():
    with pytest.raises(ValueError, match="nao pode ser negativa"):
        pontuacao_distancia(-1.0)


def test_alcance_nao_positivo_falha_alto():
    with pytest.raises(ValueError, match="precisa ser positivo"):
        pontuacao_distancia(1.0, alcance_km=0)


# --- calcular_score (soma ponderada) ----------------------------------------
def test_score_e_a_soma_ponderada_de_vulnerabilidade_e_proximidade():
    c = candidato(
        {"bolsa_familia": 1, "deficiencia": 1},          # vulnerabilidade = 2
        (localizacao(0.0, 0.0), localizacao(0.0, 0.0)),  # distancia = 0 -> proximidade 1.0
    )
    programa = Programa(programa_id="E1", localizacao=localizacao(0.0, 0.0))

    score = calcular_score(c, programa, peso_vulnerabilidade=3.0, peso_distancia=10.0)

    assert score == pytest.approx(3.0 * 2 + 10.0 * 1.0)


def test_score_retorna_apenas_o_numero():
    c = candidato({"bolsa_familia": 1})
    programa = Programa(programa_id="E1", localizacao=localizacao())
    resultado = calcular_score(c, programa)
    assert isinstance(resultado, float)


def test_score_usa_pesos_default_um():
    c = candidato({"bolsa_familia": 1})  # vulnerabilidade = 1
    programa = Programa(programa_id="E1", localizacao=localizacao())  # distancia 0 -> proximidade 1
    assert calcular_score(c, programa) == pytest.approx(2.0)


def test_score_cai_conforme_a_distancia_aumenta():
    programa = Programa(programa_id="E1", localizacao=localizacao(0.0, 0.0))
    perto = candidato({}, (localizacao(0.0, 0.0), localizacao(0.0, 0.0)))
    longe = candidato({}, (localizacao(1.0, 0.0), localizacao(1.0, 0.0)))

    assert calcular_score(perto, programa, alcance_km=200) > calcular_score(
        longe, programa, alcance_km=200
    )


def test_score_zero_quando_sem_vulnerabilidade_e_fora_do_alcance():
    c = candidato({}, (localizacao(10.0, 10.0), localizacao(10.0, 10.0)))
    programa = Programa(programa_id="E1", localizacao=localizacao(0.0, 0.0))
    assert calcular_score(c, programa, alcance_km=5.0) == 0.0


def test_calcular_score_nao_muta_as_entradas():
    c = candidato({"bolsa_familia": 1})
    programa = Programa(programa_id="E1", localizacao=localizacao())
    antes = (dict(c.score.detalhe), c.localizacoes)
    calcular_score(c, programa)
    assert (dict(c.score.detalhe), c.localizacoes) == antes
