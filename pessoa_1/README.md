# pessoa_1 — motor de classificação de vagas de creche

Quatro funções puras. Sem banco, sem API. O único módulo que toca disco é
[carga.py](carga.py), e nenhuma das quatro funções o importa.

> Integração com a API (Back B): ver **"Como integrar com a Pessoa 1"** em
> [backend/README.md](../backend/README.md). O stub em
> `backend/app/classification_engine.py` está esperando estas 4 funções —
> ainda não fiz a troca porque falta alinhar IDs (aqui são `str`; lá são
> inteiros do SQLite) e o formato de retorno de `reclassificar` (aqui é um
> objeto rico; lá espera `list[int]`).

```python
from pessoa_1 import calcular_score, nota_corte_atual, posicao_na_fila, reclassificar
```

| # | Função | Assinatura | Retorno |
|---|---|---|---|
| 1 | `calcular_score` | `(respostas, regua_do_ano)` | `Score` — total, detalhe por `perg_id`, desempates |
| 2 | `nota_corte_atual` | `(programa)` | `int \| None` — menor score entre os admitidos |
| 3 | `posicao_na_fila` | `(crianca_id, programa)` | `int \| None` — 1-based |
| 4 | `reclassificar` | `(alocacao, **mudancas)` | `Reclassificacao` — `.subiram`, `.sairam`, `.desistiram`, `.desceram` |

`programa` é um `ProgramaAlocado` (`alocacao.programa(programa_id)`). As funções 2
e 3 também aceitam `(programa_id, alocacao)`.

## Rodando

Todos os comandos abaixo a partir da raiz do repo (`Hackaton_Atropic/`):

```bash
pip install -r pessoa_1/requirements.txt
pytest pessoa_1 -m "not dados_reais"   # unitários, sem I/O
python -m pessoa_1.build_data          # gera data/*.parquet dos 5 anos (~2,5s)
pytest pessoa_1                        # com os testes de dado real
pytest pessoa_1 -m "not lento"         # pula o ano inteiro
```

`pessoa_1/pytest.ini` é escopado ao próprio pacote (`testpaths = tests`) —
não interfere no `pytest` do `backend/`.

Não precisa do módulo `duckdb`: se ele não estiver instalado,
`carga.executar_duckdb` cai no binário `duckdb` do PATH. Útil em plataformas sem
wheel — foi assim que esta suíte foi validada (Python do MSYS2, `mingw_x86_64`).

## Fluxo

```
QueryB (respostas) ──┐
                     ├─► calcular_score ──► Score ──┐
QueryC (régua)   ────┘                              │
                                                    ├─► deferred_acceptance ──► Alocacao
opcoes.parquet (preferências) ──► Candidato ────────┤                              │
programas.parquet (vagas) ──────► Programa ─────────┘                              │
                                                                                   ▼
                                        nota_corte_atual · posicao_na_fila · reclassificar
```

## Decisões que importam

**A régua é sempre por ano.** `perg_id = 2` ("a criança tem alguma deficiência?")
valia 100 pontos de 2021 a 2023 e passou a 25 em 2024, e o questionário foi
redesenhado entre esses dois anos — das 13 perguntas de 2023 só 3 sobreviveram.
`calcular_score` devolve `Score.ignoradas` com os `ich_perg_id` que não existem na
régua recebida: se vier cheio, a régua está no ano errado.

**Critério de desempate não é ponto.** Na Query C, `perg_criterio = 'Sim'`
(equivalente a `perg_pontuacao = 0`) marca pergunta que não soma. Vai para
`Score.desempates`, e entra na ordenação depois do score.

**Programa = (ano, unidade, grupamento, horário).** É nesse grão que a vaga
existe: o mesmo EDI tem fila separada para Berçário Integral e Berçário Parcial.
Chave montada por `contrato.montar_programa_id`.

**A fila não é "todo mundo que listou o programa".** Quem já ficou numa opção que
prefere a esta não sobe se abrir vaga aqui — então não ocupa lugar na fila. A fila
é exatamente o conjunto que aceitaria a vaga, ordenado por prioridade. Pela
estabilidade do DA, todos ali foram de fato rejeitados por este programa.

**`reclassificar` roda o DA inteiro, não "chama o próximo".** Uma desistência
libera uma vaga que pode ser preenchida por quem hoje está numa opção pior — e
essa pessoa libera a vaga dela, que puxa outra. A cascata é o resultado que
importa.

