# Análise — Inscrição Creche RJ (2021–2025): faixas de score e inscritos x vaga

Gerado a partir das bases oficiais em `Bases IC_ ClassificadoseFila/` (Query A, B e C). Script de apuração: `scripts/analise_creche.py` (nesta mesma pasta do projeto — cópia do script usado para gerar os números abaixo).

> ⚠️ Os dados de origem são anonimizados (aleatorização/generalização/supressão). Os números aqui **não representam a realidade** — servem para ilustrar a dinâmica do processo, como já avisa o `README.md` da base.

---

## 1. Metodologia

**Inscrição = 1 criança em 1 processo/ano.** A Query A tem uma linha por *opção de creche escolhida*; uma mesma inscrição pode ter até 6 opções (linhas). Para não contar a mesma criança várias vezes, cada inscrição foi reduzida à sua **melhor situação** entre as opções, usando a prioridade:

`Confirmado > Ativo > Selecionado > Selecionado da lista > Lista de espera > Cancelado na confirmacao > Cancelado > Cancelado pelo sistema`

**"Vaga ocupada"** = inscrição cuja melhor situação é `Confirmado`, `Ativo`, `Selecionado` ou `Selecionado da lista`. É uma aproximação a partir do desfecho da própria inscrição — a base `OferecimentosEvagas/` (monitoramento mensal de matrícula das unidades) tem granularidade e formato diferentes a cada ano (colunas e abas mudam) e não foi possível casá-la de forma confiável com os processos seletivos 2021–2025 no tempo disponível. Ou seja: "vaga" aqui significa **vaga efetivamente preenchida pelo processo seletivo daquele ano**, não a capacidade total ofertada pela rede.

**Score (pontuação) por inscrição** = soma de `perg_pontuacao` (Query C) de todas as perguntas em que a família respondeu **"Sim"** (Query B), somado por inscrição. Não foi filtrado pelo campo `confirmado` (validação da SME), então o score aqui é o **autodeclarado**, não necessariamente o valor confirmado/oficial da classificação.

**Faixas de score normalizadas.** A régua de pontuação mudou muito entre 2023 e 2024 (pontuação máxima teórica caiu de 465 para 100 pontos, e o peso de perguntas foi reescalonado — ver `README_dicionario_dados.md`). Comparar score bruto entre anos seria enganoso. Por isso as faixas abaixo são um **percentual da pontuação máxima teórica daquele ano**:

| Faixa | Critério |
|---|---|
| 0 pontos | Nenhuma resposta "Sim" pontuável |
| 1–25% do máximo | Pontuação de 1% a 25% do teto do ano |
| 26–50% do máximo | 26% a 50% do teto do ano |
| 51–75% do máximo | 51% a 75% do teto do ano |
| 76–100% do máximo | 76% a 100% do teto do ano |

Pontuação máxima teórica por ano: **2021–2023 = 465 pontos**, **2024–2025 = 100 pontos**.

---

## 2. Inscritos x vaga, por ano

| Ano | Inscrições | Crianças distintas | Vagas ocupadas | Lista de espera | Cancelados | Inscrições/vaga | Crianças/vaga | Taxa de ocupação |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 73.283 | 57.690 | 29.465 | 27.755 | 16.063 | **2,49** | 1,96 | 40,2% |
| 2022 | 64.055 | 57.820 | 35.359 | 15.118 | 13.578 | **1,81** | 1,64 | 55,2% |
| 2023 | 51.331 | 45.918 | 28.686 | 13.222 | 9.423 | **1,79** | 1,60 | 55,9% |
| 2024 | 82.690 | 71.757 | 52.068 | 14.150 | 16.472 | **1,59** | 1,38 | 63,0% |
| 2025 | 71.949 | 62.899 | 48.856 | 8.063 | 15.030 | **1,47** | 1,29 | 67,9% |

- **Inscrições/vaga** = quantas inscrições disputaram cada vaga preenchida naquele ano (quanto maior, mais concorrido).
- **Taxa de ocupação** = % das inscrições daquele ano que terminaram em vaga preenchida.
- "Cancelados" agrupa `Cancelado`, `Cancelado na confirmacao` e `Cancelado pelo sistema` (a maior parte do funil em todos os anos).

**Leitura**: a concorrência caiu de ~2,5 inscrições por vaga em 2021 para ~1,5 em 2025, e a taxa de ocupação subiu de 40% para 68%. Isso pode refletir mais vagas preenchidas, menos duplicidade de inscrição, ou mudanças no processo (não dá para separar as causas só com esta base).

---

## 3. Distribuição por faixa de score, por ano

### 3.1 Contagem de inscrições

| Ano | 0 pontos | 1–25% do máx. | 26–50% do máx. | 51–75% do máx. | 76–100% do máx. | Total |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 47.279 | 22.517 | 3.276 | 203 | 8 | 73.283 |
| 2022 | 40.721 | 20.331 | 2.817 | 176 | 10 | 64.055 |
| 2023 | 23.834 | 23.603 | 3.659 | 208 | 27 | 51.331 |
| 2024 | 26.093 | 21.070 | 33.066 | 2.394 | 67 | 82.690 |
| 2025 | 22.855 | 13.647 | 306 | 34.067 | 1.074 | 71.949 |

### 3.2 Percentual dentro de cada ano

