🔗 **Site:** https://r15n-eng.github.io/Hackaton_Atropic/
🎥 **Vídeo:** Na raiz do  git

---

# Match Carioca

**A fila de creches do Rio, resolvida como o SISU resolve o vestibular.**

Hoje, uma família que quer matricular o filho numa creche municipal do Rio
enfrenta um processo às escuras: leva os mesmos documentos a cada escola que
escolheu, espera meses sem saber sua posição real, e só descobre o resultado
quando alguém liga — se ligar. O **Match Carioca** substitui isso por um
processo digital, com prazos fixos, visibilidade total da fila em tempo real e
um motor de alocação que aloca a **criança**, não a **opção**.

Protótipo do **Claude Impact Lab Rio #2**, rodado sobre a base real e
anonimizada da SME (2021–2025) e testado por um motor de alocação que a
própria API expõe — os números abaixo não são estimativa de pitch, são a
saída de `backend/engine/simulate.py`.

---

## O problema, com números reais

A base pública da SME (`dadoscreche-main/`, Query A/B/C, 2021–2025,
anonimizada) mostra a dinâmica do funil de inscrição ano a ano:

| Ano | Inscrições | Crianças distintas | Vagas ocupadas | Lista de espera | Cancelados | Inscrições/vaga | Taxa de ocupação |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 73.283 | 57.690 | 29.465 | 27.755 | 16.063 | 2,49 | 40,2% |
| 2022 | 64.055 | 57.820 | 35.359 | 15.118 | 13.578 | 1,81 | 55,2% |
| 2023 | 51.331 | 45.918 | 28.686 | 13.222 | 9.423 | 1,79 | 55,9% |
| 2024 | 82.690 | 71.757 | 52.068 | 14.150 | 16.472 | 1,59 | 63,0% |
| 2025 | 71.949 | 62.899 | 48.856 | 8.063 | 15.030 | 1,47 | 67,9% |

A ocupação melhorou ano a ano (40% → 68%), mas o retrato de 2025 ainda é: **de
cada 5 inscrições, 1 termina em lista de espera e mais 1 é cancelada** — sem
que a família necessariamente tenha desistido por vontade própria. Parte
relevante desse funil se perde por **desorganização do processo**, não por
falta real de vaga:

- **A família não sabe onde está.** Não existe ranking visível durante o
  processo — só depois, quando o resultado já saiu.
- **O mesmo documento, entregue várias vezes.** Quem se inscreve em até 5
  ou 6 unidades (o processo permite múltiplas opções) hoje pode ter que
  levar os *mesmos* comprovantes de vulnerabilidade a cada uma delas.
- **Redistribuição de vaga é reativa e lenta.** Quando uma família desiste ou
  não comparece, a vaga liberada volta à fila por meio de contato manual,
  sem prazo fixo — o funil de "cancelados" (2,2% a 39% das opções, conforme
  o corte, ver `dadoscreche-main/Bases IC_.../README_dicionario_dados.md`)
  mostra o tamanho do atrito.

E o caso mais direto de todos, tirado do nosso próprio motor rodando sobre
2025 (ver seção seguinte): na creche **CM Otávio Henrique de Oliveira**
(Jacarepaguá), turma Maternal II Integral, o corte **real** do processo
histórico foi de **2 pontos** — uma criança com 2 pontos entrou enquanto
**343 crianças**, várias com até **59 pontos**, ficaram na lista de espera.
Isso não é falta de vaga, é alocação **por opção, não por criança**: a vaga
foi para quem escolheu aquela opção primeiro, não para quem tinha a maior
prioridade real.

---

## A solução — como funciona

O processo é dividido em **3 etapas**, todas com prazo fixo e visíveis para a
família dentro do próprio site.

### Etapa 1 — Cadastro

O responsável cadastra quantos candidatos quiser no processo, informando
CPF, residência, local de trabalho e as vulnerabilidades de cada criança.
Dois efeitos automáticos:

- **Cruzamento de CPF com dados do governo.** O que já é público e
  verificável (Bolsa Família, CadÚnico etc.) é pré-validado automaticamente,
  em vez de depender só da palavra da família no formulário.
- **Sugestão da unidade de entrega de documentos mais próxima da
  residência.** Essa unidade **não precisa ser** nenhuma das escolas
  escolhidas para o filho — ela só centraliza o recebimento físico dos
  documentos de vulnerabilidade. Isso resolve o problema de hoje: a família
  não leva mais o mesmo comprovante a 5 escolas diferentes, leva **uma vez**,
  no lugar mais perto de casa.

