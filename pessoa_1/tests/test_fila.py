"""nota_corte_atual e posicao_na_fila -- funcoes 2 e 3, e o motor de DA."""

from __future__ import annotations

import pytest

from pessoa_1 import (
    deferred_acceptance,
    detalhar_posicao,
    nota_corte_atual,
    posicao_na_fila,
)

from .conftest import faz_candidato, faz_programa


@pytest.fixture
def cenario():
    """Um programa com 2 vagas e 4 candidatas; a segunda opcao de todas e B."""
    candidatos = [
        faz_candidato("a", 300, "A", "B"),
        faz_candidato("b", 210, "A", "B"),
        faz_candidato("c", 110, "A", "B"),
        faz_candidato("d", 10, "A", "B"),
    ]
    programas = [faz_programa("A", 2), faz_programa("B", 1)]
    return deferred_acceptance(candidatos, programas)


# --- funcao 2 --------------------------------------------------------------
def test_nota_corte_e_o_menor_score_entre_os_admitidos(cenario):
    assert nota_corte_atual(cenario.programa("A")) == 210
    assert [c.crianca_id for c in cenario.programa("A").admitidos] == ["a", "b"]


def test_nota_corte_none_quando_ninguem_foi_admitido():
    alocacao = deferred_acceptance([], [faz_programa("A", 5)])
    assert nota_corte_atual(alocacao.programa("A")) is None


def test_nota_corte_com_vaga_sobrando_nao_e_barreira():
    alocacao = deferred_acceptance(
        [faz_candidato("a", 300, "A")], [faz_programa("A", 5)]
    )
    programa = alocacao.programa("A")
    assert nota_corte_atual(programa) == 300
    assert not programa.lotado and programa.vagas_livres == 4


def test_nota_corte_aceita_id_mais_alocacao(cenario):
    assert nota_corte_atual("A", cenario) == 210


def test_nota_corte_e_o_minimo_nao_o_ultimo_colocado():
    """Desempate pode colocar quem tem score menor a frente: o corte e o MIN,
    nao o score do ultimo da lista de admitidos."""
    candidatos = [
        faz_candidato("com_irmao", 100, "A", desempates={26}),
        faz_candidato("sem_irmao", 100, "A"),
    ]
    alocacao = deferred_acceptance(candidatos, [faz_programa("A", 2)])
    programa = alocacao.programa("A")
    assert [c.crianca_id for c in programa.admitidos] == ["com_irmao", "sem_irmao"]
    assert nota_corte_atual(programa) == 100


# --- funcao 3 --------------------------------------------------------------
def test_posicao_na_fila_por_prioridade(cenario):
    fila_a = cenario.programa("A")
    assert posicao_na_fila("c", fila_a) == 1
    assert posicao_na_fila("d", fila_a) == 2


def test_admitido_nao_esta_na_propria_fila(cenario):
    assert posicao_na_fila("a", cenario.programa("A")) is None


def test_quem_esta_em_opcao_melhor_nao_ocupa_fila_de_opcao_pior(cenario):
    """`a` ficou em A (1ª opcao). Se abrir vaga em B (2ª opcao) ela nao sobe --
    logo nao entra na fila de B. Sem isso a fila mente sobre quem seria chamado."""
    fila_b = [c.crianca_id for c in cenario.programa("B").fila]
    assert "a" not in fila_b and "b" not in fila_b
    assert posicao_na_fila("a", cenario.programa("B")) is None


def test_quem_nao_listou_o_programa_nao_tem_posicao(cenario):
    assert posicao_na_fila("inexistente", cenario.programa("A")) is None


def test_detalhar_posicao_separa_os_casos_de_none(cenario):
    assert detalhar_posicao("a", cenario.programa("A"), cenario)["situacao"] == "admitido"
    assert detalhar_posicao("c", cenario.programa("A"), cenario)["situacao"] == "na_fila"
    assert (
        detalhar_posicao("a", cenario.programa("B"), cenario)["situacao"]
        == "alocado_em_opcao_melhor"
    )
    assert (
        detalhar_posicao("zzz", cenario.programa("A"), cenario)["situacao"]
        == "nao_inscrito_no_programa"
    )


