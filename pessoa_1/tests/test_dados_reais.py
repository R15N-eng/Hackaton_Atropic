"""Integracao contra os dados reais.

Pula automaticamente se `data/opcoes.parquet` nao existir. Para gerar:

    pip install duckdb pandas pyarrow pytest
    python -m pessoa_1.build_data --ano 2025
"""

from __future__ import annotations

import pytest

from pessoa_1 import (
    calcular_score,
    deferred_acceptance,
    nota_corte_atual,
    posicao_na_fila,
    reclassificar,
)
from pessoa_1 import carga
from pessoa_1.contrato import DESEMPATE_ORDEM

pytestmark = pytest.mark.dados_reais

ANO = 2025
LIMITE_PROGRAMAS = 60  # subproblema real: os 60 programas mais disputados do ano


def _pular_sem_dados():
    pytest.importorskip("pandas", reason="pip install -r requirements.txt")
    pytest.importorskip("pyarrow", reason="pip install -r requirements.txt")
    if not (carga.DIR_DADOS / "opcoes.parquet").exists():
        pytest.skip("rode: python -m pessoa_1.build_data --ano 2025")


@pytest.fixture(scope="module")
def reguas():
    pytest.importorskip("pandas", reason="pip install -r requirements.txt")
    if not carga.QUERY_C.exists():
        pytest.skip(f"Query C nao encontrada em {carga.QUERY_C}")
    return carga.carregar_reguas()


@pytest.fixture(scope="module")
def ano_real():
    _pular_sem_dados()
    candidatos, programas = carga.carregar_ano(ANO, limite_programas=LIMITE_PROGRAMAS)
    if not candidatos or not programas:
        pytest.skip(f"sem dados de {ANO} em opcoes.parquet")
    return candidatos, programas


@pytest.fixture(scope="module")
def alocacao(ano_real):
    candidatos, programas = ano_real
    return deferred_acceptance(candidatos, programas)


# --- regua real (Query C) --------------------------------------------------
def test_query_c_tem_13_perguntas_por_ano(reguas):
    assert set(reguas) == {2021, 2022, 2023, 2024, 2025}
    for ano, regua in reguas.items():
        assert len(regua.perguntas) == 13, ano


def test_reescalonamento_de_2024_esta_na_regua(reguas):
    """perg_id=2 valia 100 pontos de 2021 a 2023 e virou 25 em 2024."""
    assert reguas[2023].por_perg_id(2).pontuacao == 100
    assert reguas[2024].por_perg_id(2).pontuacao == 25


def test_criterios_de_desempate_existem_na_regua_real(reguas):
    for ano, regua in reguas.items():
        criterios = {p.perg_id for p in regua.perguntas.values() if p.criterio}
        assert criterios, ano
        # a ordem de desempate configurada precisa referenciar perguntas reais
        assert set(DESEMPATE_ORDEM) & criterios or ano >= 2024


def test_criterio_equivale_a_pontuacao_zero(reguas):
    """O dicionario de dados afirma a equivalencia nas 65 linhas. Se quebrar, o
    tratamento de `criterio` em `calcular_score` precisa mudar."""
    for regua in reguas.values():
        for pergunta in regua.perguntas.values():
            assert pergunta.criterio == (pergunta.pontuacao == 0)


def test_calcular_score_reproduz_o_maximo_de_cada_ano(reguas):
    for ano, regua in reguas.items():
        todos_sim = {p.ich_perg_id: "Sim" for p in regua.perguntas.values()}
        assert calcular_score(todos_sim, regua).total == regua.pontuacao_maxima


def test_score_do_parquet_cabe_na_regua_do_ano(reguas):
    """O score gravado no parquet nunca pode passar o teto da regua daquele ano
    -- se passar, a regua foi aplicada no ano errado em algum lugar."""
    _pular_sem_dados()
    tabela = carga._ler_parquet(
        carga.DIR_DADOS / "opcoes.parquet", ["ano", "score"]
    )
    for ano, grupo in tabela.groupby("ano"):
        assert grupo["score"].max() <= reguas[int(ano)].pontuacao_maxima, ano
        assert grupo["score"].min() >= 0, ano


