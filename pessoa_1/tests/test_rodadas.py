"""rodadas.py -- motor de rodadas com pontuacao por (candidato, programa)
(vulnerabilidade + distancia), diferente do deferred_acceptance.py da regua
(prioridade global, igual em qualquer programa)."""

from __future__ import annotations

import pytest

from pessoa_1.localizacao import Localizacao
from pessoa_1.modelos import Candidato, Programa, Score
from pessoa_1.rodadas import (
    alocar_vagas_remanescentes,
    deferred_acceptance_por_pontuacao,
    nota_corte_atual,
    posicao_na_fila,
    programas_para_proxima_rodada,
)


def loc(lat=0.0, lon=0.0) -> Localizacao:
    return Localizacao(latitude=lat, longitude=lon)


def cand(crianca_id, flags=0, localizacoes=None, *preferencias) -> Candidato:
    """`flags` = quantas perguntas de vulnerabilidade contam como 'Sim'
    (contagem, nao pontos -- ver vulnerabilidade.pontuacao_vulnerabilidade)."""
    score = Score(total=0, detalhe={i: 1 for i in range(flags)})
    return Candidato(
        crianca_id=crianca_id,
        score=score,
        preferencias=preferencias,
        localizacoes=localizacoes or (loc(), loc()),
    )


def prog(programa_id, vagas, localizacao=None) -> Programa:
    return Programa(programa_id=programa_id, vagas=vagas, localizacao=localizacao or loc())


# --- deferred_acceptance_por_pontuacao --------------------------------------
def test_prioridade_depende_do_programa_dentro_de_um_so_programa():
    """Dentro do programa A, quem mora mais perto ganha a vaga -- prova que a
    decisao de admissao usa a pontuacao DAQUELE programa, nao um rank global
    precalculado (que e como o motor da regua funciona)."""
    perto_de_A = loc(0.0, 0.0)
    perto_de_B = loc(1.0, 0.0)
    A = prog("A", vagas=1, localizacao=perto_de_A)

    # "a" mora perto de A; "b" mora perto de B (longe de A) -- mesma vulnerabilidade
    a = cand("a", 0, (perto_de_A, perto_de_A), "A")
    b = cand("b", 0, (perto_de_B, perto_de_B), "A")  # so listou A, nao tem pra onde ir

    alocacao = deferred_acceptance_por_pontuacao([a, b], [A])

    assert alocacao.matches == {"a": "A"}
    assert alocacao.nao_alocados == ("b",)


def test_a_mesma_dupla_inverte_de_ordem_entre_dois_programas():
    """A demonstracao completa: "a" ganha o programa perto dele, "b" ganha o
    perto dele -- mesmo os dois preferindo A em primeiro lugar. Isso e
    impossivel no motor da regua, onde a prioridade e a mesma em qualquer
    programa (so depende do candidato)."""
    local_A = loc(0.0, 0.0)
    local_B = loc(1.0, 0.0)
    A = prog("A", vagas=1, localizacao=local_A)
    B = prog("B", vagas=1, localizacao=local_B)

    a = cand("a", 0, (local_A, local_A), "A", "B")  # mora em A, prefere A
    b = cand("b", 0, (local_B, local_B), "A", "B")  # mora em B, tambem prefere A

    alocacao = deferred_acceptance_por_pontuacao([a, b], [A, B])

    # "a" ganha a disputa por A (mora la); "b" perde, tenta B e ganha (mora la)
    assert alocacao.matches == {"a": "A", "b": "B"}


def test_admitido_e_quem_tem_maior_pontuacao_no_programa():
    A = prog("A", vagas=1)
    alto = cand("alto", 2, None, "A")   # 2 flags
    baixo = cand("baixo", 0, None, "A")  # 0 flags, mesma localizacao (empate espacial)

    alocacao = deferred_acceptance_por_pontuacao([alto, baixo], [A])

    assert alocacao.matches == {"alto": "A"}
    assert alocacao.nao_alocados == ("baixo",)


def test_respeita_a_ordem_de_preferencia():
    A, B = prog("A", vagas=1), prog("B", vagas=1)
    a = cand("a", 0, None, "A")
    b = cand("b", 5, None, "B", "A")  # prefere B mesmo tendo pontuacao pra A

    alocacao = deferred_acceptance_por_pontuacao([a, b], [A, B])

    assert alocacao.matches == {"a": "A", "b": "B"}


def test_empate_resolvido_por_sorteio_reproduzivel():
    A = prog("A", vagas=1)
    empatados = [cand(str(i), 0, None, "A") for i in range(6)]  # todos empatados

    primeira = deferred_acceptance_por_pontuacao(empatados, [A], semente=1)
    segunda = deferred_acceptance_por_pontuacao(empatados, [A], semente=1)

    assert primeira.matches == segunda.matches