**Desistir de uma opção ≠ sair do processo.** `desistencias=[(crianca, programa)]`
remove só aquele programa da lista de preferências — a criança continua
concorrendo nas outras. `saidas=[crianca]` tira ela do processo.

**Desistência não é monotônica para terceiros — e isso surpreende.** Quem desiste
de uma opção segue no processo com o score inteiro, desce para a própria 2ª opção
e *desloca alguém de lá*. Esse deslocado pode cair na vaga que acabou de vagar e
passar na frente do 1º da fila. Nos dados de 2025 é exatamente o que acontece no
programa mais disputado (`2025|0716601|Maternal II|Integral`, 6 vagas, 423 na
fila): o desistente de score 84 vai para a 2ª opção dele, desloca um de score 76,
e esse 76 fica com a vaga — não o 1º da fila, de score 60.

Consequência prática para a convocação: **não se pode prometer à família que ela é
"a próxima" com base na posição de hoje**, se a vaga vier de uma desistência. O
que continua garantido é que a vaga vai para o melhor classificado entre quem a
aceitaria.

`.desceram` separa terceiros que pioraram de quem desceu por escolha própria
(`.desistiram`). Ele é sentinela apenas para `saidas` e aumento de vagas — nesses
dois casos tem que vir vazio, e o motor é testado contra isso nos dados reais.

## Premissas a confirmar com a SME

1. **Ordem dos desempates.** `contrato.DESEMPATE_ORDEM` está como
   `(26 irmão na creche, 1 mãe adolescente)`, depois inscrição mais antiga. A
   Resolução SME nº 542/2025 cita "desempates" sem fixar a ordem no material do
   hackathon. **Isto é um chute informado.**
2. **`vagas` é ocupação observada, não capacidade parametrizada.** As bases do
   hackathon não trazem o parâmetro de vagas da SME, então
   [build_data.py](build_data.py) deriva `vagas` de quantas crianças distintas
   terminaram o processo com vaga no programa. Substituir pelo parâmetro real
   quando ele estiver disponível.
3. **Score por inscrição, não por opção.** As opções de uma inscrição
   compartilham o score. Criança com mais de uma inscrição no mesmo ano (polos
   diferentes) tem as opções concatenadas e fica com o maior score. **Não é caso
   raro: 38.765 pares (criança, ano) nos 5 processos.** Se a regra da SME for
   tratar cada inscrição como concorrente independente, isso muda o resultado —
   `build_data` reporta o número em `criancas_multi_inscricao`.
4. **`resp_confirmado` é ignorado.** A Query B tem `confirmado` além de
   `resposta`, e 12,4% das linhas vêm `Sim`. O score aqui usa `resposta`. Se a
   regra oficial for pontuar só critério confirmado, é uma linha em
   [score.py](score.py) — e muda o número para muita gente. É exatamente o
   problema que o desafio do hackathon quer resolver (validação automática dos
   critérios em vez de comprovação manual).

## Em construção — score por vulnerabilidade + distância

Linha de trabalho separada, ainda não integrada às quatro funções acima.
`vulnerabilidade.calcular_score(candidato, programa)` devolve **só o número**
(`float`), soma ponderada de duas peças pequenas e testáveis isoladamente:

```python
score = peso_vulnerabilidade * pontuacao_vulnerabilidade(candidato)   # conta perguntas 'Sim', sem peso
      + peso_distancia       * pontuacao_distancia(menor_distancia)   # 1.0 na porta, decai a 0 em alcance_km
```

**`Candidato` e `Programa` são tipos únicos, em `modelos.py`** — usados tanto
pelo motor da régua quanto por esta linha. Até pouco atrás `vulnerabilidade.py`
tinha os seus próprios: um `Candidato` com um dict de flags separado guardando
a mesma informação que `Score` já guarda, e um `Escola` (identidade +
localização + vagas) representando a mesma noção de "onde a vaga existe" que
`Programa` já representa. `pontuacao_vulnerabilidade` deriva direto de
`Score.detalhe` + `Score.desempates` (a união das duas é toda pergunta de
vulnerabilidade que a família confirmou, pontuada ou só critério) — conta
**perguntas**, não pontos: uma pergunta que vale 51 na régua conta 1 aqui,
igual a uma que vale 2.

Ranquear por `Programa` (não por escola inteira) também é mais correto: vagas
são por grupamento/turno, não por prédio — a mesma unidade tem fila separada
para Berçário Integral e Maternal II Parcial. `Programa.localizacao` é o único
campo que só esta linha usa — o motor da régua nunca olha para ele.

