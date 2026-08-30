import pandas as pd
import numpy as np
import json, os

BASE = r"c:\Profissional\Projetos\Hackaton_ImpactLab_2026\dadoscreche-main\Bases IC_ ClassificadoseFila"
OUT = r"C:\Users\srnon\AppData\Local\Temp\claude\c--Profissional-Projetos-Hackaton-ImpactLab-2026\22ca8003-160d-421f-9e88-c9763a2480ad\scratchpad"

pd.set_option("display.width", 200)

# ---------------------------------------------------------------
# 1) Query A - inscricoes por ano (opcao de creche)
# ---------------------------------------------------------------
qa_path = os.path.join(BASE, "01_QueryA_InscricoesPorAno.csv.gz")
cols_a = ["ano", "prm_id", "plm_id", "ipl_id", "opcao", "aluno_anon", "situacao"]
print("Lendo Query A...")
qa = pd.read_csv(qa_path, sep=";", encoding="utf-8-sig", usecols=cols_a,
                  dtype={"ano": "int32", "prm_id": "int32", "plm_id": "int32",
                         "ipl_id": "int64", "opcao": "int8",
                         "aluno_anon": "string", "situacao": "category"})
print("Query A shape:", qa.shape)

# chave da inscricao (independe da opcao)
qa["insc_key"] = (qa["ano"].astype(str) + "_" + qa["prm_id"].astype(str) + "_" +
                   qa["plm_id"].astype(str) + "_" + qa["ipl_id"].astype(str))

# prioridade de status (1 = melhor desfecho / vaga ocupada, 8 = pior)
prioridade = {
    "Confirmado": 1,
    "Ativo": 2,
    "Selecionado": 3,
    "Selecionado da lista": 4,
    "Lista de espera": 5,
    "Cancelado na confirmacao": 6,
    "Cancelado": 7,
    "Cancelado pelo sistema": 8,
}
qa["prioridade"] = qa["situacao"].map(prioridade).astype("int8")

# melhor situacao por inscricao (1 linha por crianca/inscricao/ano)
idx_best = qa.groupby("insc_key")["prioridade"].idxmin()
insc = qa.loc[idx_best, ["insc_key", "ano", "aluno_anon", "situacao"]].reset_index(drop=True)
insc = insc.rename(columns={"situacao": "melhor_situacao"})
print("Inscricoes distintas (ano,prm,plm,ipl):", insc.shape[0])

VAGA_STATUS = {"Confirmado", "Ativo", "Selecionado", "Selecionado da lista"}
insc["vaga_ocupada"] = insc["melhor_situacao"].isin(VAGA_STATUS)
insc["lista_espera"] = insc["melhor_situacao"] == "Lista de espera"
insc["cancelado"] = insc["melhor_situacao"].isin(
    {"Cancelado", "Cancelado na confirmacao", "Cancelado pelo sistema"})

resumo_ano = insc.groupby("ano").agg(
    inscricoes=("insc_key", "nunique"),
    criancas_distintas=("aluno_anon", "nunique"),
    vagas_ocupadas=("vaga_ocupada", "sum"),
    lista_espera=("lista_espera", "sum"),
    cancelados=("cancelado", "sum"),
).reset_index()
resumo_ano["inscricoes_por_vaga"] = (resumo_ano["inscricoes"] / resumo_ano["vagas_ocupadas"]).round(2)
resumo_ano["criancas_por_vaga"] = (resumo_ano["criancas_distintas"] / resumo_ano["vagas_ocupadas"]).round(2)
resumo_ano["taxa_ocupacao_pct"] = (resumo_ano["vagas_ocupadas"] / resumo_ano["inscricoes"] * 100).round(1)

print(resumo_ano)
resumo_ano.to_csv(os.path.join(OUT, "resumo_inscritos_vaga_por_ano.csv"), index=False)

# opcoes por situacao por ano (linha = opcao, nao inscricao) - contexto adicional
sit_ano = qa.groupby(["ano", "situacao"], observed=True).size().unstack(fill_value=0)
sit_ano.to_csv(os.path.join(OUT, "situacao_opcoes_por_ano.csv"))

# ---------------------------------------------------------------
# 2) Query C - régua de pontuação
# ---------------------------------------------------------------
qc_path = os.path.join(BASE, "03_QueryC_PerguntasComDescricao.csv")
qc = pd.read_csv(qc_path, sep=";", encoding="utf-8-sig")
pont_map = qc.set_index(["ano", "ich_perg_id"])["perg_pontuacao"].to_dict()
max_score_ano = qc.groupby("ano")["perg_pontuacao"].sum().to_dict()
print("Pontuacao maxima teorica por ano:", max_score_ano)

