"""ProgramaClassificado / classificar_programa / posicao_na_fila -- ranking por
programa na linha de vulnerabilidade + distancia (ver test_vulnerabilidade.py
para as pecas de calcular_score que esta classificacao reaproveita)."""

from __future__ import annotations

import pytest

from pessoa_1.localizacao import Localizacao
from pessoa_1.modelos import Score
from pessoa_1.vulnerabilidade import (
    Candidato,
    Programa,
    adicionar_candidato,
    classificar_programa,
    posicao_na_fila,
    remover_candidato,
)


def loc(lat=0.0, lon=0.0) -> Localizacao:
    return Localizacao(latitude=lat, longitude=lon)


def cand(crianca_id, vulnerabilidade=None, localizacoes=None) -> Candidato:
    """`vulnerabilidade` e so uma forma legivel de dizer quantas perguntas
    contam como 'Sim' -- ver test_vulnerabilidade.py para o porque."""
    marcadas = sum(1 for v in (vulnerabilidade or {}).values() if v)
    score = Score(total=0, detalhe={i: 1 for i in range(marcadas)})
    return Candidato(
        crianca_id=crianca_id,
        score=score,
        localizacoes=localizacoes or (loc(), loc()),
    )


def test_classificar_programa_ordena_por_score_decrescente():
    programa = Programa(programa_id="E1", localizacao=loc(0.0, 0.0))
    alta = cand("alta", {"bolsa_familia": 1, "deficiencia": 1})   # score = 2
    media = cand("media", {"bolsa_familia": 1})                  # score = 1
    baixa = cand("baixa", {})                                    # score = 0

    classificada = classificar_programa(programa, [media, baixa, alta])

    assert [c.crianca_id for c in classificada.candidatos] == ["alta", "media", "baixa"]
    assert classificada.programa_id == "E1"


def test_distancia_entra_no_ranking_junto_com_vulnerabilidade():
    programa = Programa(programa_id="E1", localizacao=loc(0.0, 0.0))
    perto_sem_vulnerabilidade = cand("perto", {}, (loc(0.0, 0.0), loc(0.0, 0.0)))
    # duas flags (score 2.0) para nao empatar com a proximidade maxima do
    # "perto" (score 1.0) -- sem isso o teste dependeria do sorteio de empate
    longe_com_vulnerabilidade = cand(
        "longe", {"bolsa_familia": 1, "deficiencia": 1}, (loc(10.0, 10.0), loc(10.0, 10.0))
    )

    classificada = classificar_programa(
        programa, [longe_com_vulnerabilidade, perto_sem_vulnerabilidade], alcance_km=5.0
    )

    # fora do alcance a proximidade satura em 0 -- so a vulnerabilidade conta
    assert [c.crianca_id for c in classificada.candidatos] == ["longe", "perto"]


def test_empate_e_resolvido_por_sorteio_reproduzivel_com_semente():
    programa = Programa(programa_id="E1", localizacao=loc())
    empatados = [cand(str(i)) for i in range(6)]  # todos score 0 -- empate total

    primeira = classificar_programa(programa, empatados, semente=42)
    segunda = classificar_programa(programa, empatados, semente=42)

    assert [c.crianca_id for c in primeira.candidatos] == [
        c.crianca_id for c in segunda.candidatos
    ]


def test_sementes_diferentes_sorteiam_ordens_diferentes():
    programa = Programa(programa_id="E1", localizacao=loc())
    empatados = [cand(str(i)) for i in range(6)]

    ordens = {
        tuple(c.crianca_id for c in classificar_programa(programa, empatados, semente=s).candidatos)
        for s in range(10)
    }
    # com 6 empatados e 10 sementes, a chance de sortear sempre a mesma ordem
    # por acaso e desprezivel -- se isso falhar, o sorteio nao esta variando
    assert len(ordens) > 1


def test_sorteio_de_empate_nao_atropela_diferenca_de_score():
    """O sorteio so decide ENTRE empatados -- quem tem score maior sempre fica
    na frente, seja qual for a semente."""
    programa = Programa(programa_id="E1", localizacao=loc())
    melhor = cand("melhor", {"bolsa_familia": 1})       # score = 1
    empatados = [cand(str(i)) for i in range(5)]        # score = 0

    for semente in range(5):
        classificada = classificar_programa(programa, [*empatados, melhor], semente=semente)
        assert classificada.candidatos[0].crianca_id == "melhor"


def test_classificar_programa_sem_semente_nao_falha():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a"), cand("b")])
    assert {c.crianca_id for c in classificada.candidatos} == {"a", "b"}


def test_pesos_customizados_mudam_a_ordem():
    programa = Programa(programa_id="E1", localizacao=loc(0.0, 0.0))
    vulneravel_longe = cand("vulneravel", {"bolsa_familia": 1}, (loc(10.0, 10.0), loc(10.0, 10.0)))
    perto_sem_flag = cand("perto", {}, (loc(0.0, 0.0), loc(0.0, 0.0)))

    # peso alto em distancia: quem mora perto ganha mesmo sem vulnerabilidade
    classificada = classificar_programa(
        programa,
        [vulneravel_longe, perto_sem_flag],
        peso_vulnerabilidade=1.0,
        peso_distancia=100.0,
        alcance_km=50.0,
    )
    assert classificada.candidatos[0].crianca_id == "perto"


def test_posicao_na_fila_encontra_a_posicao_correta():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(
        programa, [cand("c", {}), cand("b", {"x": 1}), cand("a", {"x": 1, "y": 1})]
    )
    assert posicao_na_fila("a", classificada) == 1
    assert posicao_na_fila("b", classificada) == 2
    assert posicao_na_fila("c", classificada) == 3