`Candidato.localizacoes` e `Programa.localizacao` são opcionais (`None` por
padrão — "sem dado geocodificado"); o candidato tem duas `Localizacao` quando
disponíveis (usa-se a mais próxima do programa), o programa tem uma.
`menor_distancia_km` levanta erro claro se chamado com um candidato ou
programa sem localização, em vez de inventar uma distância. Distância é
haversine em linha reta ([localizacao.py](localizacao.py)), não rota real.
Pesos e `alcance_km` são parâmetros com default, não um contrato fixo — ainda
não decidimos se isso substitui a régua da SME, entra como critério paralelo,
ou se junta ao `Score` que o Deferred Acceptance consome. Isso é a próxima
decisão, via o "contrato externo" mencionado.

**Cada programa tem sua própria classificação.** `ProgramaClassificado` = um
`Programa` + os candidatos que o listaram, já ordenados pelo `calcular_score`
acima (melhor primeiro). É montada por `classificar_programa(programa,
candidatos)`, uma função pura — o `Programa` em si continua um valor pequeno
(id + localização + vagas), sem saber quem se candidatou a ele. É o mesmo
desenho que `modelos.Programa`/`ProgramaAlocado` já usa no motor da régua: o
valor fica pequeno e reutilizável, e quem cruza valor + candidatos é uma
função separada. `posicao_na_fila(crianca_id, programa_classificado)` funciona
igual à função homônima em `fila.py`, só que sobre este ranking em vez do
`Score` da régua.

**Empate é resolvido por sorteio.** `classificar_programa(..., semente=42)` —
com `semente`, o sorteio é reproduzível (mesma lista + mesma semente = mesma
ordem, testável); sem ela, cada chamada pode sortear uma ordem diferente entre
os empatados — deixa de ser determinística de propósito. O sorteio só decide
*entre* empatados: quem tem score maior sempre fica na frente, qualquer que
seja a semente.

**`adicionar_candidato(programa_classificado, candidato)` coloca UM candidato
na lista já existente**, na posição que o score dele determina. Por baixo,
refaz o ranking inteiro (chama `classificar_programa` de novo com a lista + o
novo candidato) em vez de calcular a posição e inserir direto — porque não
guardamos o sorteio de empate de quem já estava na lista, então se o novo
candidato empatar com alguém, a única forma correta de decidir é resortear o
grupo empatado. No tamanho de um programa isso é barato. Falha se a criança já
estiver na classificação.

**`remover_candidato(programa_classificado, crianca_id)` tira uma criança da
lista** (desistência, saída do processo) — inverso de `adicionar_candidato`.
Diferente de adicionar, remover não precisa resortear nada: a ordem relativa
de quem fica não muda quando alguém sai, então é só um filtro. Falha
(`KeyError`) se a criança não estiver na classificação.

**Cuidado ao escrever teste contra este ranking: empate é fácil de criar por
acidente.** `Candidato(crianca_id, score=Score(total=0))` sem flags nem
distância customizada empata com qualquer outro candidato igual (mesma
vulnerabilidade zero, mesma distância zero) — o sorteio decide a ordem, então
uma asserção de lista exata (`== ["a", "b"]`) fica flaky se os scores não
forem distintos. Isso já aconteceu várias vezes nos testes deste módulo; a
correção sempre foi a mesma: dar aos candidatos scores inequívocos (flags ou
distância diferentes) quando o teste depende da ordem.

**`Programa.vagas` tem default 0** ("não informei" nunca significa
"ilimitado") — mesma convenção que `Escola` tinha antes de unificar.
`ProgramaClassificado` guarda o score de cada candidato em `scores` (não só a
ordem), porque `nota_corte_atual` precisa do número exato usado na
classificação — recalcular com pesos diferentes por engano faria o corte
mentir. A partir de `programa.vagas`, `ProgramaClassificado` expõe
`admitidos`/`fila`/`vagas_ocupadas`/`vagas_livres`/`lotado`, e
`nota_corte_atual(programa_classificado)` é o menor score entre os admitidos —
mesmas ressalvas do `nota_corte_atual` da régua oficial (`None` sem admitido;
não é barreira real se `vagas_livres > 0`). `classificar_programa` também
passou a rejeitar `crianca_id` duplicado, mesma regra do
`deferred_acceptance`.

