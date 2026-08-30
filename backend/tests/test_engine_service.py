"""Testes de engine_service.py -- o motor real (Deferred Acceptance da
Pessoa 1) sobre os dados de 2025.

Não usa o fixture `client`/`conftest.py` de propósito: `engine_service.py`
não depende de FastAPI/SQLAlchemy (só de `pessoa_1`), então esses testes
rodam sem precisar do stack todo do backend -- só de
`pip install -r requirements.txt` (duckdb/pandas/openpyxl/pyarrow).

Pula automaticamente se `data/opcoes.parquet` não existir -- gere com
`python -m pessoa_1.build_data --ano 2025` a partir da raiz do repo.
"""

from __future__ import annotations

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
for caminho in (_REPO_ROOT, os.path.join(_BACKEND_DIR, "app")):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

import pytest

from pessoa_1 import carga as motor_carga

pytestmark = pytest.mark.skipif(
    not (motor_carga.DIR_DADOS / "opcoes.parquet").exists(),
    reason="rode: python -m pessoa_1.build_data --ano 2025 (na raiz do repo)",
)


@pytest.fixture(scope="module")
def es():
    import engine_service

    engine_service._STATE = None  # cada rodada de teste carrega do zero
    return engine_service


@pytest.fixture(scope="module")
def estado(es):
    return es.estado()


def test_metricas_gerais_tem_formato_esperado(es):
    m = es.metricas_gerais()
    assert m["total_criancas"] > 0
    assert m["total_programas"] > 0
    assert 0 < m["criancas_colocadas"] <= m["total_criancas"]
    assert m["criancas_colocadas"] <= m["capacidade_total"]
    assert 0 <= m["pct_primeira_opcao"] <= 100
    assert 0 <= m["pct_vulneraveis_colocadas"] <= 100


def test_listar_programas_devolve_chave_sem_prefixo_de_ano(es):
    programas = es.listar_programas(limite=5)
    assert programas
    for p in programas:
        # a chave do motor tem "2025|" na frente; o contrato externo nao
        assert "2025|" not in p["programa"]
        assert p["capacidade"] >= 0
        assert p["ocupadas"] <= p["capacidade"] + p["total_lista_de_espera"]


def test_analise_por_programa_bate_com_listar_programas(es):
    programa = es.listar_programas(limite=1)[0]["programa"]
    detalhe = es.analise_por_programa(programa)
    assert detalhe is not None
    assert detalhe["programa"] == programa
    assert len(detalhe["alocadas"]) == detalhe["ocupadas"]
    assert detalhe["ocupadas"] <= detalhe["capacidade"]


def test_analise_por_programa_inexistente_e_none(es):
    assert es.analise_por_programa("programa-que-nao-existe|X|Y") is None


def test_serializar_crianca_inexistente_e_none(es):
    assert es.serializar_crianca("aluno_nao_existe_999999") is None


def test_amostra_criancas_cobre_status_validos(es):
    amostra = es.amostra_criancas(limite=9)
    assert amostra
    status_validos = {es.STATUS_DENTRO, es.STATUS_ESPERA, es.STATUS_FORA}
    for c in amostra:
        assert c["status"] in status_validos
        detalhe = es.serializar_crianca(c["aluno_anon"])
        assert detalhe["status"] == c["status"]


def test_reclassificar_sem_uma_crianca_alocada(es, estado):
    """Remove uma criança que tem vaga, roda o motor de novo -- alocadas
    depois nunca pode passar de alocadas antes - 1 (quem saiu) + quantas
    vagas isso libera pra fila (sempre >= 0, pelo `nao e monotonica` do
    pessoa_1 nao aplicar aqui -- reclassificar_sem usa saida completa, que
    e sempre monotonica pra terceiros)."""
    alocada = next(cr for cr, prog in estado.alocacao.items())
    resultado = es.reclassificar_sem(alocada)

    assert resultado["aluno_anon_removido"] == alocada
    assert resultado["alocadas_antes"] == len(estado.alocacao)
    # saida completa nunca piora terceiros: quem tinha vaga continua tendo
    assert resultado["alocadas_depois"] >= resultado["alocadas_antes"] - 1
    for m in resultado["movimentos"]:
        assert m["tipo"] in ("subiu_da_lista_de_espera", "trocou_de_programa")


def test_reclassificar_sem_crianca_inexistente(es):
    resultado = es.reclassificar_sem("aluno_nao_existe_999999")
    assert resultado["erro"] == "crianca_nao_encontrada"


def test_timeline_notificacoes_sinaliza_mock(es):
    timeline = es.timeline_notificacoes(limite=3)
    assert timeline["mock"] is True
    assert len(timeline["eventos"]) <= 3
    for evento in timeline["eventos"]:
        assert evento["canal"] == "whatsapp"
