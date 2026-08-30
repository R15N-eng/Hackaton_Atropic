"""score_calc por vulnerabilidade + distancia -- linha de trabalho separada da
regua oficial (ver test_score.py para a regua da SME)."""

from __future__ import annotations

import pytest

from pessoa_1.localizacao import Localizacao, distancia_km
from pessoa_1.vulnerabilidade import (
    Candidato,
    Escola,
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
    return Candidato(
        crianca_id="c1",
        vulnerabilidade=vulnerabilidade or {},
        localizacoes=localizacoes or (localizacao(), localizacao()),
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


def test_flag_fora_de_0_1_falha_alto():
    with pytest.raises(ValueError, match="so aceita 0/1"):
        candidato({"bolsa_familia": 2})


def test_candidato_exige_exatamente_duas_localizacoes():
    with pytest.raises(ValueError, match="exatamente 2 localizacoes"):
        Candidato(crianca_id="c1", vulnerabilidade={}, localizacoes=(localizacao(),))


# --- menor_distancia_km -----------------------------------------------------
def test_usa_a_localizacao_mais_proxima_da_escola():
    perto = localizacao(0.0, 0.0)
    longe = localizacao(10.0, 10.0)
    c = candidato(localizacoes=(longe, perto))
    escola = Escola(escola_id="E1", localizacao=localizacao(0.0, 0.0))
    assert menor_distancia_km(c, escola) == pytest.approx(0.0, abs=1e-6)


def test_menor_distancia_nao_depende_da_ordem():
    a = localizacao(0.0, 0.0)
    b = localizacao(1.0, 0.0)
    escola = Escola(escola_id="E1", localizacao=a)
    c1 = candidato(localizacoes=(a, b))
    c2 = candidato(localizacoes=(b, a))
    assert menor_distancia_km(c1, escola) == menor_distancia_km(c2, escola)


# --- pontuacao_distancia (decaimento) ---------------------------------------
def test_pontuacao_maxima_na_porta_da_escola():
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
    escola = Escola(escola_id="E1", localizacao=localizacao(0.0, 0.0))

    score = calcular_score(c, escola, peso_vulnerabilidade=3.0, peso_distancia=10.0)

    assert score == pytest.approx(3.0 * 2 + 10.0 * 1.0)


def test_score_retorna_apenas_o_numero():
    c = candidato({"bolsa_familia": 1})
    escola = Escola(escola_id="E1", localizacao=localizacao())
    resultado = calcular_score(c, escola)
    assert isinstance(resultado, float)


def test_score_usa_pesos_default_um():
    c = candidato({"bolsa_familia": 1})  # vulnerabilidade = 1
    escola = Escola(escola_id="E1", localizacao=localizacao())  # distancia 0 -> proximidade 1
    assert calcular_score(c, escola) == pytest.approx(2.0)


def test_score_cai_conforme_a_distancia_aumenta():
    escola = Escola(escola_id="E1", localizacao=localizacao(0.0, 0.0))
    perto = candidato({}, (localizacao(0.0, 0.0), localizacao(0.0, 0.0)))
    longe = candidato({}, (localizacao(1.0, 0.0), localizacao(1.0, 0.0)))

    assert calcular_score(perto, escola, alcance_km=200) > calcular_score(
        longe, escola, alcance_km=200
    )


def test_score_zero_quando_sem_vulnerabilidade_e_fora_do_alcance():
    c = candidato({}, (localizacao(10.0, 10.0), localizacao(10.0, 10.0)))
    escola = Escola(escola_id="E1", localizacao=localizacao(0.0, 0.0))
    assert calcular_score(c, escola, alcance_km=5.0) == 0.0


def test_calcular_score_nao_muta_as_entradas():
    c = candidato({"bolsa_familia": 1})
    escola = Escola(escola_id="E1", localizacao=localizacao())
    antes = (dict(c.vulnerabilidade), c.localizacoes)
    calcular_score(c, escola)
    assert (dict(c.vulnerabilidade), c.localizacoes) == antes
