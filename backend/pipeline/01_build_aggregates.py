"""
Etapa 1 do pipeline — transforma as bases brutas da SME em parquet enxuto.

Uso:
    python pipeline/01_build_aggregates.py --repo ../dadoscreche --ano 2025

Saída em data/:
    opcoes.parquet     1 linha por (criança, programa) com ordem de preferência e score
    programas.parquet  1 linha por programa = (unidade, grupamento, turno) + capacidade + geo
"""
import argparse, os
import duckdb, pandas as pd

p = argparse.ArgumentParser()
p.add_argument("--repo", default="../dadoscreche", help="raiz do clone de CIT-SME-RJ/dadoscreche")
p.add_argument("--ano", type=int, default=2025)
p.add_argument("--out", default="data")
a = p.parse_args()

BASE = os.path.join(a.repo, "Bases IC_ ClassificadoseFila")
OFER = os.path.join(a.repo, "OferecimentosEvagas")
os.makedirs(a.out, exist_ok=True)
c = duckdb.connect()

c.sql(f"create view A as select * from read_csv('{BASE}/01_QueryA_InscricoesPorAno.csv.gz', delim=';', header=true, encoding='utf-8')")
c.sql(f"create view B as select * from read_csv('{BASE}/02_QueryB_RespostasSocioEconomicas.csv.gz', delim=';', header=true, encoding='utf-8')")
c.sql(f"create view C as select * from read_csv('{BASE}/03_QueryC_PerguntasComDescricao.csv', delim=';', header=true, encoding='utf-8')")

# --- Score aplicando a régua DO ANO (os pesos mudam a cada processo) --------
c.sql(f"""create table SCORE as
select b.prm_id, b.plm_id, b.ipl_id,
       sum(case when b.resposta='Sim' then c.perg_pontuacao else 0 end) as score
from B b join C c on b.ano=c.ano and b.ich_perg_id=c.ich_perg_id
where b.ano={a.ano} group by 1,2,3""")

# --- Opções: 1 linha por (criança, programa) -------------------------------
# programa = unidade + grupamento + turno, que é como a fila é ordenada.
c.sql(f"""create table OPCOES as
select a.aluno_anon                              as crianca,
       a.prm_id, a.plm_id, a.ipl_id,
       a.opcao                                   as pref,
       lpad(cast(a.unidade as varchar),7,'0')    as unidade,
       trim(a.grupamento)                        as grupamento,
       a.horario                                 as turno,
       lpad(cast(a.unidade as varchar),7,'0')||'|'||trim(a.grupamento)||'|'||a.horario as programa,
       coalesce(s.score, 0)                      as score,
       a.bairro                                  as bairro_familia,
       a.CEP                                     as cep_familia,
       a.situacao,
       case when a.situacao='Confirmado' then 1 else 0 end as confirmado_real
from A a left join SCORE s using(prm_id, plm_id, ipl_id)
where a.ano={a.ano}""")

# --- Capacidade: PROXY declarado ------------------------------------------
# Não existe base de vagas ofertadas por processo. Usamos as confirmações
# observadas como capacidade efetivamente preenchida naquele ano.
# Isso limita a pergunta a: "com os MESMOS assentos, dava para alocar melhor?"
c.sql("""create table PROGRAMAS as
select programa, unidade, grupamento, turno,
       count(*) filter (where confirmado_real=1) as capacidade,
       count(*)                                  as demanda_opcoes,
       count(distinct crianca)                   as demanda_criancas
from OPCOES group by 1,2,3,4""")

# --- Geo das unidades ------------------------------------------------------
u = pd.read_excel(os.path.join(OFER, "Unidades_Unificadas_com_Localizacao.xlsx"), "Unidades_Unificadas")
u["unidade"] = u.DESIGNACAO.astype(str).str.strip().str.zfill(7)
u = u[["unidade", "CRE", "microárea", "BAIRRO", "LATITUDE", "LONGITUDE", "Tipo"]].rename(
    columns={"microárea": "microarea", "BAIRRO": "bairro_unidade", "LATITUDE": "lat", "LONGITUDE": "lon"})
u = u.drop_duplicates("unidade")
c.register("GEO", u)

c.sql(f"copy (select o.*, g.lat, g.lon, g.bairro_unidade, g.CRE, g.microarea from OPCOES o left join GEO g using(unidade)) to '{a.out}/opcoes.parquet' (format parquet)")
c.sql(f"copy (select p.*, g.lat, g.lon, g.bairro_unidade, g.CRE, g.microarea from PROGRAMAS p left join GEO g using(unidade)) to '{a.out}/programas.parquet' (format parquet)")

n_op, n_pr = c.sql("select count(*) from OPCOES").fetchone()[0], c.sql("select count(*) from PROGRAMAS").fetchone()[0]
n_cr = c.sql("select count(distinct crianca) from OPCOES").fetchone()[0]
cap  = c.sql("select sum(capacidade) from PROGRAMAS").fetchone()[0]
sem_geo = c.sql("select count(*) from PROGRAMAS p left join GEO g using(unidade) where g.lat is null").fetchone()[0]
print(f"ano {a.ano}: {n_cr} crianças · {n_op} opções · {n_pr} programas · capacidade {cap}")
print(f"programas sem geo: {sem_geo}")