def test_calcular_score_bate_com_a_coluna_score_do_parquet(reguas):
    """Recalcula do zero, direto da Query B, para uma amostra de inscricoes e
    compara com o que o build gravou. E o teste que fecha o circuito."""
    _pular_sem_dados()
    if not carga.duckdb_disponivel():
        pytest.skip("precisa do duckdb (modulo ou binario no PATH)")
    from pessoa_1.build_data import QUERY_B

    tabela = carga._ler_parquet(
        carga.DIR_DADOS / "opcoes.parquet",
        ["ano", "prm_id", "plm_id", "ipl_id", "score", "desempates"],
    )
    amostra = (
        tabela[tabela["ano"] == ANO]
        .drop_duplicates(["prm_id", "plm_id", "ipl_id"])
        .sort_values("score", ascending=False)
        .head(200)
    )
    if amostra.empty:
        pytest.skip(f"sem inscricoes de {ANO}")

    chaves = ", ".join(
        f"({int(l.prm_id)}, {int(l.plm_id)}, {int(l.ipl_id)})"
        for l in amostra.itertuples()
    )
    respostas = carga.consultar_duckdb(
        f"""
        SELECT prm_id, plm_id, ipl_id, ich_perg_id, resposta
        FROM read_csv_auto('{QUERY_B.as_posix()}', delim=';', header=true)
        WHERE ano = {ANO} AND (prm_id, plm_id, ipl_id) IN ({chaves})
        """
    )

    por_inscricao: dict = {}
    for linha in respostas.itertuples():
        chave = (int(linha.prm_id), int(linha.plm_id), int(linha.ipl_id))
        por_inscricao.setdefault(chave, {})[int(linha.ich_perg_id)] = linha.resposta

    conferidas = 0
    for linha in amostra.itertuples():
        chave = (int(linha.prm_id), int(linha.plm_id), int(linha.ipl_id))
        score = calcular_score(por_inscricao.get(chave, {}), reguas[ANO])
        assert score.total == int(linha.score), chave
        esperados = {
            int(p) for p in str(linha.desempates or "").split(",") if p.strip()
        }
        assert score.desempates == esperados, chave
        assert not score.ignoradas, chave
        conferidas += 1

    assert conferidas >= 50, "amostra pequena demais para valer como teste"


# --- alocacao sobre dado real ---------------------------------------------
def test_o_recorte_real_tem_tamanho_de_verdade(ano_real, alocacao):
    candidatos, programas = ano_real
    assert len(programas) > 1
    assert len(candidatos) > 100
    assert sum(p.vagas for p in programas) > 0
    assert alocacao.matches, "ninguem foi alocado no recorte"


def test_nenhum_programa_estoura_a_capacidade(alocacao):
    for programa in alocacao.programas.values():
        assert programa.vagas_ocupadas <= programa.vagas, programa.programa_id


def test_cada_crianca_ocupa_no_maximo_uma_vaga(alocacao):
    ocupantes = [cid for p in alocacao.programas.values() for cid in
                 (c.crianca_id for c in p.admitidos)]
    assert len(ocupantes) == len(set(ocupantes))
    assert len(ocupantes) == len(alocacao.matches)


def test_todo_admitido_listou_o_programa(alocacao):
    for programa in alocacao.programas.values():
        for candidato in programa.admitidos:
            assert candidato.rank_da_preferencia(programa.programa_id) is not None


def test_alocacao_real_e_estavel(alocacao):
    """Nenhum par bloqueante: se a crianca prefere outro programa ao seu, aquele
    programa esta lotado e com nota de corte >= o score dela."""
    for crianca_id, candidato in alocacao.candidatos.items():
        atual = alocacao.alocacao_de(crianca_id)
        limite = candidato.rank_da_preferencia(atual)
        melhores = candidato.preferencias[
            : len(candidato.preferencias) if limite is None else limite
        ]
        for programa_id in melhores:
            if programa_id not in alocacao.programas:
                continue
            programa = alocacao.programa(programa_id)
            assert programa.lotado, (crianca_id, programa_id)
            assert nota_corte_atual(programa) >= int(candidato.score)


def test_nota_corte_real_e_o_minimo_dos_admitidos(alocacao):
    for programa in alocacao.programas.values():
        corte = nota_corte_atual(programa)
        if not programa.admitidos:
            assert corte is None
            continue
        assert corte == min(int(c.score) for c in programa.admitidos)
        for candidato in programa.fila:
            # ninguem na fila supera o corte -- seria par bloqueante
            assert int(candidato.score) <= corte


def test_fila_real_esta_ordenada_por_prioridade(alocacao):
    from pessoa_1 import chave_de_prioridade

    for programa in alocacao.programas.values():
        chaves = [chave_de_prioridade(c) for c in programa.fila]
        assert chaves == sorted(chaves), programa.programa_id


def test_posicao_na_fila_real_e_consistente(alocacao):
    programa = max(alocacao.programas.values(), key=lambda p: len(p.fila))
    if not programa.fila:
        pytest.skip("nenhuma fila no recorte")
    for posicao, candidato in enumerate(programa.fila, start=1):
        assert posicao_na_fila(candidato.crianca_id, programa) == posicao
    for candidato in programa.admitidos:
        assert posicao_na_fila(candidato.crianca_id, programa) is None


# --- reclassificacao sobre dado real -------------------------------------
@pytest.fixture(scope="module")
def programa_disputado(alocacao):
    programa = max(
        (p for p in alocacao.programas.values() if p.admitidos and p.fila),
        key=lambda p: len(p.fila),
        default=None,
    )
    if programa is None:
        pytest.skip("nenhum programa lotado com fila no recorte")
    return programa


