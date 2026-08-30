"""
Roda o Deferred Acceptance sobre o processo real e compara com o que aconteceu.

Uso:
    python engine/simulate.py                       # cenário base
    python engine/simulate.py --peso-cadunico 25    # rebalanceia a régua
    python engine/simulate.py --max-opcoes 3        # limita opções por criança
"""
import argparse, sys, os
import duckdb, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from deferred_acceptance import deferred_acceptance

p = argparse.ArgumentParser()
p.add_argument("--peso-cadunico", type=float, default=None,
               help="reescala a contribuição do CadUnico (51 pts na régua de 2025)")
p.add_argument("--max-opcoes", type=int, default=5)
p.add_argument("--semente", default="rio2025")
a = p.parse_args()

c = duckdb.connect()
c.sql("create view O as select * from 'data/opcoes.parquet'")
df = c.sql(f"select crianca, programa, pref, score, confirmado_real from O where pref <= {a.max_opcoes}").df()
cap = c.sql("select programa, capacidade from 'data/programas.parquet'").df()
capacidades = dict(zip(cap.programa, cap.capacidade.astype(int)))

# grupo de vulnerabilidade fixado pela régua ORIGINAL da SME.
# Precisa ser calculado ANTES de mexer nos pesos, senão a alavanca de política
# redefine o próprio grupo que ela deveria estar medindo.
score_original = df.groupby("crianca").score.max().to_dict()

# alavanca de política: reescalar o peso do CadÚnico (51 pts na régua de 2025)
if a.peso_cadunico is not None:
    df["score"] = df.score.apply(lambda s: s - 51 + a.peso_cadunico if s >= 51 else s)

opcoes = df[["crianca", "programa", "pref", "score"]].to_dict("records")
aloc = deferred_acceptance(opcoes, capacidades, semente=a.semente)

# ---- comparação -----------------------------------------------------------
real = dict(df[df.confirmado_real == 1][["crianca", "programa"]].values)
pref_map = {(r.crianca, r.programa): r.pref for r in df.itertuples()}
todas = set(df.crianca)

def metricas(alocacao, nome):
    colocadas = len(alocacao)
    prefs = [pref_map.get((cr, pg)) for cr, pg in alocacao.items()]
    prefs = [x for x in prefs if x is not None]
    primeira = sum(1 for x in prefs if x == 1)
    vuln = [cr for cr in todas if score_original.get(cr, 0) >= 51]
    vuln_col = sum(1 for cr in vuln if cr in alocacao)
    nao_vuln = [cr for cr in todas if score_original.get(cr, 0) < 51]
    nvuln_col = sum(1 for cr in nao_vuln if cr in alocacao)
    return {
        "cenário": nome,
        "crianças colocadas": colocadas,
        "% na 1ª opção": round(100 * primeira / max(colocadas, 1), 1),
        "preferência média": round(sum(prefs) / max(len(prefs), 1), 2),
        "% vulneráveis colocadas": round(100 * vuln_col / max(len(vuln), 1), 1),
        "% não-vulneráveis colocadas": round(100 * nvuln_col / max(len(nao_vuln), 1), 1),
    }

out = pd.DataFrame([metricas(real, "Real 2025 (por opção)"),
                    metricas(aloc, "Deferred Acceptance (por criança)")])
print("=" * 86)
print(f"SIMULAÇÃO — max_opcoes={a.max_opcoes}"
      + (f", peso CadUnico={a.peso_cadunico}" if a.peso_cadunico is not None else ", régua original"))
print("=" * 86)
print(out.to_string(index=False))

g = out.iloc[1]["% vulneráveis colocadas"] - out.iloc[0]["% vulneráveis colocadas"]
print(f"\nvariação no atendimento de famílias vulneráveis: {g:+.1f} pp")
