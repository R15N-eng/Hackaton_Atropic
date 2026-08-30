# Back B — API + WhatsApp (fila de creches)

Implementação da **Pessoa 2** do time: uma API FastAPI com persistência em
SQLite, que cobre as 4 etapas do processo (inscrição, verificação de
documentos, classificação, matrícula) e integra a WhatsApp Cloud API (Meta)
para: confirmação de inscrição, convocação quando a criança é selecionada,
**inscrição feita 100% pelo WhatsApp** e **verificação mensal do número de
telefone do responsável**.

## O que foi feito

### Estrutura

```
backend/
  app/
    main.py                  endpoints da API (FastAPI)
    models.py                tabelas SQLite (SQLAlchemy)
    schemas.py                contrato de entrada/saída (Pydantic) da API
    crud.py                   criação de inscrição (usada pelo site e pelo WhatsApp)
    whatsapp.py               cliente da WhatsApp Cloud API, templates de mensagem, maquina
                               de estados da inscrição por WhatsApp, verificação mensal
    classification_engine.py  motor de pontuação/fila (stub — ver seção de integração)
    scheduler.py              job mensal automático (APScheduler)
    config.py / database.py   configuração e conexão com o banco
  tests/                      pytest, com a Cloud API mockada (não faz chamada real)
  seed_data.py                popula 3 creches de exemplo para testar manualmente
  requirements.txt
  .env.example
```

### Modelo de dados (SQLite)

- **Programa** — uma unidade/creche (nome, bairro, endereço, capacidade, faixas etárias, turnos).
- **Crianca** — uma inscrição: dados da criança e do responsável, telefone (WhatsApp),
  respostas do questionário de vulnerabilidade, `score`, `status`
  (`inscrito` → `verificacao_documentos` → `classificado` → `selecionado` →
  `matriculado`, ou `cancelado`), canal de inscrição (`site`/`whatsapp`),
  unidade escolhida e data da escolha (para a janela de troca de 7 dias).
- **Preferencia** — até 5 unidades de preferência por criança, em ordem.
- **Notificacao** — log de toda mensagem de WhatsApp enviada (sucesso ou falha),
  usado para auditoria e para nunca derrubar a API por causa da Cloud API.
- **WhatsappSessao** — estado da conversa por número de telefone, usado pela
  inscrição feita via WhatsApp.

### Endpoints

| Método | Rota | Etapa | O que faz |
|---|---|---|---|
| POST | `/inscricao` | 1 | Cria a inscrição (site). Envia WhatsApp de confirmação. |
| POST | `/verificacao_documentos/{crianca_id}` | 2 | Define a unidade (a informada, se estiver nas preferências, ou força a 1ª preferência como "mais próxima disponível" — ver TODO da Pessoa 1). |
| GET | `/classificacao/{crianca_id}` | 3 | Posição na fila da unidade escolhida, nota de corte atual, sugestões nas outras preferências, e se ainda pode trocar de escola (janela de 7 dias). |
| POST | `/escolher_unidade` | 3 | Troca a unidade escolhida entre as preferências, respeitando a janela de 7 dias. |
| POST | `/avancar_processo` | 3/4 | Muda o status (`classificado`, `selecionado`, `matriculado`, `cancelado`). Ao virar `selecionado`, dispara a convocação por WhatsApp. Ao liberar uma vaga (`cancelado`/`matriculado`), roda a reclassificação e avisa quem subiu na fila. |
| GET | `/programa/{id}`, `/programas` | — | Dados da unidade + nota de corte atual. |
| GET/POST | `/whatsapp/webhook` | 1 e extra | Webhook da Meta: GET faz a verificação de assinatura do webhook, POST recebe as mensagens (inscrição por WhatsApp, resposta a `STATUS`, resposta à verificação mensal de telefone). |
| POST | `/jobs/verificar_telefones` | extra | Dispara manualmente a verificação mensal (útil para demo, sem esperar 30 dias). |
| GET | `/health` | — | Healthcheck. |

### Features extras pedidas (além do contrato original da Pessoa 2)

**1. Inscrição via WhatsApp.** O webhook (`/whatsapp/webhook`) reconhece uma
conversa nova (ou a palavra `INSCRICAO`) e conduz uma máquina de estados
(`app/whatsapp.py:iniciar_ou_continuar_inscricao`) que pergunta, uma
mensagem por vez: nome da criança, data de nascimento, nome do responsável,
bairro, CEP, a unidade de preferência (por número da lista) e as perguntas
de vulnerabilidade (sim/não). Ao final, cria a mesma `Crianca` que o
endpoint `/inscricao` criaria — as duas portas de entrada (site e WhatsApp)
passam pela mesma função em `app/crud.py`, então não há regra de negócio
duplicada.

