# Frontend — Match Carioca

HTML + CSS + JS puro. Sem framework, sem build, sem `node_modules`.

## Como abrir

O front hoje está **ligado na API real** (`USE_MOCK = false`, `API_BASE = http://localhost:8000`).
O backend ocupa a porta 8000, então **sirva o front em outra porta**:

```bash
# terminal 1 — backend (porta 8000)
cd ../backend && ./.venv/Scripts/python.exe seed_data.py
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# terminal 2 — front (porta 8080)
cd frontend && python -m http.server 8080
# abrir http://localhost:8080/inscricao.html
```

> Abrir por duplo clique (`file://`) **não funciona mais** com a API ligada: o
> navegador bloqueia o fetch por CORS em origem `file://`. Use o servidor local.

### Plano B: voltar para o mock em segundos

Se a API cair (ou não houver rede na hora da demo), troque **uma linha** em `api.js`:

```js
const USE_MOCK = true;
```

Tudo volta a funcionar 100% offline, sem backend nenhum — inclusive o caso de
demonstração de Jacarepaguá com os números reais de 2025. O código do mock é
mantido de propósito, não é código morto.

## Fluxo das 4 telas

`inscricao.html` → `verificacao.html` → `classificacao.html` → `status.html`

O `crianca_id` retornado pela inscrição é salvo só em `localStorage` deste aparelho — nunca aparece na URL, para não vazar em histórico do navegador, print de tela ou link compartilhado. Dá para recarregar qualquer tela sem perder o contexto; para acompanhar de outro aparelho, a família usa o login por telefone (`login.html`), que não depende do id.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `api.js` | **Única** fronteira com o backend. Contém o mock completo (fiel ao contrato) e o fetch real. Só este arquivo muda quando o Back B publicar a API. |
| `app.js` | Utilidades compartilhadas + a lógica de cada uma das 4 telas (`App.initInscricao`, `App.initVerificacao`, `App.initClassificacao`, `App.initStatus`). |
| `styles.css` | Design system (tokens de cor/tipografia, componentes: cartões, botões, badges de status, contador regressivo, banners de erro/vazio/loading). |
| `*.html` | Uma tela cada, mobile-first. |

## Ligar na API real

Já está ligada. Para apontar para outra URL (ex.: quando o Back B publicar), em `api.js`:

```js
const USE_MOCK = false;
const API_BASE = "https://sua-api-aqui.com"; // URL do Back B
```

`RealApi` traduz o contrato do backend (`programa_id` numérico, `faixa_etaria`,
`nota_corte_atual`...) para o formato que as telas usam — nenhuma tela muda.

## Diferença entre o mock e a API real (importante para a demo)

Verificado ponta a ponta em 30/08/2026, com o backend rodando de verdade:

| | Mock | API real |
|---|---|---|
| Régua 2025 (13 perguntas, teto 100) | ✅ | ✅ (`classification_engine.REGUA_PADRAO`) |
| 30 unidades reais | ✅ | ✅ (via `GET /programas`) |
| Nota de corte histórica de 2025 | ✅ (2 em 0716601, 53 em 0716603) | ❌ — ver abaixo |
| Fila com a demanda real (483 famílias) | ✅ | ❌ — só quem está no SQLite local |

**Por que o caso Jacarepaguá não se reproduz na API real:** o backend calcula
`nota_corte_atual` como *o menor score entre quem já foi selecionado naquele
programa*. Num banco recém-populado, ninguém foi selecionado ainda → o corte é
`null` e a fila tem só as crianças cadastradas na sessão. O resultado real fica
"1ª de 1, dentro" em qualquer unidade, em vez de "4ª de 483, dentro" vs "13ª de
259, fora".

Isso **não é um bug do front nem da API** — falta carregar no banco a fila
histórica de 2025 (as ~483 opções por programa) ou o motor do Back A que lê os
Parquets. Para a demo do caso de equidade, use o modo mock.

## Estados tratados

Cada tela trata: carregando, vazio (sem classificação ainda), erro de rede/servidor (com botão "tentar de novo"), e no caso da classificação, um **cache local** da última resposta bem-sucedida — se a API cair, a família ainda vê a última posição salva, com aviso de que pode estar desatualizada.