def test_detalhar_posicao_monta_a_tela_da_familia(cenario):
    detalhe = detalhar_posicao("c", cenario.programa("A"), cenario)
    assert detalhe["posicao"] == 1
    assert detalhe["nota_corte_atual"] == 210
    assert detalhe["score"] == 110
    assert detalhe["vagas_livres"] == 0


# --- motor -----------------------------------------------------------------
def test_da_respeita_a_ordem_de_preferencia():
    """`b` prefere B, mesmo tendo score para entrar em A."""
    candidatos = [faz_candidato("a", 100, "A"), faz_candidato("b", 300, "B", "A")]
    alocacao = deferred_acceptance(candidatos, [faz_programa("A", 1), faz_programa("B", 1)])
    assert alocacao.matches == {"a": "A", "b": "B"}


def test_da_e_estavel_sem_par_bloqueante(cenario):
    """Estabilidade: se alguem prefere um programa a sua alocacao, esse programa
    esta cheio de gente melhor classificada."""
    for crianca_id, candidato in cenario.candidatos.items():
        atual = cenario.alocacao_de(crianca_id)
        limite = candidato.rank_da_preferencia(atual)
        melhores = candidato.preferencias[: len(candidato.preferencias) if limite is None else limite]
        for programa_id in melhores:
            programa = cenario.programa(programa_id)
            assert programa.lotado, f"{crianca_id} deveria ter entrado em {programa_id}"
            corte = nota_corte_atual(programa)
            assert corte is not None and corte >= int(candidato.score)


def test_da_ignora_opcao_fora_do_catalogo():
    alocacao = deferred_acceptance(
        [faz_candidato("a", 100, "FANTASMA", "A")], [faz_programa("A", 1)]
    )
    assert alocacao.matches == {"a": "A"}


def test_da_deixa_sem_vaga_quem_esgotou_as_opcoes():
    candidatos = [faz_candidato("a", 300, "A"), faz_candidato("b", 100, "A")]
    alocacao = deferred_acceptance(candidatos, [faz_programa("A", 1)])
    assert alocacao.nao_alocados == ("b",)
    assert alocacao.alocacao_de("b") is None


def test_da_recusa_crianca_duplicada():
    with pytest.raises(ValueError, match="crianca_id duplicado"):
        deferred_acceptance(
            [faz_candidato("a", 1, "A"), faz_candidato("a", 2, "A")],
            [faz_programa("A", 1)],
        )


def test_da_recusa_programa_duplicado():
    with pytest.raises(ValueError, match="programa_id duplicado"):
        deferred_acceptance([], [faz_programa("A", 1), faz_programa("A", 2)])


def test_programa_com_zero_vagas_nao_admite_ninguem():
    alocacao = deferred_acceptance(
        [faz_candidato("a", 300, "A", "B")], [faz_programa("A", 0), faz_programa("B", 1)]
    )
    assert alocacao.matches == {"a": "B"}
    assert nota_corte_atual(alocacao.programa("A")) is None


def test_da_nao_muta_a_entrada():
    candidato = faz_candidato("a", 100, "A", "B")
    antes = (candidato.preferencias, int(candidato.score))
    deferred_acceptance([candidato], [faz_programa("A", 1), faz_programa("B", 1)])
    assert (candidato.preferencias, int(candidato.score)) == antes


def test_desempate_por_antiguidade_da_inscricao():
    candidatos = [
        faz_candidato("antiga", 100, "A", dia=1),
        faz_candidato("recente", 100, "A", dia=20),
    ]
    alocacao = deferred_acceptance(candidatos, [faz_programa("A", 1)])
    assert alocacao.matches == {"antiga": "A"}
