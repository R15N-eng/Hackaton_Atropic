from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pessoa_1.modelos import Candidato, Programa, ReguaDoAno, Score  # noqa: E402

# Regua de 2021 reproduzida da Query C (13 perguntas, maximo 465 pontos).
LINHAS_QUERYC_2021 = [
    {"ano": 2021, "ich_perg_id": 95, "perg_id": 2, "perg_pontuacao": 100, "perg_criterio": "Não", "pergunta_texto": "A criança tem alguma deficiência?", "perg_ordemVisualizacao": 1},
    {"ano": 2021, "ich_perg_id": 96, "perg_id": 7, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "deficit nutricional", "perg_ordemVisualizacao": 2},
    {"ano": 2021, "ich_perg_id": 97, "perg_id": 8, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "violencia na residencia", "perg_ordemVisualizacao": 3},
    {"ano": 2021, "ich_perg_id": 98, "perg_id": 9, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "uso de drogas", "perg_ordemVisualizacao": 4},
    {"ano": 2021, "ich_perg_id": 120, "perg_id": 12, "perg_pontuacao": 5, "perg_criterio": "Não", "pergunta_texto": "presidiario", "perg_ordemVisualizacao": 5},
    {"ano": 2021, "ich_perg_id": 121, "perg_id": 11, "perg_pontuacao": 100, "perg_criterio": "Não", "pergunta_texto": "bolsa familia", "perg_ordemVisualizacao": 6},
    {"ano": 2021, "ich_perg_id": 122, "perg_id": 3, "perg_pontuacao": 100, "perg_criterio": "Não", "pergunta_texto": "cartao carioca", "perg_ordemVisualizacao": 7},
    {"ano": 2021, "ich_perg_id": 123, "perg_id": 26, "perg_pontuacao": 0, "perg_criterio": "Sim", "pergunta_texto": "irmao na creche", "perg_ordemVisualizacao": 8},
    {"ano": 2021, "ich_perg_id": 124, "perg_id": 1, "perg_pontuacao": 0, "perg_criterio": "Sim", "pergunta_texto": "mae adolescente", "perg_ordemVisualizacao": 9},
    {"ano": 2021, "ich_perg_id": 125, "perg_id": 21, "perg_pontuacao": 100, "perg_criterio": "Não", "pergunta_texto": "territorios sociais", "perg_ordemVisualizacao": 10},
    {"ano": 2021, "ich_perg_id": 126, "perg_id": 23, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "refugiado", "perg_ordemVisualizacao": 11},
    {"ano": 2021, "ich_perg_id": 127, "perg_id": 24, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "responsavel 60+", "perg_ordemVisualizacao": 12},
    {"ano": 2021, "ich_perg_id": 128, "perg_id": 25, "perg_pontuacao": 10, "perg_criterio": "Não", "pergunta_texto": "responsavel deficiente", "perg_ordemVisualizacao": 13},
]


@pytest.fixture
def regua_2021() -> ReguaDoAno:
    return ReguaDoAno.de_linhas_queryc(2021, LINHAS_QUERYC_2021)


def faz_candidato(
    crianca_id: str,
    score: int,
    *preferencias: str,
    desempates=(),
    dia: int = 1,
) -> Candidato:
    return Candidato(
        crianca_id=crianca_id,
        score=Score(total=score, desempates=frozenset(desempates), ano=2021),
        preferencias=tuple(preferencias),
        data_criacao=datetime(2021, 1, dia),
    )


def faz_programa(programa_id: str, vagas: int) -> Programa:
    return Programa(programa_id=programa_id, vagas=vagas, ano=2021)