### Etapa 2 — Verificação de documentos

O responsável vai à unidade escolhida na Etapa 1 com os documentos físicos.
O coordenador da unidade valida cada um **pelo próprio site**, confirmando
ou invalidando as vulnerabilidades autodeclaradas. Isso:

- evita que escolas concorridas fiquem sobrecarregadas verificando documento
  de quem, pela régua, claramente não teria prioridade ali;
- dá à família uma **data certa** para essa etapa, em vez do "vá quando
  puder" de hoje;
- gera um registro confiável — só o que foi fisicamente confirmado entra na
  classificação da Etapa 3.

A verificação em si (autenticidade de assinatura, documento físico) é e
continua sendo trabalho humano da rede — o protótipo não promete automatizar
isso, só organiza o fluxo e o prazo em volta dela.

### Etapa 3 — Classificação (o "SISU das creches")

Cada criança pode estar associada a até **5 escolas**, em ordem de
prioridade — e o sistema sugere as 5 unidades mais próximas da residência
como ponto de partida, mas a família decide a ordem final. A partir daí, o
site funciona como um SISU:

- **Ranking diário e visível.** A família vê, para cada uma das 5 escolas,
  a posição atual — classificado ou em lista de espera — *antes* de o
  processo terminar, não depois.
- **Recomendações fora da lista.** Se nenhuma das 5 opções escolhidas dá
  chance real, o sistema aponta outras unidades onde a pontuação da criança
  teria chance — sem nunca mudar a ordem de preferência que a família
  declarou por conta própria.
- **Rodadas com prazo fixo.** O período é dividido em janelas: alguns dias
  para escolha e ranking se estabilizar, depois uma janela curta e fixa para
  as escolas convocarem quem foi classificado.
- **Vaga não confirmada = vaga liberada, na hora.** Quem recusa, nega ou não
  comparece libera a vaga imediatamente para uma nova rodada — sem espera
  indefinida por uma ligação de redistribuição.
- **Última rodada prioriza proximidade.** Ao final do ciclo, o critério de
  localização (CEP da residência ou do trabalho do responsável) ganha peso
  extra, como garantia de frequência efetiva da criança.

### Encerramento do ciclo

Só perde a vaga quem de fato recusou, negou ou não compareceu numa das
rodadas — nunca quem simplesmente não sabia onde estava na fila. O ciclo é
finito: termina quando as vagas disponíveis e as crianças remanescentes se
esgotam mutuamente, com datas conhecidas desde o início.

---

## Resultados medidos — não é estimativa, é o motor rodando

`backend/engine/simulate.py` roda o algoritmo de **Deferred Acceptance**
(o mesmo tipo de mecanismo usado no SISU e no matching de residência médica)
sobre a base real e anonimizada de 2025, e compara com o resultado real
daquele ano (processo **por opção**, um por um, sem visão do todo):

| Cenário | Colocadas | % na 1ª opção | Preferência média | % vulneráveis atendidos | % demais atendidos |
|---|---:|---:|---:|---:|---:|
| Real 2025 (por opção — o processo atual) | 48.680 | 72,2% | 1,47 | 78,0% | 76,8% |
| **Match Carioca (por criança, Deferred Acceptance)** | **47.768** | **83,9%** | **1,24** | **93,5%** | **59,2%** |

**+15,5 pontos percentuais no atendimento de famílias vulneráveis** (78,0% →
93,5%), com famílias sendo atendidas, em média, mais perto do topo da sua
própria lista de preferência (1,24 vs. 1,47).

Duas leituras necessárias, para não vender número demais:

- **47.768 é menor que 48.680.** O Deferred Acceptance nunca aloca uma
  criança a um programa que ela não escolheu — a capacidade usada é a
  confirmação observada em 2025, não a vaga ofertada, e alguns programas com
  assento livre simplesmente não recebem proposta de ninguém no algoritmo.
  Não é o algoritmo perdendo vaga, é a comparação sendo honesta com a mesma
  capacidade observada nos dois cenários.
- **Não-vulneráveis caem de 76,8% para 59,2%.** É redistribuição de
  prioridade, não ganho universal — o outro lado dos +15,5 p.p.

### O caso que resume o problema

`0716601 | Maternal II | Integral` (CM Otávio Henrique de Oliveira,
Jacarepaguá): **6 vagas, 343 crianças na lista de espera, corte real do
algoritmo em 59 pontos — disputa de 78× por vaga.** No processo histórico
"por opção", o corte foi de **2 pontos**. Ou seja: hoje uma criança com 2
pontos ocupa a vaga enquanto 343 esperam, muitas com pontuação 30× maior.

