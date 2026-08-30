# Frontend — Inscrição Creche RJ

HTML + CSS + JS puro. Sem framework, sem build, sem `node_modules`.

## Como abrir

- Duplo clique em `inscricao.html`, **ou**
- `python -m http.server` dentro desta pasta e abrir `http://localhost:8000/inscricao.html`

Por padrão está em **modo mock** (`USE_MOCK = true` em `api.js`) — os dados são gerados no próprio navegador, nada precisa estar no ar.

## Fluxo das 4 telas

`inscricao.html` → `verificacao.html` → `classificacao.html` → `status.html`

O `crianca_id` retornado pela inscrição é salvo em `localStorage` e propagado na URL (`?crianca_id=...`) entre as telas — dá para recarregar ou compartilhar o link de qualquer tela sem perder o contexto.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `api.js` | **Única** fronteira com o backend. Contém o mock completo (fiel ao contrato) e o fetch real. Só este arquivo muda quando o Back B publicar a API. |
| `app.js` | Utilidades compartilhadas + a lógica de cada uma das 4 telas (`App.initInscricao`, `App.initVerificacao`, `App.initClassificacao`, `App.initStatus`). |
| `styles.css` | Design system (tokens de cor/tipografia, componentes: cartões, botões, badges de status, contador regressivo, banners de erro/vazio/loading). |
| `*.html` | Uma tela cada, mobile-first. |

## Ligar na API real

Em `api.js`:

```js
const USE_MOCK = false;
const API_BASE = "https://sua-api-aqui.com"; // URL do Back B
```

Os nomes de campo em `RealApi` já seguem o contrato combinado com o time (crianca_id, preferencias, score, classificacoes, status, etc.) — não precisa mudar nada nas telas.

## Estados tratados

Cada tela trata: carregando, vazio (sem classificação ainda), erro de rede/servidor (com botão "tentar de novo"), e no caso da classificação, um **cache local** da última resposta bem-sucedida — se a API cair, a família ainda vê a última posição salva, com aviso de que pode estar desatualizada.
