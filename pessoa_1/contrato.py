"""Contrato dos artefatos de dados consumidos por este pacote.

Um unico lugar para os nomes de coluna. Se o pipeline em DuckDB
(`01_build_aggregates.py`) usar nomes diferentes dos assumidos aqui, ajuste
apenas este modulo -- nenhum outro arquivo referencia string de coluna.

data/opcoes.parquet
    Grao: uma linha por *opcao de creche* dentro de uma inscricao.
    Uma crianca com 5 opcoes gera 5 linhas com o mesmo score.

data/programas.parquet
    Grao: uma linha por *programa*, onde programa = (ano, unidade, grupamento,
    horario). E nesse nivel que a vaga existe: o mesmo EDI tem fila separada
    para Bercario Integral e Bercario Parcial.
"""

from __future__ import annotations

# --- data/opcoes.parquet ---------------------------------------------------
OPCOES = "opcoes.parquet"

COL_ANO = "ano"
COL_PRM = "prm_id"
COL_PLM = "plm_id"
COL_IPL = "ipl_id"
COL_OPCAO = "opcao"
COL_CRIANCA = "crianca_id"
COL_PROGRAMA = "programa_id"
COL_SCORE = "score"
COL_DESEMPATES = "desempates"
COL_SITUACAO = "situacao"
COL_DATA_CRIACAO = "data_criacao"

# --- data/programas.parquet ------------------------------------------------
PROGRAMAS = "programas.parquet"

COL_UNIDADE = "unidade"
COL_NOME_UNIDADE = "nome_unidade"
COL_GRUPAMENTO = "grupamento"
COL_HORARIO = "horario"
COL_VAGAS = "vagas"

# --- vocabulario da coluna `situacao` (Query A) ----------------------------
# Enum reconstruido no dicionario de dados. Atencao a grafia gravada no banco:
# "Cancelado na confirmacao" vem sem cedilha e sem til.
SITUACAO_COM_VAGA = frozenset(
    {"Confirmado", "Ativo", "Selecionado", "Selecionado da lista"}
)
SITUACAO_FILA = frozenset({"Lista de espera"})
SITUACAO_CANCELADA = frozenset(
    {"Cancelado", "Cancelado na confirmacao", "Cancelado pelo sistema"}
)

# --- criterios de desempate ------------------------------------------------
# Na Query C, `perg_pontuacao = 0` + `perg_criterio = 'Sim'` marca pergunta que
# nao pontua: entra como desempate. A resolucao SME nº 542/2025 cita "desempates"
# sem fixar a ordem no material do hackathon, entao a ordem abaixo e uma
# PREMISSA -- confirmar com a SME antes de usar em producao.
#
# Chaves sao `perg_id` (estavel entre anos), nao `ich_perg_id`.
DESEMPATE_ORDEM: tuple[int, ...] = (
    26,  # Possui irmao participando de processo classificatorio na creche?
    1,   # A mae e mae adolescente?
)

SEPARADOR_DESEMPATES = ","


def montar_programa_id(ano, unidade, grupamento, horario) -> str:
    """Chave canonica do programa. Usada no build e na leitura -- nunca duplicar."""
    partes = (ano, unidade, grupamento, horario)
    return "|".join("" if p is None else str(p).strip() for p in partes)