E a redistribuição funciona rápido: liberar **uma única vaga** nesse
programa gera **3 movimentos em cadeia** — a próxima da fila sobe, e isso
libera espaço para a próxima, e assim por diante — calculados e notificados
em **1,2 segundo**, contra o processo manual de hoje, sem prazo definido.

---

## Qual é o motor oficial

O repositório contém mais de uma implementação de classificação, por termos
trabalhado em paralelo. Para não haver dúvida, **o motor canônico é
`backend/engine/`** — é ele que a API (`/motor/*`) usa e é dele que saem os
números acima.

| Pasta | O que é | Usado pela API? |
|---|---|---|
| **`backend/engine/`** | **Motor oficial.** Deferred Acceptance (Gale–Shapley), desempate por loteria única reproduzível, sobre `backend/data/*.parquet` (commitado, não regenerado a cada deploy). | ✅ sim — via `backend/app/engine_service.py` |
| `pessoa_1/` | Motor alternativo: mesmo Deferred Acceptance, mas desempate pelos critérios reais da régua (irmão já matriculado, mãe adolescente) em vez de loteria. Mais fiel à régua da SME, mas exigiria revalidar todo o material do pitch e resolver um cold start de ~170s no Render — candidato natural para a próxima versão, nada foi apagado. | ❌ não (revertido, ver histórico) |
| `backend/app/classification_engine.py` | Régua de pontuação e fila do fluxo de inscrição **ao vivo** (SQLite), usado pelas telas de inscrição e pelo WhatsApp do protótipo. Não é o motor de alocação. | ✅ só no fluxo de inscrição |

`engine/` e `classification_engine.py` operam sobre **populações diferentes**
e não se cruzam de propósito: o primeiro sobre as 62.899 crianças anonimizadas
do processo real de 2025 (`aluno_anon`), o segundo sobre as inscrições criadas
na demo do fluxo ao vivo (`Crianca.id`).

---

## Impacto esperado — tempo, ociosidade e equidade

Estes três pontos combinam o desenho do processo (estrutural, não medido)
com os números acima (medidos, reais):

- **Tempo da família.** Hoje, uma família com 5 preferências pode precisar
  levar o mesmo comprovante de vulnerabilidade a 5 endereços diferentes. No
  Match Carioca, ela leva **uma vez**, à unidade mais próxima de casa — os
  outros 4 deslocamentos deixam de existir por desenho, não por otimização.
- **Ociosidade de vaga.** O caso `0716601` mostra o custo do sistema atual:
  uma vaga ocupada por quem tem 2 pontos enquanto 343 crianças com pontuação
  muito maior esperam — não é uma vaga vazia, mas é uma vaga **mal alocada**.
  A reclassificação automática (3 movimentos em cadeia por vaga liberada, em
  1,2s) substitui a ligação manual e sem prazo de hoje por uma fila que se
  redistribui sozinha, na velocidade de um clique.
- **Equidade.** +15,5 p.p. no atendimento de famílias vulneráveis é o número
  que mais importa aqui: o mesmo total de vagas, alocado por prioridade real
  da criança em vez de "quem escolheu primeiro", atende proporcionalmente
  muito mais quem a régua da SME existe para priorizar.

Não fizemos — e não fingimos ter feito — uma medição de horas ou de custo em
reais: a base pública não tem essa granularidade (ver limitações abaixo). O
que está medido é o que o motor realmente produz sobre dados reais; o resto
é a lógica direta do desenho do processo.

---

## Como rodar

O backend ocupa a porta 8000, então sirva o front em outra:

```bash
# terminal 1 — backend + motor
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
./.venv/Scripts/python.exe seed_data.py
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# terminal 2 — frontend
cd frontend
python -m http.server 8080
```

- Perfil Família → http://localhost:8080/familia.html
- Perfil SME/CRE → http://localhost:8080/sme.html
- API (Swagger) → http://localhost:8000/docs

Validar os números do motor:

```bash
cd backend && ./.venv/Scripts/python.exe engine/simulate.py
```

---

## Estrutura

