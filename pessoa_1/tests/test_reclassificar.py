"""reclassificar -- funcao 4."""

from __future__ import annotations

import pytest

from pessoa_1 import deferred_acceptance, nota_corte_atual, reclassificar

from .conftest import faz_candidato, faz_programa


@pytest.fixture
def cenario():
    """A tem 2 vagas, B tem 1. Todas querem A; `c` e `d` ficam na fila de A."""
    candidatos = [
        faz_candidato("a", 300, "A", "B"),
        faz_candidato("b", 210, "A", "B"),
        faz_candidato("c", 110, "A", "B"),
        faz_candidato("d", 10, "A", "B"),
    ]
    return deferred_acceptance(
        candidatos, [faz_programa("A", 2), faz_programa("B", 1)]
    )


def test_desistencia_chama_o_primeiro_da_fila(cenario):
    assert cenario.matches == {"a": "A", "b": "A", "c": "B"}

    resultado = reclassificar(cenario, desistencias=[("a", "A")])

    assert [m.crianca_id for m in resultado.subiram] == ["c"]
    assert resultado.alocacao.alocacao_de("c") == "A"
    movimento = resultado.subiram[0]
    assert movimento.de == "B" and movimento.para == "A"
    assert movimento.de_opcao == 2 and movimento.para_opcao == 1
    assert movimento.subiu


def test_saida_dispara_cascata(cenario):
    """`a` deixa o processo: `c` sai de B para A, e a vaga de B que ela abriu
    puxa `d`, que estava fora. E a cascata que justifica rodar o DA inteiro em
    vez de so chamar o proximo da fila de A."""
    resultado = reclassificar(cenario, saidas=["a"])

    assert resultado.alocacao.alocacao_de("c") == "A"
    assert resultado.alocacao.alocacao_de("d") == "B"
    assert {m.crianca_id for m in resultado.subiram} == {"c", "d"}
    movimento_d = next(m for m in resultado.subiram if m.crianca_id == "d")
    assert movimento_d.de is None and movimento_d.para == "B"
    assert movimento_d.posicao_na_fila_anterior == 1


def test_quem_desiste_cai_para_a_propria_segunda_opcao(cenario):
    """Desistir de A nao libera A para a fila inteira: `a` desce para B, que era
    de `c`, e `c` sobe para A. `d` nao ganha nada -- a vaga de B nao vagou."""
    resultado = reclassificar(cenario, desistencias=[("a", "A")])

    assert resultado.alocacao.matches == {"b": "A", "c": "A", "a": "B"}
    assert resultado.alocacao.alocacao_de("d") is None
    # a queda de `a` e voluntaria: entra em `desistiram`, nunca em `desceram`
    assert [m.crianca_id for m in resultado.desistiram] == ["a"]
    assert resultado.desceram == ()


def test_subiram_vem_do_melhor_score_para_o_pior(cenario):
    resultado = reclassificar(cenario, desistencias=[("a", "A")])
    scores = [m.score for m in resultado.subiram]
    assert scores == sorted(scores, reverse=True)


def test_desistencia_move_a_nota_de_corte(cenario):
    assert nota_corte_atual(cenario.programa("A")) == 210
    resultado = reclassificar(cenario, desistencias=[("a", "A")])
    assert nota_corte_atual(resultado.alocacao.programa("A")) == 110
    assert resultado.notas_de_corte_alteradas["A"] == (210, 110)


def test_quem_desiste_de_uma_opcao_continua_concorrendo_nas_outras(cenario):
    """Desistir de A nao e sair do processo: `a` cai para a 2ª opcao dela."""
    resultado = reclassificar(cenario, desistencias=[("a", "A")])
    assert resultado.alocacao.alocacao_de("a") == "B"
    assert "A" not in resultado.alocacao.candidatos["a"].preferencias


def test_desistencia_sem_programa_usa_a_alocacao_atual(cenario):
    por_id = reclassificar(cenario, desistencias=["a"])
    por_par = reclassificar(cenario, desistencias=[("a", "A")])
    assert por_id.alocacao.matches == por_par.alocacao.matches


def test_saida_do_processo_e_diferente_de_desistir_de_uma_opcao(cenario):
    resultado = reclassificar(cenario, saidas=["a"])
    assert "a" not in resultado.alocacao.candidatos
    assert resultado.alocacao.alocacao_de("c") == "A"
    assert [m.crianca_id for m in resultado.sairam] == ["a"]


def test_vaga_nova_puxa_a_fila(cenario):
    resultado = reclassificar(cenario, delta_vagas={"A": 1})
    assert resultado.alocacao.alocacao_de("c") == "A"
    assert resultado.alocacao.alocacao_de("d") == "B"