def test_posicao_na_fila_none_quando_crianca_nao_esta_na_lista():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a")])
    assert posicao_na_fila("zzz", classificada) is None


def test_classificar_programa_nao_muta_a_lista_de_entrada():
    programa = Programa(programa_id="E1", localizacao=loc())
    candidatos = [cand("b"), cand("a", {"x": 1})]
    antes = list(candidatos)
    classificar_programa(programa, candidatos)
    assert candidatos == antes


def test_classificar_programa_com_lista_vazia():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [])
    assert classificada.candidatos == ()
    assert posicao_na_fila("qualquer", classificada) is None


# --- adicionar_candidato -----------------------------------------------------
def test_adicionar_candidato_entra_na_posicao_que_o_score_determina():
    programa = Programa(programa_id="E1", localizacao=loc(0.0, 0.0))
    longe = (loc(1.0, 0.0), loc(1.0, 0.0))  # fora do alcance default -> proximidade 0
    # "baixo": score 0 (sem flag, longe). "alto": score 2 (1 flag, na porta).
    classificada = classificar_programa(
        programa, [cand("baixo", {}, longe), cand("alto", {"x": 1})]
    )

    # "medio": 1 flag mas longe -- score 1, fica entre os dois
    com_novo = adicionar_candidato(classificada, cand("medio", {"x": 1}, longe))

    assert [c.crianca_id for c in com_novo.candidatos] == ["alto", "medio", "baixo"]


def test_adicionar_candidato_aumenta_o_tamanho_em_um():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a"), cand("b")])
    com_novo = adicionar_candidato(classificada, cand("c"))
    assert len(com_novo.candidatos) == 3
    assert posicao_na_fila("c", com_novo) is not None


def test_adicionar_candidato_em_classificacao_vazia():
    programa = Programa(programa_id="E1", localizacao=loc())
    vazia = classificar_programa(programa, [])
    com_novo = adicionar_candidato(vazia, cand("a"))
    assert [c.crianca_id for c in com_novo.candidatos] == ["a"]


def test_adicionar_candidato_duplicado_falha_alto():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a")])
    with pytest.raises(ValueError, match="ja esta na classificacao"):
        adicionar_candidato(classificada, cand("a"))


def test_adicionar_candidato_nao_muta_a_classificacao_anterior():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a"), cand("b")])
    antes = classificada.candidatos

    adicionar_candidato(classificada, cand("c"))

    assert classificada.candidatos == antes
    assert len(classificada.candidatos) == 2


def test_adicionar_candidato_com_semente_e_reproduzivel_em_empate():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a"), cand("b")], semente=1)

    primeira = adicionar_candidato(classificada, cand("novo"), semente=7)
    segunda = adicionar_candidato(classificada, cand("novo"), semente=7)

    assert primeira.candidatos == segunda.candidatos


# --- remover_candidato -------------------------------------------------------
def test_remover_candidato_tira_da_lista():
    programa = Programa(programa_id="E1", localizacao=loc())
    # scores distintos -- sem isso a ordem inicial de a/b/c e sorteada e o
    # ["a", "c"] esperado depois de remover "b" nao seria garantido
    classificada = classificar_programa(
        programa, [cand("a", {"x": 1, "y": 1}), cand("b", {"x": 1}), cand("c", {})]
    )
    assert [c.crianca_id for c in classificada.candidatos] == ["a", "b", "c"]

    sem_b = remover_candidato(classificada, "b")

    assert [c.crianca_id for c in sem_b.candidatos] == ["a", "c"]
    assert posicao_na_fila("b", sem_b) is None


def test_remover_candidato_preserva_a_ordem_dos_demais():
    programa = Programa(programa_id="E1", localizacao=loc(0.0, 0.0))
    longe = (loc(1.0, 0.0), loc(1.0, 0.0))
    classificada = classificar_programa(
        programa, [cand("baixo", {}, longe), cand("medio", {"x": 1}, longe), cand("alto", {"x": 1})]
    )
    assert [c.crianca_id for c in classificada.candidatos] == ["alto", "medio", "baixo"]

    sem_medio = remover_candidato(classificada, "medio")

    assert [c.crianca_id for c in sem_medio.candidatos] == ["alto", "baixo"]
    assert posicao_na_fila("alto", sem_medio) == 1
    assert posicao_na_fila("baixo", sem_medio) == 2


def test_remover_candidato_inexistente_falha_alto():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a")])
    with pytest.raises(KeyError, match="nao esta na classificacao"):
        remover_candidato(classificada, "zzz")


def test_remover_ultimo_candidato_deixa_lista_vazia():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a")])
    vazia = remover_candidato(classificada, "a")
    assert vazia.candidatos == ()


def test_remover_candidato_nao_muta_a_classificacao_anterior():
    programa = Programa(programa_id="E1", localizacao=loc())
    classificada = classificar_programa(programa, [cand("a"), cand("b")])
    antes = classificada.candidatos

    remover_candidato(classificada, "a")

    assert classificada.candidatos == antes


def test_adicionar_e_remover_sao_inversos():
    programa = Programa(programa_id="E1", localizacao=loc())
    # scores distintos -- com empate, adicionar_candidato resorteia o grupo
    # empatado (comportamento correto, ver README) e o "round trip" deixa de
    # valer por design, nao por bug
    classificada = classificar_programa(programa, [cand("a", {"x": 1}), cand("b", {})])

    com_novo = adicionar_candidato(classificada, cand("c", {"x": 1, "y": 1}))
    de_volta = remover_candidato(com_novo, "c")

    assert de_volta.candidatos == classificada.candidatos
