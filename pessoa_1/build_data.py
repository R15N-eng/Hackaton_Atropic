"""Gera data/opcoes.parquet e data/programas.parquet a partir dos CSVs reais.

Existe um pipeline equivalente em `backend/pipeline/01_build_aggregates.py`
(de outra frente do time, so para o ano de 2025). Este arquivo cobre os 5
anos e preserva `desempates` por pergunta (nao so o score somado) -- e o
motivo de manter os dois: o contrato de dados esta em `contrato.py`, e e o
unico ponto de acoplamento.

    python -m pessoa_1.build_data              # todos os anos
    python -m pessoa_1.build_data --ano 2025

DuckDB le os .gz direto e agrega sem carregar a Query B (4,3 M linhas) na memoria.
O SQL e um so: roda pelo modulo `duckdb` quando ele existe, senao pelo binario
`duckdb` do PATH (util em plataformas sem wheel, como o Python do MSYS2).

Tambem cruza `OferecimentosEvagas/Unidades_Unificadas_com_Localizacao.xlsx`
(base auxiliar da SME, fora da extracao Query A/B/C) para geocodificar as
unidades -- ver `preparar_geo_unidades`. So popula `Programa.localizacao`;
o lado da familia (`Candidato.localizacoes`) continua sem geocodificacao,
essa base nao tem lat/lon do responsavel.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .carga import DIR_BASES, DIR_DADOS, _ler_parquet, _pandas, executar_duckdb
from .contrato import SITUACAO_COM_VAGA

QUERY_A = DIR_BASES / "01_QueryA_InscricoesPorAno.csv.gz"
QUERY_B = DIR_BASES / "02_QueryB_RespostasSocioEconomicas.csv.gz"
QUERY_C = DIR_BASES / "03_QueryC_PerguntasComDescricao.csv"

# Geocodificacao real das unidades -- lat/lon/bairro/CRE por `unidade`. Nao
# faz parte da extracao Query A/B/C do hackathon; e uma base auxiliar da SME
# (a mesma que o pipeline de outra equipe do time ja usa). Casa por
# `unidade` com zero-padding de 7 digitos -- confirmado 1.941 unidades
# distintas, sem nulos em lat/lon na fonte.
GEO_XLSX = (
    DIR_BASES.parent / "OferecimentosEvagas" / "Unidades_Unificadas_com_Localizacao.xlsx"
)


def _sql_lista(valores) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in sorted(valores))


def preparar_geo_unidades(destino: Path) -> Path | None:
    """Le o Excel de geocodificacao e grava um parquet intermediario, para o
    join em SQL puro poder ler um arquivo em vez de um DataFrame em memoria
    -- o fallback via binario `duckdb` (sem o modulo Python) so executa SQL
    de arquivo, nao registra objeto Python.

    None se o Excel nao existir -- geocodificacao e uma base auxiliar, opcional
    (o build continua funcionando sem ela, so `Programa.localizacao` fica
    `None`, como ja era antes desta extensao).

    A coluna de microarea no Excel vem com acento na origem (`microárea`) --
    acessada por posicao, nao por nome, para nao depender de a leitura
    preservar exatamente aquele byte em todo ambiente.
    """
    if not GEO_XLSX.exists():
        return None
    pd = _pandas()
    geo = pd.read_excel(GEO_XLSX, sheet_name="Unidades_Unificadas")
    geo = geo.rename(columns={
        geo.columns[0]: "unidade_raw",  # DESIGNACAO
        geo.columns[1]: "cre",          # CRE
        geo.columns[2]: "microarea",    # microárea
        geo.columns[5]: "bairro_unidade",  # BAIRRO
        geo.columns[6]: "lat",          # LATITUDE
        geo.columns[7]: "lon",          # LONGITUDE
    })
    geo["unidade"] = geo["unidade_raw"].astype(str).str.strip().str.zfill(7)
    geo = geo[["unidade", "cre", "microarea", "bairro_unidade", "lat", "lon"]]
    geo = geo.drop_duplicates("unidade")

    caminho = destino / "_geo_unidades.parquet"
    geo.to_parquet(caminho, index=False)
    return caminho


def montar_sql(ano: int | None, destino: Path, geo_parquet: Path | None) -> str:
    """O script inteiro, em um lugar so. Fonte unica da verdade do build."""
    filtro_c = f"WHERE ano = {int(ano)}" if ano is not None else ""
    filtro_a = f"WHERE a.ano = {int(ano)}" if ano is not None else ""

    if geo_parquet is not None:
        geo_cte = f"SELECT * FROM read_parquet('{geo_parquet.as_posix()}')"
    else:
        geo_cte = (
            "SELECT NULL::VARCHAR AS unidade, NULL::INTEGER AS cre, "
            "NULL::VARCHAR AS microarea, NULL::VARCHAR AS bairro_unidade, "
            "NULL::DOUBLE AS lat, NULL::DOUBLE AS lon WHERE FALSE"
        )

    return f"""
