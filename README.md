# Match Carioca

Motor de alocação de vagas de creche para a SME-Rio, com dois perfis de consulta.
Protótipo do **Claude Impact Lab Rio #2**.

Substitui a classificação **por opção** (atual) por uma alocação **por criança**
via Deferred Acceptance, e mede o resultado contra o processo real de 2025.

---

## ⚠️ Qual é o motor oficial

**O motor canônico é `backend/engine/`** — é ele que a API (`/motor/*`) usa e é
dele que saem todos os números do pitch.

O repositório contém mais de uma implementação de classificação, por termos
trabalhado em paralelo. Para não haver dúvida:

| Pasta | O que é | Usado pela API? |
|---|---|---|
| **`backend/engine/`** | **Motor oficial.** Deferred Acceptance (Gale–Shapley), desempate por loteria única reproduzível, sobre `backend/data/*.parquet` (commitado, não regenerado a cada deploy). | ✅ **sim** — via `backend/app/engine_service.py` |
| `pessoa_1/` | Motor alternativo do Miguel: mesmo Deferred Acceptance, mas desempate pelos critérios reais da régua (irmão já matriculado, mãe adolescente) + antiguidade da inscrição, em vez de loteria. Esteve no ar entre 30/08 ~15h e ~15h50 — revertido para `backend/engine/` por dois motivos: (1) todo o material do pitch já escrito (inclusive o caso 0716601, corte 59/fila 343) foi validado contra `backend/engine/`, e re-auditar contra o motor novo não cabia no tempo restante; (2) o cold start no Render subiu de ~29s para ~170s com o build gerando os parquets a cada deploy. **Candidato natural para a próxima versão** — é mais fiel à régua real da SME — assim que houver tempo para revalidar os números e resolver o cold start (ex.: comitar os parquets gerados em vez de rebuildar). Nenhum trabalho do Miguel foi apagado: o motor, o pipeline e o teste (`backend/tests/test_engine_service.py`) continuam no repo, só não são o que a API usa agora. | ❌ não (revertido) |
| `backend/app/classification_engine.py` | Régua de pontuação e fila do fluxo de inscrição **ao vivo** (SQLite), usado pelas telas de inscrição e pelo WhatsApp. Não é o motor de alocação. | ✅ só no fluxo de inscrição |

`engine/` e `classification_engine.py` operam sobre **populações diferentes** e
não se cruzam de propósito: o primeiro sobre as 62.899 crianças anonimizadas do
processo de 2025 (`aluno_anon`), o segundo sobre as inscrições criadas na demo
(`Crianca.id`).

---

## Números (rodados, não estimados)

`backend/engine/simulate.py` sobre o processo real de 2025:

| Cenário | Colocadas | % na 1ª opção | Pref. média | % vulneráveis | % demais |
|---|---:|---:|---:|---:|---:|
| Real 2025 (por opção) | 48.680 | 72,2% | 1,47 | 78,0% | 76,8% |
| **Motor oficial — `backend/engine/`** (por criança, desempate por loteria) | **47.768** | **83,9%** | **1,24** | **93,5%** | **59,2%** |
| Motor alternativo — `pessoa_1` (desempate por critérios reais) | 47.618 | 79,5% | 1,32 | 92,8% | 59,4% |

**Atendimento de famílias vulneráveis: +15,5 pp** sobre o processo real (78,0% → 93,5%).

> Estes são os números que a API serve hoje (`GET /motor/metricas`) e os que
> aparecem no material do pitch. A linha do motor alternativo é referência para
> quando ele for revalidado — não é o que está no ar.

Duas leituras necessárias para não superinterpretar:

- **O DA coloca 912 crianças a menos.** A capacidade usada é *proxy* — são as
  confirmações observadas em 2025, não vagas ofertadas. E o DA nunca aloca uma
  criança a um programa que ela não escolheu: alguns programas com assento livre
  simplesmente não recebem proposta de ninguém. É consequência de comparar com a
  mesma capacidade observada, não falha do algoritmo.
- **Não-vulneráveis caem de 76,8% para 59,2%.** É redistribuição, não ganho
  universal — o outro lado dos +15,5 pp.

### Caso de referência

`0716601|Maternal II|Integral` (CM Otávio Henrique de Oliveira, Jacarepaguá):
**6 vagas, 343 na lista de espera, corte de 59 pontos, disputa de 78× por vaga.**
No processo histórico "por opção" o corte foi de 2 pontos — ou seja, hoje uma
criança de 2 pontos entra enquanto 343 esperam, várias com 59.

Liberar **uma** vaga nesse programa gera **3 movimentos em cadeia** em 1,2s, e
uma criança que estava sem vaga nenhuma passa a ter — sem ninguém perder vaga.

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

- **Notificações são simuladas.** O Twilio está integrado no backend mas sem
  credencial neste ambiente. `/motor/notificacoes` devolve `mock: true` e um
  aviso no corpo, e a tela exibe o selo **DADOS SIMULADOS**. Crianças, programas
  e pontuações são reais; horário de envio e status de confirmação, não.
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
