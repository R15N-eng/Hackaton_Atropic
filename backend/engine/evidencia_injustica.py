"""
Mede a INVEJA JUSTIFICADA no resultado real do processo seletivo.

Definição conservadora, para não superestimar:
uma criança conta como injustiçada quando (a) terminou o ano SEM nenhuma vaga,
(b) tinha o programa P entre as opções declaradas, e (c) sua pontuação é
ESTRITAMENTE MAIOR que a da criança de menor pontuação admitida em P.

Isso é exatamente o que o Deferred Acceptance elimina por construção.
"""
import duckdb, pandas as pd

c = duckdb.connect()
c.sql("create view O as select * from 'data/opcoes.parquet'")

c.sql("""create table SEM_VAGA as
select crianca, max(score) score from O
where crianca not in (select crianca from O where confirmado_real=1)
group by 1""")

# corte de entrada de cada programa = menor pontuação entre as admitidas
c.sql("""create table CORTE as
select programa, min(score) corte, count(*) admitidas
from O where confirmado_real=1 group by 1""")

print("=" * 74)
print("INVEJA JUSTIFICADA NO RESULTADO REAL DE 2025")
print("=" * 74)

r = c.sql("""
select count(distinct o.crianca) criancas_injusticadas
from O o
join SEM_VAGA s on o.crianca=s.crianca
join CORTE k on o.programa=k.programa
where s.score > k.corte""").df()
total_sem = c.sql("select count(*) from SEM_VAGA").fetchone()[0]
n = int(r.criancas_injusticadas[0])
print(f"crianças que terminaram 2025 sem vaga:              {total_sem:>7,}")
print(f"  dessas, com pontuação acima do corte de alguma")
print(f"  unidade que elas mesmas escolheram:               {n:>7,}  ({100*n/total_sem:.1f}%)")

print("\nPor faixa de pontuação da criança preterida:")
print(c.sql("""
select case when s.score=0 then 'A. score 0'
            when s.score<51 then 'B. score 1-50'
            else 'C. score 51+ (CadUnico)' end faixa,
       count(distinct o.crianca) injusticadas
from O o join SEM_VAGA s on o.crianca=s.crianca
join CORTE k on o.programa=k.programa
where s.score > k.corte group by 1 order by 1""").df().to_string(index=False))

print("\nTop 10 programas que mais preteriram criança de pontuação maior:")
print(c.sql("""
select o.programa, k.corte, k.admitidas, count(distinct o.crianca) preteridas
from O o join SEM_VAGA s on o.crianca=s.crianca
join CORTE k on o.programa=k.programa
where s.score > k.corte
group by 1,2,3 order by preteridas desc limit 10""").df().to_string(index=False))