**2. Verificação mensal do telefone.** `app/whatsapp.py:disparar_verificacao_mensal_telefone`
varre as inscrições ativas cujo telefone não é confirmado há mais de 30 dias
(`config.INTERVALO_VERIFICACAO_TELEFONE_DIAS`) e envia: *"Este ainda é o seu
número de WhatsApp? Responda SIM ou envie o novo número."* A resposta é
tratada no mesmo webhook: `SIM` confirma; um número novo (validado por regex)
atualiza o cadastro; qualquer outra coisa pede para repetir. Isso roda
automaticamente todo mês via APScheduler (`ENABLE_SCHEDULER=true` no `.env`),
e também pode ser disparado a qualquer momento em `POST /jobs/verificar_telefones`
(sem essa opção, testar a automação real levaria um mês).

### Integração com a WhatsApp Cloud API (Meta)

`app/whatsapp.py:enviar_whatsapp` centraliza todo envio (chamada HTTP direta
ao `graph.facebook.com`, sem SDK). Se a Cloud API falhar (token expirado,
número de destino não verificado no modo de teste, número inválido) **a API
não quebra**: o erro é capturado, registrado na tabela `Notificacao` com
`status="falhou"` e `erro=<mensagem>`, e a request que disparou o envio
continua normalmente (ex.: a inscrição é criada mesmo que o WhatsApp de
confirmação falhe).

### Motor de classificação (`classification_engine.py`)

A Pessoa 1 (Back A) está construindo o motor real (DuckDB + Deferred
Acceptance sobre `opcoes.parquet`/`programas.parquet`). Para não bloquear o
desenvolvimento da API nele, este arquivo já implementa as **mesmas 4
assinaturas de função** com uma versão simples e funcional sobre o SQLite
local:

```python
calcular_score(respostas, regua_do_ano=None) -> float
nota_corte_atual(programa_id, db) -> float | None
posicao_na_fila(crianca_id, programa_id, db) -> tuple[int, int]
reclassificar(db) -> list[int]
```

Ver seção **"Como integrar com a Pessoa 1"** abaixo.

## Como testar

### 1. Instalar e configurar

```bash
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Mac/Linux

cp .env.example .env   # preencha as credenciais da Meta WhatsApp Cloud API (opcional p/ rodar local)
```

### 2. Rodar os testes automatizados

```bash
./.venv/Scripts/python.exe -m pytest tests/ -v
```

8 testes cobrindo: inscrição → verificação de documentos → classificação →
seleção; erro ao selecionar sem unidade escolhida; bloqueio de troca de
unidade fora da janela de 7 dias; login por telefone + código (e isolamento
entre famílias); inscrição inteira feita pelo WhatsApp; verificação mensal de
telefone (disparo + resposta `SIM`); webhook sem inscrição encontrada. A
Cloud API é mockada nos testes — nenhuma mensagem real é enviada.

### 3. Rodar a API localmente

```bash
python seed_data.py                         # cria 3 creches de exemplo
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Documentação interativa (Swagger) em `http://localhost:8000/docs`.

Fluxo manual rápido:

```bash
# 1. inscrever
curl -X POST http://localhost:8000/inscricao -H "Content-Type: application/json" -d '{
  "nome": "Maria", "data_nascimento": "2023-01-10",
  "responsavel_nome": "Joana", "responsavel_telefone": "+5521999990000",
  "bairro": "Bangu",
  "preferencias": [{"programa_id": 1, "faixa_etaria": "0-2", "turno": "manha"}],
  "respostas_vulnerabilidade": {"renda_baixa": true}
}'

# 2. verificação de documentos (define/sugere a unidade)
curl -X POST http://localhost:8000/verificacao_documentos/1

# 3. ver posição na fila
curl http://localhost:8000/classificacao/1

# 4. selecionar (dispara WhatsApp de convocação)
curl -X POST http://localhost:8000/avancar_processo -H "Content-Type: application/json" \
  -d '{"crianca_id": 1, "novo_status": "selecionado"}'
```

### 4. Testar o WhatsApp de verdade (Meta WhatsApp Cloud API)

1. Crie um app em https://developers.facebook.com/apps → tipo "Business" →
   adicione o produto **WhatsApp**.
2. Na página "API Setup" do produto, copie o **token de acesso temporário**
   e o **Phone number ID** (número de teste da Meta) para `META_WHATSAPP_TOKEN`
   e `META_PHONE_NUMBER_ID` no `.env`. Defina `META_VERIFY_TOKEN` como
   qualquer string sua (ex.: `minha-verificacao-123`).
