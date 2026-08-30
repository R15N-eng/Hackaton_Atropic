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
| **`backend/engine/`** | **Motor oficial.** Deferred Acceptance (Gale–Shapley) sobre `backend/data/*.parquet`. | ✅ **sim** — via `backend/app/engine_service.py` |
| `pessoa_1/` | Motor de classificação desenvolvido em paralelo pelo Back A (régua + vulnerabilidade + distância). Mantido no repo como trabalho do time. | ❌ não |
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
| **Deferred Acceptance (por criança)** | **47.768** | **83,9%** | **1,24** | **93,5%** | **59,2%** |

**Atendimento de famílias vulneráveis: +15,5 pp.**

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
- **Sem autenticação.** Os perfis são duas rotas, sem login: é protótipo de
  demonstração, não sistema em produção.
- **Não há tempo de espera, distância exata nem renda** — esses dados não
  existem na base anonimizada e não são exibidos em nenhuma tela.

---

## Sobre os dados

Base anonimizada pela SME (aleatorização, generalização e supressão).
**Os indicadores não representam a realidade** — ilustram a dinâmica do processo
de inscrição em creche entre 2021 e 2025.

Este é um protótipo de hackathon inspirado na identidade visual da Prefeitura do
Rio. Não é serviço oficial da Prefeitura nem extensão do site matricula.rio.