```
backend/
  engine/          MOTOR OFICIAL — deferred_acceptance.py, simulate.py
  pipeline/         geração dos agregados a partir da base bruta da SME
  data/             opcoes.parquet, programas.parquet (anonimizados, commitados)
  app/
    engine_service.py   ponte motor -> API (objetos criança / programa / reclassificação)
    main.py             FastAPI: /motor/* (motor) + fluxo de inscrição e WhatsApp
    classification_engine.py  régua do fluxo de inscrição ao vivo (SQLite)
frontend/
  familia.html      perfil Família — consulta somente-leitura
  sme.html          perfil SME/CRE — classificação, reclassificação, notificações
  motor.css         identidade visual
  motor-api.js      fronteira com /motor/*
  inscricao.html … status.html   fluxo de inscrição em 4 telas (demo ao vivo)
pessoa_1/           motor paralelo do Back A (não usado pela API)
dadoscreche-main/   base bruta da SME + análise exploratória
```

---

## Endpoints do motor

| Método | Rota | Retorna |
|---|---|---|
| GET | `/motor/metricas` | números gerais da alocação |
| GET | `/motor/programas` | catálogo (unidade × grupamento × turno) |
| GET | `/motor/programa?programa=…` | corte, ocupação, alocadas e lista de espera |
| GET | `/motor/crianca/{aluno_anon}` | status, pontuação, opções, posição na fila |
| GET | `/motor/criancas-exemplo` | amostra para o seletor da tela Família |
| POST | `/motor/reclassificar/{aluno_anon}` | diff de quem sobe ao liberar uma vaga |
| GET | `/motor/notificacoes` | timeline de envios (**`mock: true`** — ver abaixo) |

---

## Roadmap — desenhado, não implementado

Está fora do protótipo de propósito, por tempo e risco. **Nenhuma tela simula
estas funções como se estivessem prontas** — onde aparecem, aparecem como texto
explicativo da regra da SME, não como funcionalidade.

- **Ciclo de rodadas semanais** (fase de ranking + fase de chamada, estilo SISU).
  Hoje o motor roda uma alocação completa e a reclassificação é sob demanda.
- **Recálculo de pontuação na comprovação de documentos.** A tela de verificação
  lista os critérios declarados e explica a regra ("critério não comprovado sai
  do cálculo"), mas o sistema não confere documento nem recalcula — e a tela diz
  isso, em vez de fingir que confere.
- **Contagem de prazo real** (7 dias para trocar, prazo de resposta à
  convocação). A janela aparece como informação, não como cronômetro com efeito.

## Limitações declaradas

- **Notificações são simuladas.** O envio por WhatsApp está integrado no
  backend (Meta WhatsApp Cloud API), mas as credenciais não estão configuradas
  neste ambiente. `/motor/notificacoes` devolve `mock: true` e um aviso no
  corpo, e a tela exibe o selo **DADOS SIMULADOS**. Crianças, programas e
  pontuações são reais; horário de envio e status de confirmação, não.
- **Não existe status "fora".** Das 62.899 crianças, 15.131 não são alocadas — e
  **todas** estão em alguma lista de espera. A tela Família tem 2 estados, não 3.
- **`cadunico` é derivado, não é coluna.** Na régua de 2025 o CadÚnico vale 51
  dos 100 pontos e é o único critério ≥ 51, então `score >= 51` identifica quem
  o declarou. Se a régua mudar de ano, a derivação muda junto.
- **Nome de unidade casa em ~58%** das unidades (488 de 836). Onde não casa, a
  interface mostra o código — não inventa nome.
- **Desempate por loteria única, não pelos critérios documentais da régua.**
  O motor oficial (`backend/engine/`) desempata por sorteio único e reproduzível
  — é determinístico, auditável e à prova de estratégia (declarar a preferência
  verdadeira é sempre a melhor jogada). Ele **não** usa os critérios reais de
  desempate da SME (irmão já matriculado, responsável menor de 18 anos), que
  existem nos dados históricos e são explorados pelo motor alternativo
  (`pessoa_1`, ver tabela acima) — não trocamos para ele nesta entrega por
  falta de tempo para revalidar os números contra o material já escrito.
- **Autenticação mínima.** Há login por telefone com código via WhatsApp para a
  família voltar de outro aparelho, mas o painel SME/CRE não tem autenticação
  nenhuma — é protótipo de demonstração, não sistema em produção.
- **Não há tempo de espera, distância exata nem renda** — esses dados não
  existem na base anonimizada e não são exibidos em nenhuma tela.

---

## Sobre os dados

Base anonimizada pela SME (aleatorização, generalização e supressão).
**Os indicadores não representam a realidade** — ilustram a dinâmica do processo
de inscrição em creche entre 2021 e 2025.

Este é um protótipo de hackathon inspirado na identidade visual da Prefeitura do
Rio. Não é serviço oficial da Prefeitura nem extensão do site matricula.rio.
