"""Fronteira de I/O -- o unico modulo do pacote que toca disco.

As quatro funcoes do motor sao puras; tudo que le parquet/csv vive aqui, para o
motor poder ser testado sem arquivo e reusado atras de API ou banco depois.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from . import contrato as C
from .localizacao import Localizacao
from .modelos import SEM_DATA, Candidato, Programa, ReguaDoAno, Score

RAIZ = Path(__file__).resolve().parent.parent  # raiz do repo Hackaton_Atropic
DIR_DADOS = RAIZ / "data"
DIR_BASES = RAIZ / "dadoscreche-main" / "Bases IC_ ClassificadoseFila"
QUERY_C = DIR_BASES / "03_QueryC_PerguntasComDescricao.csv"


def _pandas():
    try:
        import pandas as pd
    except ModuleNotFoundError as erro:  # pragma: no cover
        raise ModuleNotFoundError(
            "carga.py precisa de pandas + pyarrow: pip install pandas pyarrow"
        ) from erro
    return pd


# ---------------------------------------------------------------------------
# DuckDB: modulo quando existe, binario do PATH quando nao
# ---------------------------------------------------------------------------
def duckdb_disponivel() -> bool:
    try:
        import duckdb  # noqa: F401

        return True
    except ModuleNotFoundError:
        return shutil.which("duckdb") is not None


def executar_duckdb(sql: str) -> None:
    """Roda um script SQL sem retorno (CREATE, COPY)."""
    try:
        import duckdb
    except ModuleNotFoundError:
        duckdb = None

    if duckdb is not None:
        con = duckdb.connect()
        try:
            con.execute(sql)
        finally:
            con.close()
        return

    binario = shutil.which("duckdb")
    if binario is None:
        raise ModuleNotFoundError(
            "precisa do duckdb: `pip install duckdb` ou o binario `duckdb` no PATH"
        )
    with tempfile.TemporaryDirectory() as pasta:
        script = Path(pasta) / "script.sql"
        script.write_text(sql, encoding="utf-8")
        processo = subprocess.run(
            [binario, "-f", str(script)], capture_output=True, text=True
        )
    if processo.returncode != 0:
        raise RuntimeError(
            f"duckdb falhou (codigo {processo.returncode}):\n{processo.stderr}"
        )


def consultar_duckdb(sql: str):
    """Roda um SELECT e devolve um DataFrame.

    Pelo CLI o resultado vai para um parquet temporario em vez de ser parseado da
    saida de texto -- sem ambiguidade de quoting, encoding ou tipo.
    """
    try:
        import duckdb
    except ModuleNotFoundError:
        duckdb = None

    if duckdb is not None:
        con = duckdb.connect()
        try:
            return con.execute(sql).df()
        finally:
            con.close()

    pd = _pandas()
    with tempfile.TemporaryDirectory() as pasta:
        saida = Path(pasta) / "resultado.parquet"
        executar_duckdb(
            f"COPY ({sql.rstrip().rstrip(';')}) TO '{saida.as_posix()}' "
            f"(FORMAT PARQUET);"
        )
        return pd.read_parquet(saida)


# ---------------------------------------------------------------------------
# Query C -> reguas
# ---------------------------------------------------------------------------
def carregar_reguas(caminho: Path = QUERY_C) -> dict:
    """{ano: ReguaDoAno} a partir da Query C. 13 perguntas por ano, 65 linhas."""
    pd = _pandas()
    tabela = pd.read_csv(
        caminho, sep=";", encoding="utf-8-sig", na_values=["NULL"]
    )
    linhas = tabela.to_dict("records")
    return {
        int(ano): ReguaDoAno.de_linhas_queryc(int(ano), linhas)
        for ano in sorted(tabela["ano"].unique())
    }


# ---------------------------------------------------------------------------
# parquet -> candidatos / programas
# ---------------------------------------------------------------------------
def _ler_parquet(caminho: Path, colunas: Optional[Iterable[str]] = None):
    pd = _pandas()
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho} nao existe. Gere com: python -m pessoa_1.build_data"
        )
    return pd.read_parquet(caminho, columns=list(colunas) if colunas else None)


def _parse_desempates(bruto) -> frozenset:
    if bruto is None or bruto != bruto or not str(bruto).strip():  # NaN-safe
        return frozenset()
    return frozenset(
        int(parte)
        for parte in str(bruto).split(C.SEPARADOR_DESEMPATES)
        if parte.strip()
    )


def carregar_programas(
    ano: Optional[int] = None,
    caminho: Optional[Path] = None,
    programa_ids: Optional[Iterable[str]] = None,
) -> list:
    tabela = _ler_parquet(caminho or DIR_DADOS / C.PROGRAMAS)
    if ano is not None:
        tabela = tabela[tabela[C.COL_ANO] == ano]
    if programa_ids is not None:
        tabela = tabela[tabela[C.COL_PROGRAMA].isin(set(programa_ids))]
    return [
        Programa(
            programa_id=linha[C.COL_PROGRAMA],
            vagas=int(linha[C.COL_VAGAS]),
            ano=int(linha[C.COL_ANO]),
            unidade=linha.get(C.COL_UNIDADE),
            nome_unidade=linha.get(C.COL_NOME_UNIDADE),
            grupamento=linha.get(C.COL_GRUPAMENTO),
            horario=linha.get(C.COL_HORARIO),
            localizacao=_localizacao_da_linha(linha),
        )
        for linha in tabela.to_dict("records")
    ]


def _localizacao_da_linha(linha) -> Optional[Localizacao]:
    """`None` se o parquet nao tem lat/lon (build antigo, sem geocodificacao)
    ou a unidade nao casou com a base de enderecos (~43% hoje nao casam)."""
    lat, lon = linha.get(C.COL_LAT), linha.get(C.COL_LON)
    if lat is None or lon is None:
        return None
    if _pandas().isna(lat) or _pandas().isna(lon):
        return None
    return Localizacao(latitude=float(lat), longitude=float(lon))


def carregar_candidatos(
    ano: Optional[int] = None,
    caminho: Optional[Path] = None,
    programa_ids: Optional[Iterable[str]] = None,
) -> list:
    """Agrega `opcoes.parquet` em um `Candidato` por crianca.

    A crianca pode ter mais de uma inscricao no mesmo ano (polos diferentes) e o
    mesmo `aluno_anon` reaparece nos 5 processos. Aqui as opcoes da crianca no ano
    sao concatenadas na ordem `(data_criacao, ipl_id, opcao)`, com o maior score
    entre as inscricoes; programa repetido mantem so a primeira aparicao.

    programa_ids recorta um subconjunto de programas: ficam as criancas que
    listaram ao menos um deles, com as preferencias reduzidas a esses programas.
    """
    tabela = _ler_parquet(caminho or DIR_DADOS / C.OPCOES)
    if ano is not None:
        tabela = tabela[tabela[C.COL_ANO] == ano]
    if programa_ids is not None:
        tabela = tabela[tabela[C.COL_PROGRAMA].isin(set(programa_ids))]
    if tabela.empty:
        return []

    tabela = tabela.sort_values(
        [C.COL_CRIANCA, C.COL_DATA_CRIACAO, C.COL_IPL, C.COL_OPCAO],
        kind="mergesort",
    )

    candidatos: list = []
    for crianca_id, grupo in tabela.groupby(C.COL_CRIANCA, sort=True):
        preferencias: list = []
        vistos: set = set()
        for programa_id in grupo[C.COL_PROGRAMA]:
            if programa_id not in vistos:
                vistos.add(programa_id)
                preferencias.append(programa_id)

        melhor = grupo.loc[grupo[C.COL_SCORE].idxmax()]
        data = melhor[C.COL_DATA_CRIACAO]
        candidatos.append(
            Candidato(
                crianca_id=str(crianca_id),
                score=Score(
                    total=int(melhor[C.COL_SCORE]),
                    desempates=_parse_desempates(melhor.get(C.COL_DESEMPATES)),
                    ano=int(melhor[C.COL_ANO]),
                ),
                preferencias=tuple(preferencias),
                data_criacao=data.to_pydatetime() if hasattr(data, "to_pydatetime") else (data or SEM_DATA),
                ipl_id=int(melhor[C.COL_IPL]),
                ano=int(melhor[C.COL_ANO]),
            )
        )
    return candidatos


def carregar_ano(ano: int, limite_programas: Optional[int] = None) -> tuple:
    """(candidatos, programas) de um processo.

    `limite_programas` recorta os N programas mais disputados do ano -- um
    subproblema real, pequeno o bastante para teste rapido.
    """
    programa_ids = None
    if limite_programas is not None:
        tabela = _ler_parquet(
            DIR_DADOS / C.OPCOES, [C.COL_ANO, C.COL_PROGRAMA]
        )
        tabela = tabela[tabela[C.COL_ANO] == ano]
        programa_ids = (
            tabela[C.COL_PROGRAMA].value_counts().head(limite_programas).index.tolist()
        )
    return (
        carregar_candidatos(ano, programa_ids=programa_ids),
        carregar_programas(ano, programa_ids=programa_ids),
    )