def test_saida_real_promove_o_primeiro_da_fila(alocacao, programa_disputado):
    """Quando quem tem a vaga deixa o processo, quem sobe e o 1º da fila. Essa
    garantia vale para `saidas`, nao para `desistencias`."""
    programa_id = programa_disputado.programa_id
    proximo = programa_disputado.fila[0].crianca_id

    resultado = reclassificar(
        alocacao, saidas=[programa_disputado.admitidos[0].crianca_id]
    )

    assert resultado.alocacao.alocacao_de(proximo) == programa_id
    assert proximo in {m.crianca_id for m in resultado.subiram}
    assert resultado.desceram == (), "tirar alguem do processo nao piora terceiros"
    corte_antes = nota_corte_atual(programa_disputado)
    corte_depois = nota_corte_atual(resultado.alocacao.programa(programa_id))
    assert corte_depois <= corte_antes


def test_desistencia_real_pode_deslocar_terceiro(alocacao, programa_disputado):
    """Desistir de UMA opcao nao e monotonico: quem desiste segue no processo com
    o score inteiro, desce para a propria 2ª opcao e desloca alguem de la. Esse
    deslocado pode cair na vaga que acabou de vagar e passar na frente da fila.

    Nos dados de 2025 e exatamente o que acontece no programa mais disputado. O
    que continua valendo em qualquer caso: a vaga vai para o melhor classificado
    entre quem a aceitaria -- nunca para alguem pior que o 1º da fila."""
    programa_id = programa_disputado.programa_id
    desistente = programa_disputado.admitidos[0]
    score_do_primeiro = int(programa_disputado.fila[0].score)

    resultado = reclassificar(
        alocacao, desistencias=[(desistente.crianca_id, programa_id)]
    )
    novo = resultado.alocacao.programa(programa_id)

    assert [m.crianca_id for m in resultado.desistiram] == [desistente.crianca_id]
    assert resultado.alocacao.alocacao_de(desistente.crianca_id) != programa_id
    assert novo.vagas_ocupadas <= novo.vagas

    entrantes = {c.crianca_id for c in novo.admitidos} - {
        c.crianca_id for c in programa_disputado.admitidos
    }
    assert len(entrantes) == 1, "uma vaga vagou, uma pessoa entra"
    entrante = next(c for c in novo.admitidos if c.crianca_id in entrantes)
    assert int(entrante.score) >= score_do_primeiro
    # e a alocacao resultante segue estavel
    assert nota_corte_atual(novo) >= max(
        (int(c.score) for c in novo.fila), default=0
    )


def test_reclassificar_nao_perde_ninguem_no_dado_real(alocacao):
    resultado = reclassificar(alocacao, delta_vagas={})
    assert resultado.alocacao.matches == alocacao.matches
    assert resultado.subiram == () and resultado.sairam == ()


@pytest.mark.lento
def test_ano_inteiro_fecha(reguas):
    """O recorte de 60 programas e artificial. Aqui roda o processo inteiro de
    2025 -- 60 mil criancas, 2 mil programas -- e checa os invariantes de ponta a
    ponta. Leva ~15s, quase tudo na carga do parquet."""
    _pular_sem_dados()
    candidatos, programas = carga.carregar_ano(ANO)
    if not candidatos:
        pytest.skip(f"sem dados de {ANO}")

    total_vagas = sum(p.vagas for p in programas)
    resultado = deferred_acceptance(candidatos, programas)

    assert len(resultado.matches) <= total_vagas
    for programa in resultado.programas.values():
        assert programa.vagas_ocupadas <= programa.vagas, programa.programa_id
        corte = nota_corte_atual(programa)
        if programa.admitidos:
            assert corte == min(int(c.score) for c in programa.admitidos)
            # ninguem na fila supera o corte: seria par bloqueante
            assert all(int(c.score) <= corte for c in programa.fila)
        else:
            assert corte is None

    # nenhum score do parquet extrapola a regua do ano
    teto = reguas[ANO].pontuacao_maxima
    assert all(0 <= int(c.score) <= teto for c in candidatos)

    # a maior parte das vagas precisa ser preenchida, senao o recorte esta errado
    assert len(resultado.matches) > 0.9 * total_vagas


def test_vaga_extra_real_nunca_reduz_o_total_alocado(alocacao):
    programa = max(alocacao.programas.values(), key=lambda p: len(p.fila))
    if not programa.fila:
        pytest.skip("nenhuma fila no recorte")
    resultado = reclassificar(alocacao, delta_vagas={programa.programa_id: 1})
    assert len(resultado.alocacao.matches) >= len(alocacao.matches)
    assert resultado.desceram == ()