-- geocodificacao das unidades (lat/lon/bairro/CRE) -- ver preparar_geo_unidades
CREATE OR REPLACE TABLE geo_unidades AS {geo_cte};

-- regua de pontuacao (Query C)
CREATE OR REPLACE TABLE regua AS
SELECT
    ano,
    ich_perg_id,
    perg_id,
    CAST(COALESCE(perg_pontuacao, 0) AS INTEGER) AS pontuacao,
    (lower(trim(CAST(perg_criterio AS VARCHAR))) LIKE 's%'
     OR CAST(COALESCE(perg_pontuacao, 0) AS INTEGER) = 0) AS criterio
FROM read_csv_auto('{QUERY_C.as_posix()}', delim=';', header=true, nullstr='NULL')
{filtro_c};

-- score por inscricao (Query B x regua)
-- Grao da chave: (ano, prm_id, plm_id, ipl_id). `ipl_id` sozinho nao e unico:
-- repete entre polos.
CREATE OR REPLACE TABLE score AS
SELECT
    b.ano, b.prm_id, b.plm_id, b.ipl_id,
    CAST(COALESCE(SUM(r.pontuacao) FILTER (WHERE NOT r.criterio), 0)
         AS INTEGER) AS score,
    COALESCE(array_to_string(
        list_sort(list_distinct(list(r.perg_id) FILTER (WHERE r.criterio))),
        ','), '') AS desempates
FROM read_csv_auto('{QUERY_B.as_posix()}', delim=';', header=true) b
JOIN regua r ON r.ano = b.ano AND r.ich_perg_id = b.ich_perg_id
WHERE b.resposta = 'Sim'
GROUP BY 1, 2, 3, 4;

-- opcoes = Query A + score da inscricao
CREATE OR REPLACE TABLE opcoes AS
SELECT
    a.ano, a.prm_id, a.plm_id, a.ipl_id, a.opcao,
    a.aluno_anon AS crianca_id,
    concat_ws('|', CAST(a.ano AS VARCHAR),
              COALESCE(trim(CAST(a.unidade AS VARCHAR)), ''),
              COALESCE(trim(CAST(a.grupamento AS VARCHAR)), ''),
              COALESCE(trim(CAST(a.horario AS VARCHAR)), '')) AS programa_id,
    CAST(a.unidade AS VARCHAR) AS unidade,
    CAST(a.nome_unidade AS VARCHAR) AS nome_unidade,
    trim(CAST(a.grupamento AS VARCHAR)) AS grupamento,
    CAST(a.horario AS VARCHAR) AS horario,
    COALESCE(s.score, 0) AS score,
    COALESCE(s.desempates, '') AS desempates,
    a.situacao,
    a.data_criacao
FROM read_csv_auto('{QUERY_A.as_posix()}', delim=';', header=true) a
LEFT JOIN score s
       ON s.ano = a.ano AND s.prm_id = a.prm_id
      AND s.plm_id = a.plm_id AND s.ipl_id = a.ipl_id
{filtro_a};