| Ano | 0 pontos | 1–25% do máx. | 26–50% do máx. | 51–75% do máx. | 76–100% do máx. |
|---|---:|---:|---:|---:|---:|
| 2021 | 64,5% | 30,7% | 4,5% | 0,3% | 0,0% |
| 2022 | 63,6% | 31,7% | 4,4% | 0,3% | 0,0% |
| 2023 | 46,4% | 46,0% | 7,1% | 0,4% | 0,1% |
| 2024 | 31,6% | 25,5% | 40,0% | 2,9% | 0,1% |
| 2025 | 31,8% | 19,0% | 0,4% | 47,3% | 1,5% |

### 3.3 Estatísticas do score bruto (não normalizado)

| Ano | Mín. | Máx. observado | Média | Mediana | Máximo teórico |
|---|---:|---:|---:|---:|---:|
| 2021 | 0 | 465 | 32,2 | 0 | 465 |
| 2022 | 0 | 420 | 32,8 | 0 | 465 |
| 2023 | 0 | 465 | 55,6 | 10 | 465 |
| 2024 | 0 | 100 | 21,2 | 17 | 100 |
| 2025 | 0 | 100 | 27,7 | 10 | 100 |

**Leitura importante**: o salto de 2025 para a faixa "51–75% do máximo" (quase metade das inscrições) não é um sinal de que os candidatos ficaram muito mais vulneráveis — é um artefato da régua. Em 2025 a pergunta sobre CadÚnico vale sozinha **51 dos 100 pontos possíveis**; qualquer família que responda "Sim" a ela já cai nessa faixa isoladamente. Em 2024, a pergunta de maior peso (deficiência) valia só 25 pontos, então nenhuma resposta isolada empurra o candidato além de 25%. Isso confirma o alerta do dicionário de dados: **a régua não é comparável entre anos sem tratamento**, e mudanças na "faixa" refletem o desenho do formulário tanto quanto o perfil socioeconômico real.

### 3.4 Taxa de ocupação de vaga por faixa de score (dentro de cada ano)

| Ano | 0 pontos | 1–25% | 26–50% | 51–75% | 76–100% |
|---|---:|---:|---:|---:|---:|
| 2021 | 28,7% | 60,3% | 65,8% | 72,4% | 75,0% |
| 2022 | 54,2% | 56,7% | 58,4% | 64,2% | 90,0% |
| 2023 | 53,4% | 57,8% | 59,2% | 64,4% | 63,0% |
| 2024 | 61,3% | 63,0% | 64,2% | 63,3% | 71,6% |
| 2025 | 67,9% | 68,1% | 58,8% | 67,9% | 66,9% |
| _base (nº de inscrições)_ | grande em todas as faixas | grande | pequena em 2021–23/2025 | pequena, exceto 2025 | muito pequena (8–1.074) |

Em 2021–2023, ter mais pontos aumenta visivelmente a chance de ocupar vaga (28,7% → 75,0% em 2021). Em 2024–2025 essa relação praticamente desaparece — a taxa de ocupação fica entre 59% e 72% em quase todas as faixas, inclusive em "0 pontos". Some-se a isso que as faixas de 51% ou mais têm poucas inscrições em 2021–2024 (dezenas a poucas centenas) — qualquer percentual ali é estatisticamente frágil.

---

## 4. Principais achados

1. **Concorrência caindo, ocupação subindo.** De 2021 a 2025 a razão inscrições/vaga caiu de 2,49 para 1,47 e a taxa de ocupação subiu de 40,2% para 67,9% — a trajetória é monotônica ano a ano.
2. **A maioria das famílias não pontua nada.** Em 4 dos 5 anos, "0 pontos" é a faixa mais comum ou quase (31,6%–64,5% das inscrições) — a maior parte dos candidatos não se enquadra em nenhum critério de vulnerabilidade pontuável daquele ano.
3. **A reforma de 2024 redistribuiu o funil.** Até 2023 quase ninguém passava de 50% do teto (menos de 8% das inscrições); a partir de 2024 as faixas médias/altas concentram parte relevante do volume (40% em 26–50% no próprio 2024; 47,3% em 51–75% em 2025) — efeito do reescalonamento de pesos, não necessariamente de mais vulnerabilidade real.
4. **Pontuar mais ajudava mais em 2021–2023 do que em 2024–2025.** A taxa de ocupação por faixa sobe de forma clara com o score nos três primeiros anos; nos dois últimos a diferença entre faixas é pequena, sugerindo que o desempate por pontuação perdeu força relativa (ou que outros fatores — nº de vagas ofertadas, escolha de unidade — passaram a pesar mais).
5. **Cancelamento é a maior fração do funil em todos os anos** (18.722 a 34% conforme o ano, ver dicionário) — a maioria das inscrições nunca chega a disputar de fato por uma vaga; isso já é destacado no dicionário oficial da base e se confirma na apuração por inscrição.

---

## 5. Limitações

- **"Vaga" é uma aproximação** a partir da situação final da inscrição, não da capacidade real ofertada pela rede (que está em `OferecimentosEvagas/`, com granularidade mensal e esquema de colunas diferente em cada ano — não integrada aqui).
- **Score usa apenas `resposta = 'Sim'`**, sem considerar o campo `confirmado` (validação da SME). O score "oficial" usado na classificação pode diferir ligeiramente.
- **Régua de pontuação não é comparável entre 2021–2023 e 2024–2025** (mudança de perguntas e pesos) — por isso as faixas são normalizadas por % do teto de cada ano, mas mesmo assim refletem o desenho do formulário, não só o perfil das famílias.
- Base anonimizada: indicadores absolutos não representam a realidade, apenas a dinâmica relativa (conforme aviso oficial do dataset).