def test_capacidade_absoluta(cenario):
    resultado = reclassificar(cenario, vagas={"A": 4})
    assert resultado.alocacao.programa("A").vagas_ocupadas == 4
    assert nota_corte_atual(resultado.alocacao.programa("A")) == 10


def test_corte_de_vaga_faz_alguem_perder_o_lugar(cenario):
    resultado = reclassificar(cenario, vagas={"A": 1})
    assert resultado.alocacao.alocacao_de("b") == "B"
    # `c` perdeu B para `b`, que tem score maior
    assert resultado.alocacao.alocacao_de("c") is None
    assert [m.crianca_id for m in resultado.sairam] == ["c"]


def test_vagas_nunca_ficam_negativas(cenario):
    resultado = reclassificar(cenario, delta_vagas={"A": -99})
    assert resultado.alocacao.programa("A").vagas == 0


def test_candidato_novo_entra_no_meio_da_fila(cenario):
    novo = faz_candidato("novo", 465, "A", "B")
    resultado = reclassificar(cenario, novos_candidatos=[novo])
    assert resultado.alocacao.alocacao_de("novo") == "A"
    assert resultado.alocacao.alocacao_de("b") == "B"
    assert [m.crianca_id for m in resultado.subiram] == ["novo"]
    # `b` desceu de A (1ª) para B (2ª): e uma queda, nao uma subida
    assert [m.crianca_id for m in resultado.desceram] == ["b"]


def test_reclassificar_sem_mudanca_e_idempotente(cenario):
    resultado = reclassificar(cenario)
    assert resultado.alocacao.matches == cenario.matches
    assert resultado.subiram == () and resultado.sairam == ()
    assert resultado.desistiram == () and resultado.desceram == ()
    assert resultado.notas_de_corte_alteradas == {}


def test_saida_e_vaga_nova_nunca_pioram_terceiros(cenario):
    """Sentinela: tirar alguem do processo ou criar vaga so pode melhorar a
    situacao dos outros. Se `desceram` encher aqui, o motor esta errado.

    Note que `desistencias` NAO esta na lista -- ver o teste seguinte.
    """
    for kwargs in ({"saidas": ["a"]}, {"delta_vagas": {"A": 2}},
                   {"vagas": {"B": 3}}):
        assert reclassificar(cenario, **kwargs).desceram == (), kwargs


def test_desistir_de_uma_opcao_pode_derrubar_um_terceiro():
    """Contraexemplo: desistencia nao e monotonica para terceiros.

    Quem desiste de uma opcao continua no processo com o score inteiro, entao
    desce para a propria 2ª opcao e desloca de la alguem com score menor. A vaga
    liberada nao vai necessariamente para o 1º da fila.

    Verificado tambem nos dados reais de 2025 -- ver
    test_dados_reais.test_desistencia_real_pode_deslocar_terceiro.
    """
    candidatos = [
        faz_candidato("alta", 300, "P", "Q"),
        faz_candidato("media", 200, "Q", "R"),
        faz_candidato("baixa", 100, "P"),
    ]
    programas = [faz_programa("P", 1), faz_programa("Q", 1), faz_programa("R", 1)]
    alocacao = deferred_acceptance(candidatos, programas)
    assert alocacao.matches == {"alta": "P", "media": "Q"}
    assert [c.crianca_id for c in alocacao.programa("P").fila] == ["baixa"]

    resultado = reclassificar(alocacao, desistencias=[("alta", "P")])

    assert resultado.alocacao.matches == {"alta": "Q", "media": "R", "baixa": "P"}
    assert [m.crianca_id for m in resultado.desistiram] == ["alta"]
    assert [m.crianca_id for m in resultado.subiram] == ["baixa"]
    # `media` perdeu a 1ª opcao para quem desistiu de outro programa
    assert [m.crianca_id for m in resultado.desceram] == ["media"]


def test_reclassificar_nao_muta_o_snapshot_anterior(cenario):
    matches_antes = dict(cenario.matches)
    resultado = reclassificar(cenario, desistencias=[("a", "A")])
    assert cenario.matches == matches_antes
    assert resultado.anterior.matches == matches_antes
    assert nota_corte_atual(cenario.programa("A")) == 210


def test_crianca_desconhecida_falha_alto(cenario):
    with pytest.raises(KeyError, match="crianca fora da alocacao"):
        reclassificar(cenario, desistencias=[("zzz", "A")])
    with pytest.raises(KeyError, match="crianca fora da alocacao"):
        reclassificar(cenario, saidas=["zzz"])


def test_programa_desconhecido_falha_alto(cenario):
    with pytest.raises(KeyError, match="programa desconhecido"):
        reclassificar(cenario, vagas={"FANTASMA": 3})


def test_candidato_novo_com_id_existente_falha_alto(cenario):
    with pytest.raises(ValueError, match="ja esta na alocacao"):
        reclassificar(cenario, novos_candidatos=[faz_candidato("a", 1, "A")])