-- programas. `vagas` e a ocupacao observada: quantas criancas distintas
-- terminaram o processo com vaga no programa. Proxy da capacidade
-- parametrizada pela SME, que nao esta nas bases do hackathon.
--
-- lat/lon/bairro_unidade/cre/microarea vem de geo_unidades (join por
-- `unidade`) -- nao fazem parte da extracao Query A/B/C. Ficam NULL quando o
-- Excel de geocodificacao nao esta disponivel ou a unidade nao casa (o join
-- e sempre LEFT, nunca reduz o numero de programas).
CREATE OR REPLACE TABLE programas AS
SELECT
    o.programa_id,
    any_value(o.ano) AS ano,
    any_value(o.unidade) AS unidade,
    any_value(o.nome_unidade) AS nome_unidade,
    any_value(o.grupamento) AS grupamento,
    any_value(o.horario) AS horario,
    CAST(COUNT(DISTINCT o.crianca_id) FILTER (
        WHERE o.situacao IN ({_sql_lista(SITUACAO_COM_VAGA)})
    ) AS INTEGER) AS vagas,
    any_value(g.lat) AS lat,
    any_value(g.lon) AS lon,
    any_value(g.bairro_unidade) AS bairro_unidade,
    any_value(g.cre) AS cre,
    any_value(g.microarea) AS microarea
FROM opcoes o
LEFT JOIN geo_unidades g ON g.unidade = o.unidade
GROUP BY o.programa_id;

COPY (
    SELECT ano, prm_id, plm_id, ipl_id, opcao, crianca_id, programa_id,
           score, desempates, situacao, data_criacao
    FROM opcoes
) TO '{(destino / 'opcoes.parquet').as_posix()}' (FORMAT PARQUET);

COPY (SELECT * FROM programas)
TO '{(destino / 'programas.parquet').as_posix()}' (FORMAT PARQUET);
"""


def construir(ano: int | None = None, destino: Path = DIR_DADOS) -> dict:
    for caminho in (QUERY_A, QUERY_B, QUERY_C):
        if not caminho.exists():
            raise FileNotFoundError(f"base nao encontrada: {caminho}")

    destino.mkdir(parents=True, exist_ok=True)
    geo_parquet = preparar_geo_unidades(destino)
    try:
        executar_duckdb(montar_sql(ano, destino, geo_parquet))
    finally:
        if geo_parquet is not None:
            geo_parquet.unlink(missing_ok=True)  # intermediario, nao faz parte do contrato
    return _resumir(destino)


def _resumir(destino: Path) -> dict:
    """Estatisticas de sanidade, lidas de volta dos parquets com pandas."""
    opcoes = _ler_parquet(
        destino / "opcoes.parquet",
        ["ano", "prm_id", "plm_id", "ipl_id", "crianca_id", "score"],
    )
    programas = _ler_parquet(destino / "programas.parquet", ["vagas", "lat", "lon"])

    inscricoes = (
        opcoes[["crianca_id", "ano", "prm_id", "plm_id", "ipl_id"]]
        .drop_duplicates()
        .groupby(["crianca_id", "ano"])
        .size()
    )

    return {
        "opcoes": len(opcoes),
        "criancas": opcoes["crianca_id"].nunique(),
        "programas": len(programas),
        "vagas": int(programas["vagas"].sum()),
        "programas_sem_vaga": int((programas["vagas"] == 0).sum()),
        "score_maximo": int(opcoes["score"].max()),
        "score_zero": int((opcoes["score"] == 0).sum()),
        # sinal de alerta: crianca com mais de uma inscricao no mesmo ano
        "criancas_multi_inscricao": int((inscricoes > 1).sum()),
        "programas_com_geo": int(programas["lat"].notna().sum()),
        "programas_sem_geo": int(programas["lat"].isna().sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=None, help="2021..2025")
    parser.add_argument("--destino", type=Path, default=DIR_DADOS)
    argumentos = parser.parse_args()

    resumo = construir(ano=argumentos.ano, destino=argumentos.destino)
    largura = max(len(chave) for chave in resumo)
    for chave, valor in resumo.items():
        print(f"{chave.rjust(largura)}: {valor:,}".replace(",", "."))


if __name__ == "__main__":
    main()