**Geocodificação da unidade já resolvida** — `build_data.py` cruza
`OferecimentosEvagas/Unidades_Unificadas_com_Localizacao.xlsx` (base auxiliar
da SME, fora da extração Query A/B/C) e popula `Programa.localizacao` de
verdade (~57% dos programas casam por `unidade`; o resto fica `None`, sem
inventar coordenada). **Ainda falta a localização do lado da família**:
`Candidato.localizacoes` continua `None` — as bases só têm bairro/CEP em
texto, sem lat/lon do responsável, e não há uma base auxiliar equivalente
para isso ainda.

O "`reclassificar` equivalente" saiu da lista de pendências — virou o motor
de rodadas abaixo, que é o formato real do processo (multi-ciclo), não uma
reclassificação pontual.

## Motor de rodadas (`rodadas.py`)

O processo real não é uma classificação única: é um ciclo de **rodadas**. A
cada rodada, a família se inscreve com preferências (novas a cada rodada,
não as mesmas de antes); diariamente uma página de classificação mostra
posição/situação; depois de uma janela (ex.: 5 dias) a rodada fecha — quem
tem vaga é notificado, quem não tem entra na rodada seguinte com preferências
novas, sobre a capacidade que sobrou. Repete até a última rodada, decidida
por fora (calendário) — o motor não sabe quantas rodadas vai ter.

**A peça nova é a prioridade.** No motor da régua (`deferred_acceptance.py`),
a prioridade de uma criança é a mesma em qualquer programa (só depende do
`Score.total`, que não varia por escola). Aqui, cada rodada usa
`vulnerabilidade.calcular_score(candidato, programa)` como prioridade — e
como a distância muda de programa para programa, **a mesma dupla de
candidatos pode inverter de ordem entre dois programas** (quem mora perto de
A ganha A; quem mora perto de B ganha B, mesmo que os dois preferissem A).
Isso não é possível com um rank global pré-calculado, então
`deferred_acceptance_por_pontuacao` reescreve o miolo do algoritmo: cada
proposta é comparada com a pontuação calculada NAQUELE momento, para aquele
par — não um rank fixo de antemão.

`ProgramaAlocado` ganhou um campo `scores` (opcional, `None` por padrão) só
para isso: guarda a pontuação exata usada para admitir cada criança naquele
programa, porque recalcular com pesos diferentes por engano faria o corte
mentir (mesmo motivo do `scores` em `ProgramaClassificado`). É por isso que
`rodadas.nota_corte_atual`/`posicao_na_fila` são funções **próprias deste
módulo** — as de `fila.py` leem `Score.total` e dariam um número errado aqui.
`rodadas.nota_corte_atual` levanta erro claro se receber um `ProgramaAlocado`
que veio do motor da régua (`scores=None`), em vez de silenciosamente devolver
um número sem sentido.

**`programas_para_proxima_rodada(alocacao)`** monta os `Programa` da rodada
seguinte: os mesmos, com `vagas` = `vagas_livres` da rodada que fechou — quem
já entrou não compete de novo.

**`alocar_vagas_remanescentes(candidatos, programas)`** é a última rodada,
que é qualitativamente diferente das outras: o objetivo deixa de ser
"respeitar a preferência da família" (já tentado sem sucesso nas rodadas
anteriores) e vira "não deixar vaga vazia". Por isso ela **ignora**
`Candidato.preferencias` e aloca greedy pelo programa de menor distância
entre os que ainda têm vaga, atendendo por `pontuacao_vulnerabilidade`
decrescente (empate por sorteio). Não é Deferred Acceptance — sem
preferências não há estabilidade a garantir, é só um preenchimento por
proximidade. Devolve `{crianca_id: programa_id}`, não uma `Alocacao` — quem
não coube simplesmente não aparece no dict.

Este motor **não decide calendário, não notifica, não guarda estado entre
chamadas** — cada rodada é uma chamada pura. Orquestrar quando abre/fecha uma
rodada e quantas existem é responsabilidade de quem chama (o backend).

## Trocando o pipeline

`contrato.py` é o único lugar com nome de coluna. `build_data.py` existe porque o
`01_build_aggregates.py` do pipeline não está no repositório — se ele entrar,
apague `build_data.py` e ajuste `contrato.py`. Para trocar o motor de DA, faça
`deferred_acceptance` devolver uma `Alocacao`; o resto do pacote não olha para
dentro dele.
