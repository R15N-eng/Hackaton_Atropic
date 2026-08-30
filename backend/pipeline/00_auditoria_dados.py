"""
Claude Impact Lab Rio #2 — SME/RJ
Script de auditoria reprodutível do discovery (Etapas 1-3).

Rodar de dentro da pasta do repo clonado:
    git clone https://github.com/CIT-SME-RJ/dadoscreche.git
    cd dadoscreche && pip install duckdb pandas openpyxl && python audit_00_discovery.py

Todos os números citados no documento de discovery saem daqui.
Nada aqui é estimativa: é leitura direta das bases publicadas pela SME.
"""
import duckdb, pandas as pd

pd.set_option("display.width", 250)
BASE = "Bases IC_ ClassificadoseFila/"
c = duckdb.connect()

c.sql(f"create view A as select * from read_csv('{BASE}01_QueryA_InscricoesPorAno.csv.gz', delim=';', header=true, encoding='utf-8')")
c.sql(f"create view B as select * from read_csv('{BASE}02_QueryB_RespostasSocioEconomicas.csv.gz', delim=';', header=true, encoding='utf-8')")
c.sql(f"create view C as select * from read_csv('{BASE}03_QueryC_PerguntasComDescricao.csv', delim=';', header=true, encoding='utf-8')")

# Score de vulnerabilidade por inscrição, ano a ano.
# ATENÇÃO: a régua muda de ano para ano (redesenho 2023->2024). Nunca comparar score bruto entre anos.
c.sql("""create table SCORE as
select b.ano, b.prm_id, b.plm_id, b.ipl_id,
       sum(case when b.resposta='Sim' then c.perg_pontuacao else 0 end) as score
from B b join C c on b.ano=c.ano and b.ich_perg_id=c.ich_perg_id
group by 1,2,3,4""")

# Desfecho por inscrição
c.sql("""create table DESFECHO as
select ano, prm_id, plm_id, ipl_id,
  max(case when situacao='Confirmado' then 1 else 0 end) as conf,
  max(case when situacao='Cancelado na confirmacao' then 1 else 0 end) as cc,
  max(case when situacao='Lista de espera' then 1 else 0 end) as espera
from A group by 1,2,3,4""")


def show(sql, titulo):
    print("\n" + "=" * 78 + f"\n{titulo}\n" + "=" * 78)
    print(c.sql(sql).df().to_string(index=False))


# --- F1. Volume ------------------------------------------------------------
show("""select ano, count(*) opcoes,
 count(distinct prm_id||'-'||plm_id||'-'||ipl_id) inscricoes,
 count(distinct aluno_anon) criancas, count(distinct unidade) unidades
from A group by ano order by ano""", "F1 — Volume por ano")

# --- F2. Equidade: o score de vulnerabilidade ainda ordena a fila? ---------
show("""select ano,
 case when s.score=0 then 'A. score 0' else 'B. score > 0' end faixa,
 count(*) inscricoes, round(100.0*avg(d.conf),1) pct_confirmou,
 round(100.0*avg(case when d.conf=0 and d.cc=1 then 1 else 0 end),1) pct_perdeu_na_confirmacao
from SCORE s join DESFECHO d using(ano,prm_id,plm_id,ipl_id)
group by 1,2 order by 1,2""",
     "F2 — Efeito do score de vulnerabilidade sobre o desfecho, por ano")

# --- F3. Integridade declaratória -----------------------------------------
show("""select c.ano, c.perg_pontuacao pts,
 count(*) filter (where b.resposta='Sim') declarou_sim,
 count(*) filter (where b.resposta='Sim' and b.confirmado='Sim') validado,
 round(100.0*count(*) filter (where b.resposta='Sim' and b.confirmado='Sim')
       / nullif(count(*) filter (where b.resposta='Sim'),0),1) pct_validado,
 any_value(substr(c.pergunta_texto,1,55)) pergunta
from B b join C c on b.ano=c.ano and b.ich_perg_id=c.ich_perg_id
where c.ano=2025 group by c.ano, c.ich_perg_id, c.perg_pontuacao
order by pts desc""", "F3 — Declarado x validado documentalmente (2025)")

# --- F4. Desigualdade territorial -----------------------------------------
show("""with crianca as (
 select ano, aluno_anon, any_value(bairro) bairro_fam,
   max(case when situacao='Confirmado' then 1 else 0 end) conf from A group by 1,2)
select bairro_fam, count(*) criancas, sum(conf) atendidas,
 round(100.0*sum(conf)/count(*),1) taxa_atendimento
from crianca where ano=2025 and bairro_fam is not null
group by 1 having count(*)>=300 order by taxa_atendimento""",
     "F4 — Taxa de atendimento por bairro de residência (2025, bairros com >=300 crianças)")

# --- F5. Perda na etapa de confirmação ------------------------------------
show("""select ano, count(*) inscricoes,
 sum(case when conf=0 and cc=1 then 1 else 0 end) perderam_na_confirmacao,
 round(100.0*sum(case when conf=0 and cc=1 then 1 else 0 end)/count(*),1) pct
from DESFECHO group by ano order by ano""",
     "F5 — Inscrições que terminaram sem vaga tendo passado por 'Cancelado na confirmacao'")

# --- F6. Evasão da fila ----------------------------------------------------
show("""with cr as (select ano, aluno_anon,
   max(case when situacao='Confirmado' then 1 else 0 end) conf from A group by 1,2)
select a.ano, a.conf as foi_atendida, count(*) criancas,
 round(100.0*avg(case when b.aluno_anon is not null then 1 else 0 end),1) pct_reinscreve_ano_seguinte
from cr a left join cr b on a.aluno_anon=b.aluno_anon and b.ano=a.ano+1
where a.ano<=2024 group by 1,2 order by 1,2""",
     "F6 — Reinscrição no ano seguinte, por desfecho")

# --- F7. Demanda potencial (nascidos vivos) -------------------------------
nv = pd.read_excel("NascidosvivosRJ.xlsx", header=3).dropna(how="all")
nv.columns = ["bairro"] + [str(x) for x in range(2016, 2027)] + ["total"]
print("\n" + "=" * 78 + "\nF7 — Nascidos vivos no município (denominador de demanda potencial)\n" + "=" * 78)
print(nv[nv.bairro.astype(str).str.strip() == "Total"].to_string(index=False))

# --- F8. Junções entre bases ----------------------------------------------
u = pd.read_excel("OferecimentosEvagas/Unidades_Unificadas_com_Localizacao.xlsx", "Unidades_Unificadas")
u["cod"] = u.DESIGNACAO.astype(str).str.strip().str.zfill(7)
ua = c.sql("select distinct unidade from A").df()
ua["cod"] = ua.unidade.astype(str).str.strip().str.zfill(7)
print("\n" + "=" * 78 + "\nF8 — Qualidade das junções\n" + "=" * 78)
print(f"Unidades da fila (QueryA): {len(ua)}")
print(f"  com lat/long em Unidades_Unificadas: {ua.cod.isin(set(u.cod)).sum()}")
print(f"  microárea SME ausente em {u['microárea'].isna().sum()} de {len(u)} unidades do cadastro")