3. Ainda em "API Setup", adicione o número de WhatsApp que vai receber as
   mensagens em "To" e verifique-o com o código recebido (modo de teste:
   limite de 5 números de destino).
4. Configure o webhook em WhatsApp → Configuration → Callback URL. Como a
   Meta precisa alcançar sua API publicamente, exponha a porta local com um
   túnel (ex.: `ngrok http 8000`) e use `<url-do-ngrok>/whatsapp/webhook` como
   Callback URL, com o mesmo valor de `META_VERIFY_TOKEN` no campo "Verify
   token". Assine o campo `messages`.
5. Envie `INSCRICAO` pelo WhatsApp (do número verificado no passo 3) para o
   número de teste da Meta — a máquina de estados da inscrição deve
   responder pergunta por pergunta.
6. Rode `curl -X POST http://localhost:8000/jobs/verificar_telefones` para
   simular a verificação mensal sem esperar 30 dias, e responda `SIM` ou um
   novo número pelo WhatsApp.

> O token temporário da Meta expira em ~24h; para uma demo mais longa, gere
> um token permanente via Business Settings → System Users.

## Como integrar com as outras pessoas

### Com a Pessoa 1 (Back A — motor de classificação)

Quando o motor real (DuckDB + `deferred_acceptance.py`) estiver pronto,
**troque só o corpo das 4 funções em `app/classification_engine.py`**,
mantendo a mesma assinatura — nenhum outro arquivo da API precisa mudar:

- `calcular_score` hoje soma pesos de um dict de respostas sim/não
  (`REGUA_PADRAO`); troque pela régua oficial do ano da Pessoa 1.
- `nota_corte_atual` e `posicao_na_fila` hoje consultam o SQLite local; a
  versão da Pessoa 1 provavelmente vai ler de `opcoes.parquet`/`programas.parquet`
  via DuckDB — se os IDs de criança/programa forem os mesmos usados aqui
  (`Crianca.id`, `Programa.id`), a troca é direta.
- `reclassificar` hoje é uma aproximação sem Deferred Acceptance real; a
  versão da Pessoa 1 deve devolver a lista de `crianca_id` que subiram, no
  mesmo formato (`list[int]`), para o aviso automático via WhatsApp continuar
  funcionando (`app/main.py`, endpoint `/avancar_processo`).
- Também dá para decidir manter os dados no SQLite (as tabelas `Crianca`,
  `Preferencia`, `Programa` já têm o suficiente para virar `opcoes.parquet`
  via `SELECT` + export) — vale alinhar com a Pessoa 1 qual lado vai gerar o
  Parquet, para não duplicar a fonte de verdade.

### Com a Pessoa 3 (Front)

O contrato da API é o que está na tabela de endpoints acima e em
`app/schemas.py` (schemas Pydantic = o JSON exato de entrada/saída). Pontos
de atenção:

- `POST /inscricao` espera `preferencias` como lista de até 5 objetos
  `{programa_id, faixa_etaria, turno}` — o front precisa primeiro carregar
  `GET /programas` para montar essa lista de escolha.
- A tela de classificação deve chamar `GET /classificacao/{crianca_id}` e
  usar `pode_alterar_escolha` (bool) para habilitar/desabilitar o botão de
  troca — não implemente a contagem de 7 dias no front, ela já vem calculada
  do back (`pode_alterar_ate`).
- Suba a API local (`uvicorn app.main:app --reload --port 8000`) e libere
  CORS se o front rodar em outra porta — **ainda não configurado**, avise se
  for necessário (adiciono `CORSMiddleware` no `main.py`).

### Com a Pessoa 4 (Design/Pitch)

- Métricas fáceis de extrair para os slides: contagem de `Crianca` por
  `status` e por `canal_inscricao` (`site` vs `whatsapp`), e a tabela
  `Notificacao` dá o total de mensagens de WhatsApp enviadas/entregues —
  útil para mostrar "X famílias avisadas automaticamente" na demo.
- Para a demo ao vivo, o roteiro sugerido é: inscrever pelo WhatsApp (mostra
  a conversa real no celular) → verificar documentos → mostrar posição na
  fila → avançar para "selecionado" e mostrar a convocação chegando no
  WhatsApp em tempo real.

## Limitações conhecidas / próximos passos

- `classification_engine.py` é um stub: pontuação e fila funcionam, mas sem
  localização geográfica nem o algoritmo de Deferred Acceptance real — isso
  é trabalho da Pessoa 1.
- "Unidade mais próxima" na verificação de documentos hoje é só a 1ª
  preferência (não há cálculo de distância geográfica ainda).
- Sem autenticação nos endpoints — ok para o hackathon, mas não é para
  produção.
- CORS não configurado — avisar se o front precisar.