def test_crianca_id_duplicado_falha_alto():
    A = prog("A", vagas=1)
    with pytest.raises(ValueError, match="crianca_id duplicado"):
        deferred_acceptance_por_pontuacao(
            [cand("a", 0, None, "A"), cand("a", 1, None, "A")], [A]
        )


def test_programa_id_duplicado_falha_alto():
    with pytest.raises(ValueError, match="programa_id duplicado"):
        deferred_acceptance_por_pontuacao([], [prog("A", 1), prog("A", 2)])


# --- nota_corte_atual / posicao_na_fila (deste motor) -----------------------
def test_nota_corte_le_o_score_guardado_nao_recalcula():
    A = prog("A", vagas=1)
    alto = cand("alto", 3, None, "A")
    medio = cand("medio", 1, None, "A")

    alocacao = deferred_acceptance_por_pontuacao([alto, medio], [A])
    programa_a = alocacao.programa("A")

    # score default: vulnerabilidade(3) + proximidade(1.0) = 4.0
    assert nota_corte_atual(programa_a) == pytest.approx(4.0)


def test_nota_corte_none_sem_admitido():
    A = prog("A", vagas=0)
    alocacao = deferred_acceptance_por_pontuacao([cand("a", 0, None, "A")], [A])
    assert nota_corte_atual(alocacao.programa("A")) is None


def test_nota_corte_falha_em_programaalocado_da_regua():
    """Sentinela: scores=None (motor da regua) nao pode ser confundido com
    scores vazio -- levanta erro em vez de devolver um numero errado."""
    from pessoa_1.modelos import ProgramaAlocado

    programa_alocado_da_regua = ProgramaAlocado(programa=prog("A", 1))
    with pytest.raises(ValueError, match="sem scores"):
        nota_corte_atual(programa_alocado_da_regua)


def test_posicao_na_fila_deste_motor():
    A = prog("A", vagas=1)
    alto = cand("alto", 3, None, "A")
    medio = cand("medio", 1, None, "A")
    baixo = cand("baixo", 0, None, "A")

    alocacao = deferred_acceptance_por_pontuacao([alto, medio, baixo], [A])
    programa_a = alocacao.programa("A")

    assert posicao_na_fila("medio", programa_a) == 1
    assert posicao_na_fila("baixo", programa_a) == 2
    assert posicao_na_fila("alto", programa_a) is None  # admitido, nao esta na fila


# --- programas_para_proxima_rodada ------------------------------------------
def test_programas_para_proxima_rodada_usa_vagas_livres():
    A = prog("A", vagas=3)
    alocacao = deferred_acceptance_por_pontuacao([cand("a", 0, None, "A")], [A])

    proxima = programas_para_proxima_rodada(alocacao)

    assert len(proxima) == 1
    assert proxima[0].programa_id == "A"
    assert proxima[0].vagas == 2  # 3 - 1 ocupada


def test_programas_para_proxima_rodada_zero_quando_lotado():
    A = prog("A", vagas=1)
    alocacao = deferred_acceptance_por_pontuacao([cand("a", 0, None, "A")], [A])
    proxima = programas_para_proxima_rodada(alocacao)
    assert proxima[0].vagas == 0


# --- alocar_vagas_remanescentes (ultima rodada) -----------------------------
def test_aloca_pelo_programa_mais_proximo_ignorando_preferencias():
    perto = loc(0.0, 0.0)
    longe = loc(10.0, 10.0)
    A = prog("A", vagas=1, localizacao=perto)
    B = prog("B", vagas=1, localizacao=longe)

    # "c" nao listou nenhum dos dois como preferencia -- nao importa aqui
    c = cand("c", 0, (perto, perto))

    alocados = alocar_vagas_remanescentes([c], [A, B])

    assert alocados == {"c": "A"}


def test_atende_por_vulnerabilidade_decrescente():
    A = prog("A", vagas=1, localizacao=loc())
    alta = cand("alta", 3)
    baixa = cand("baixa", 0)

    # so 1 vaga -- quem tem mais vulnerabilidade e atendido primeiro e a pega
    alocados = alocar_vagas_remanescentes([baixa, alta], [A])

    assert alocados == {"alta": "A"}


def test_quem_nao_cabe_fica_de_fora_do_resultado():
    A = prog("A", vagas=1, localizacao=loc())
    a, b = cand("a", 1), cand("b", 0)

    alocados = alocar_vagas_remanescentes([a, b], [A])

    assert set(alocados) == {"a"}  # so quem coube aparece


def test_alocar_vagas_remanescentes_sem_vaga_nenhuma():
    A = prog("A", vagas=0, localizacao=loc())
    alocados = alocar_vagas_remanescentes([cand("a")], [A])
    assert alocados == {}


def test_alocar_vagas_remanescentes_falha_sem_localizacoes():
    A = prog("A", vagas=1, localizacao=loc())
    sem_loc = Candidato(crianca_id="a", score=Score(total=0), localizacoes=None)
    with pytest.raises(ValueError, match="sem localizacoes"):
        alocar_vagas_remanescentes([sem_loc], [A])