# ---------------------------------------------------------------
# 3) Query B - respostas -> soma de pontuacao por inscricao (em blocos)
# ---------------------------------------------------------------
qb_path = os.path.join(BASE, "02_QueryB_RespostasSocioEconomicas.csv.gz")
cols_b = ["ano", "prm_id", "plm_id", "ipl_id", "ich_perg_id", "resposta"]
print("Lendo Query B em blocos...")

acc = {}  # insc_key -> soma pontuacao
chunk_n = 0
for chunk in pd.read_csv(qb_path, sep=";", encoding="utf-8-sig", usecols=cols_b,
                          dtype={"ano": "int32", "prm_id": "int32", "plm_id": "int32",
                                 "ipl_id": "int64", "ich_perg_id": "int32",
                                 "resposta": "category"},
                          chunksize=500_000):
    chunk_n += 1
    sim = chunk[chunk["resposta"] == "Sim"].copy()
    if sim.empty:
        continue
    sim["pontos"] = list(map(lambda a, p: pont_map.get((a, p), 0), sim["ano"], sim["ich_perg_id"]))
    sim["insc_key"] = (sim["ano"].astype(str) + "_" + sim["prm_id"].astype(str) + "_" +
                        sim["plm_id"].astype(str) + "_" + sim["ipl_id"].astype(str))
    g = sim.groupby("insc_key")["pontos"].sum()
    for k, v in g.items():
        acc[k] = acc.get(k, 0) + v
    print(f"  bloco {chunk_n}: {len(chunk)} linhas, {len(sim)} 'Sim', acumulado {len(acc)} inscricoes com pontos")

score_series = pd.Series(acc, name="score")
score_series.index.name = "insc_key"
score_df = score_series.reset_index()
score_df.to_csv(os.path.join(OUT, "score_por_inscricao_raw.csv"), index=False)
print("Inscricoes com score > 0:", len(score_df))

# ---------------------------------------------------------------
# 4) Junta score com a base de inscricoes (score=0 quando ausente)
# ---------------------------------------------------------------
insc = insc.merge(score_df, on="insc_key", how="left")
insc["score"] = insc["score"].fillna(0).astype(int)
insc["score_max_ano"] = insc["ano"].map(max_score_ano)
insc["pct_max"] = (insc["score"] / insc["score_max_ano"] * 100).round(2)

insc.to_csv(os.path.join(OUT, "inscricoes_com_score.csv"), index=False)

# ---------------------------------------------------------------
# 5) Faixas de score (normalizado, % da pontuacao maxima do ano)
# ---------------------------------------------------------------
def faixa(pct, score):
    if score == 0:
        return "0 pontos"
    elif pct <= 25:
        return "1-25% do maximo"
    elif pct <= 50:
        return "26-50% do maximo"
    elif pct <= 75:
        return "51-75% do maximo"
    else:
        return "76-100% do maximo"

insc["faixa_score"] = [faixa(p, s) for p, s in zip(insc["pct_max"], insc["score"])]

ordem_faixas = ["0 pontos", "1-25% do maximo", "26-50% do maximo", "51-75% do maximo", "76-100% do maximo"]
insc["faixa_score"] = pd.Categorical(insc["faixa_score"], categories=ordem_faixas, ordered=True)

faixa_ano = insc.groupby(["ano", "faixa_score"], observed=True).size().unstack(fill_value=0)
faixa_ano = faixa_ano[ordem_faixas]
faixa_ano.to_csv(os.path.join(OUT, "faixa_score_por_ano_contagem.csv"))

faixa_ano_pct = faixa_ano.div(faixa_ano.sum(axis=1), axis=0) * 100
faixa_ano_pct = faixa_ano_pct.round(1)
faixa_ano_pct.to_csv(os.path.join(OUT, "faixa_score_por_ano_percentual.csv"))

print("\n=== Faixa de score por ano (contagem) ===")
print(faixa_ano)
print("\n=== Faixa de score por ano (%) ===")
print(faixa_ano_pct)

# score x vaga ocupada (cruza faixa de score com desfecho vaga_ocupada)
cruz = insc.groupby(["ano", "faixa_score"], observed=True)["vaga_ocupada"].agg(["sum", "count"])
cruz["taxa_aprovacao_pct"] = (cruz["sum"] / cruz["count"] * 100).round(1)
cruz.to_csv(os.path.join(OUT, "faixa_score_taxa_aprovacao.csv"))
print("\n=== Taxa de vaga ocupada por faixa de score e ano ===")
print(cruz)

# estatisticas descritivas de score por ano
stats_ano = insc.groupby("ano")["score"].agg(["min", "max", "mean", "median"]).round(1)
stats_ano["score_max_teorico"] = stats_ano.index.map(max_score_ano)
stats_ano.to_csv(os.path.join(OUT, "stats_score_por_ano.csv"))
print("\n=== Estatisticas de score por ano ===")
print(stats_ano)

print("\nOK - arquivos salvos em", OUT)
