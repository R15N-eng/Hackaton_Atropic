"""Vaga/capacidade na linha de vulnerabilidade + distancia: Escola.vagas,
EscolaClassificada.admitidos/fila e nota_corte_atual.

Ver test_ranking_escola.py para o ranking em si (sem capacidade) e
test_dados_reais.py / test_fila.py para o equivalente na regua oficial."""

from __future__ import annotations

import pytest

from pessoa_1.localizacao import Localizacao
from pessoa_1.vulnerabilidade import (
    Candidato,
    Escola,
    classificar_escola,
    nota_corte_atual,
)


def loc(lat=0.0, lon=0.0) -> Localizacao:
    return Localizacao(latitude=lat, longitude=lon)


def cand(crianca_id, vulnerabilidade=None, localizacoes=None) -> Candidato:
    return Candidato(
        crianca_id=crianca_id,
        vulnerabilidade=vulnerabilidade or {},
        localizacoes=localizacoes or (loc(), loc()),
    )


# candidatos com scores inequivocos: nota, {flags}
def candidatos_com_scores():
    return [
        cand("d", {}),                     # score 1 (proximidade, sem flag)
        cand("c", {"x": 1}),               # score 2
        cand("b", {"x": 1, "y": 1}),       # score 3
        cand("a", {"x": 1, "y": 1, "z": 1}),  # score 4
    ]


# --- Escola.vagas ------------------------------------------------------------
def test_escola_vagas_default_e_zero():
    assert Escola(escola_id="E1", localizacao=loc()).vagas == 0


def test_escola_vagas_negativa_falha_alto():
    with pytest.raises(ValueError, match="vagas nao pode ser negativo"):
        Escola(escola_id="E1", localizacao=loc(), vagas=-1)


# --- admitidos / fila --------------------------------------------------------
def test_admitidos_e_fila_dividem_pela_capacidade():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=2)
    classificada = classificar_escola(escola, candidatos_com_scores())

    assert [c.crianca_id for c in classificada.candidatos] == ["a", "b", "c", "d"]
    assert [c.crianca_id for c in classificada.admitidos] == ["a", "b"]
    assert [c.crianca_id for c in classificada.fila] == ["c", "d"]


def test_vagas_ocupadas_livres_e_lotado():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=3)
    classificada = classificar_escola(escola, candidatos_com_scores())

    assert classificada.vagas == 3
    assert classificada.vagas_ocupadas == 3
    assert classificada.vagas_livres == 0
    assert classificada.lotado


def test_vaga_sobrando_nao_esta_lotada():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=10)
    classificada = classificar_escola(escola, candidatos_com_scores())

    assert classificada.vagas_ocupadas == 4
    assert classificada.vagas_livres == 6
    assert not classificada.lotado
    assert classificada.fila == ()


def test_sem_vaga_todo_mundo_fica_na_fila():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=0)
    classificada = classificar_escola(escola, candidatos_com_scores())

    assert classificada.admitidos == ()
    assert len(classificada.fila) == 4
    # `lotado` e True aqui (0 >= 0) -- caso de borda documentado no teste
    # seguinte, nao contradiz "ninguem foi admitido"


def test_escola_com_zero_vagas_e_lotado_por_definicao():
    """vagas_ocupadas(0) >= vagas(0) e verdade -- uma escola com 0 vagas ja
    esta 'lotada' mesmo sem ningum admitido. Documentando o caso de borda."""
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=0)
    classificada = classificar_escola(escola, [])
    assert classificada.lotado


# --- nota_corte_atual ---------------------------------------------------------
def test_nota_corte_e_o_menor_score_entre_os_admitidos():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=2)
    classificada = classificar_escola(escola, candidatos_com_scores())
    # admitidos: a (score 4), b (score 3) -- corte e o menor, 3
    assert nota_corte_atual(classificada) == pytest.approx(3.0)


def test_nota_corte_none_quando_ninguem_foi_admitido():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=0)
    classificada = classificar_escola(escola, candidatos_com_scores())
    assert nota_corte_atual(classificada) is None


def test_nota_corte_com_vaga_sobrando_nao_e_barreira():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=10)
    classificada = classificar_escola(escola, candidatos_com_scores())
    assert nota_corte_atual(classificada) == pytest.approx(1.0)  # score do "d"
    assert not classificada.lotado


def test_nota_corte_sem_candidatos_e_none():
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=5)
    classificada = classificar_escola(escola, [])
    assert nota_corte_atual(classificada) is None


def test_nota_corte_usa_os_pesos_da_classificacao_nao_recalcula():
    """nota_corte_atual nao recebe pesos -- ele le o score que
    classificar_escola ja guardou, sob os pesos usados ali. Isso evita o
    corte "mentir" se alguem chamar com pesos diferentes por engano."""
    escola = Escola(escola_id="E1", localizacao=loc(), vagas=1)
    classificada = classificar_escola(
        escola, candidatos_com_scores(), peso_vulnerabilidade=10.0, peso_distancia=0.0
    )
    # peso_distancia=0 zera a proximidade; so a contagem de flags*10 sobra:
    # a=30 (3 flags), b=20, c=10, d=0 -- unico admitido (vagas=1) e "a"
    assert nota_corte_atual(classificada) == pytest.approx(30.0)


# --- duplicidade -------------------------------------------------------------
def test_classificar_escola_recusa_crianca_id_duplicado():
    escola = Escola(escola_id="E1", localizacao=loc())
    with pytest.raises(ValueError, match="crianca_id duplicado"):
        classificar_escola(escola, [cand("a"), cand("a", {"x": 1})])
