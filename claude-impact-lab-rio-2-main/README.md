# Claude Impact Lab — Rio de Janeiro

Bem-vindos à **segunda edição do Claude Impact Lab Rio** — um hackathon de um dia em parceria com a Prefeitura do Rio de Janeiro, focado em construir soluções com IA para um desafio real de **educação pública** da nossa cidade.

Este não é um hackathon comum. O problema vem diretamente do governo municipal e os melhores projetos têm chance real de serem adotados para melhorar a vida de milhares de crianças no Rio.

## 🗓️ Agenda

| Horário      | Momento                                     |
| ------------ | ------------------------------------------- |
| 8h30         | Briefing do desafio                         |
| 9h00         | Início do hackathon com apoio dos mentores  |
| 12h às 13h   | Almoço servido (não precisa parar)          |
| **16h30**    | **Prazo de entrega dos projetos no GitHub** |
| 16h30        | Palestras no auditório                      |
| 17h30        | Apresentação dos 5 times finalistas         |
| 18h30        | Premiação e encerramento                    |
| 18h30 às 20h | Happy Hour e Networking                     |

## 🎯 Desafio

### Educação pública: Inteligência na Fila da Creche

A rede pública tem vagas ociosas em creches e, ao mesmo tempo, listas de espera expressivas.

Um único processo de Inscrição Creche da SME-Rio reúne mais de 45 mil inscrições, distribuídas por 872 unidades entre creches e EDIs — cada família indicando até cinco opções por ordem de preferência. Entre a inscrição e a matrícula existem três fases de retaguarda geridas manualmente pelas 11 Coordenadorias Regionais de Educação: o planejamento da oferta, que ainda se apoia na fila do ano anterior; a classificação, ordenada por uma régua de pontuação redefinida a cada processo; e a convocação, feita por meios de comunicação tradicionais sem rastreio. A fila, portanto, não é apenas por escassez — é de descompasso entre oferta e demanda por território e turno.

Os times devem transformar cinco anos de dados reais (2021–2025) em inteligência acionável que responda: **quantas vagas abrir e onde, em que ordem chamar a fila e como garantir que a família chegue à vaga dentro do prazo**.

**Link para o problema completo:** [GitHub](https://github.com/CIT-SME-RJ/dadoscreche/)

## 📋 Regras

1. **O projeto começa no evento.** O primeiro commit deve ser feito após as 09h00 do dia 30/08. Projetos com evidências de desenvolvimento anterior serão desclassificados. Bibliotecas, frameworks e APIs preexistentes podem ser usados; a lógica do projeto deve ser construída no dia.
2. **Uma submissão por equipe.** Cada equipe submete um único projeto pelo GitHub, enviando o link do repositório para o e-mail **<eventos@taicor.ai>** com o número do grupo no assunto e no corpo do e-mail. Submissões progressivas são aceitas; vale a versão mais recente até o prazo.
3. **Prazo final: 16h30.** Submissões após esse horário serão desconsideradas.
4. **Repositório público no GitHub.** Todo material produzido deve se tornar público, tanto para permitir acesso pelo governo quanto para permitir o próprio processo de avaliação hoje.

> **Use os dados da cidade com responsabilidade.** Use APIs públicas, dados abertos e os dados fornecidos pela secretaria no repositório informado acima. Não faça scraping nem uso indevido dos sistemas da cidade. Os dados e recursos referenciados estão sujeitos aos termos de uso e licenciamento de suas respectivas fontes — cabe aos participantes revisá-los e cumpri-los.

### Conteúdo obrigatório do README

- **Nome da equipe**
- **Membros da equipe**
- **Resumo:** breve explicação da solução desenvolvida
- **Arquitetura / abordagem:** como o Claude foi usado para construir e como ele atua dentro da aplicação
- **Links:** URL da aplicação, se publicada
- **Vídeo demo:** demonstração de 60s. Opcional se a aplicação estiver publicamente acessível; **obrigatório** caso contrário.

## 🎤 Finalistas e apresentações

Serão selecionados **cinco times finalistas**, anunciados na hora. Cada time finalista terá **6 minutos** para apresentar sua solução aos jurados, no auditório (Comuna), a partir das 17h30.

Use o tempo para mostrar a dor que o projeto resolve, demonstrar o protótipo ao vivo e ser honesto sobre o que está pronto hoje e o que viria em seguida. **Não será possível estourar o tempo:** nos 6 minutos, a apresentação é encerrada.

**Dica:** reserve alguns minutos durante o hackathon para estruturar a apresentação, caso o seu grupo seja um dos finalistas. Apresentações em ppt são opcionais — a explicação verbal e uma live demo são suficientes.

## 🏆 Critérios de Julgamento

### Resumo

| #   | Critério       | Peso | Pergunta central                                                        |
| --- | -------------- | ---- | ----------------------------------------------------------------------- |
| 1   | _Impacto Real_ | 40   | A prefeitura usaria isso hoje para gerar impacto real?                  |
| 2   | _Produto_      | 20   | Qual a qualidade do design, da usabilidade e da experiência de uso?     |
| 3   | _Engenharia_   | 20   | Qual a qualidade técnica da solução e sua escalabilidade para produção? |
| 4   | _Ideia_        | 10   | Desconsiderando o que foi entregue, quão inovadora é a ideia?           |
| 5   | _Apresentação_ | 10   | O quão bem o protótipo e a história foram apresentados?                 |

_Total:_ 100 pontos. Cada critério é pontuado de 1 a 5 e ajustado pelo peso correspondente.

---

### 1. Impacto Real (peso 40)

A prefeitura usaria isso hoje gerando impacto real?

| Nota | Descritor                                                          |
| ---- | ------------------------------------------------------------------ |
| 5    | Pronto para usar como está; geraria impacto relevante imediato.    |
| 4    | Usaria em produção, fazendo melhorias; impacto claro e mensurável. |
| 3    | Usaria em piloto pequeno; impacto incremental.                     |
| 2    | Usaria com muito esforço e adaptação; impacto duvidoso.            |
| 1    | Não usaria; não está pronto ou não gera impacto.                   |

---

### 2. Produto (peso 20)

Qual a qualidade do produto: sua usabilidade, experiência de uso, design, etc.?

| Nota | Descritor                                                              |
| ---- | ---------------------------------------------------------------------- |
| 5    | Produto polido; servidor não técnico opera de primeira, sem treino.    |
| 4    | Bem desenhado, fluido e intuitivo; encaixa no fluxo de trabalho.       |
| 3    | Utilizável com curva curta; design aceitável, sem brilho.              |
| 2    | Funcional, mas com atritos sérios; design duro, só usa quem é forçado. |
| 1    | Confuso, mal desenhado; exige treinamento e jargão técnico.            |

---

### 3. Engenharia (peso 20)

Qual a qualidade técnica da solução e sua escalabilidade para produção?

| Nota | Descritor                                                                 |
| ---- | ------------------------------------------------------------------------- |
| 5    | Pronto para produção; escalável, auditável, generalizável a outros casos. |
| 4    | Robusto, auditável, lida com dado ruidoso; caminho claro para produção.   |
| 3    | End-to-end funcionando; reprodutível; precisa de retrabalho para escalar. |
| 2    | Funciona no caso feliz; frágil com dado sujo; longe de produção.          |
| 1    | Não funciona fora do cenário ensaiado; alucina; quebra com dado real.     |

---

### 4. Ideia (peso 10)

Desconsiderando o que foi entregue, quão inovadora é a ideia que tentaram?

| Nota | Descritor                                                 |
| ---- | --------------------------------------------------------- |
| 5    | Genuinamente nova; faz repensar o problema; insight raro. |
| 4    | Criativa, com ângulo original que destrava o problema.    |
| 3    | Sólida, mas previsível; raciocínio defensável.            |
| 2    | Pequena variação do que já foi tentado.                   |
| 1    | Trivial; já existe; sem ângulo novo.                      |

---

### 5. Apresentação (peso 10)

O quão bem o protótipo e a história foram apresentados?

| Nota | Descritor                                                                          |
| ---- | ---------------------------------------------------------------------------------- |
| 5    | Pitch impecável; demo ao vivo impressiona; honesto sobre hoje vs. próximos passos. |
| 4    | Narrativa envolvente; demo ao vivo convincente; conexão com a dor real.            |
| 3    | Clara, mas sem brilho; demo ao vivo funcionou no básico.                           |
| 2    | Narrativa fraca; demo gravada escondendo problemas.                                |
| 1    | Sem narrativa; demo falhou ou não houve; estourou o tempo.                         |

---

## Cálculo da nota final

Nota final = (Impacto Real × 8) + (Produto × 4) + (Engenharia × 4) + (Ideia × 2) + (Apresentação × 2)

Cada critério é pontuado de 1 a 5. Máximo possível: 100 pontos.

| Critério     | Multiplicador | Nota máx. |
| ------------ | ------------- | --------- |
| Impacto Real | × 8           | 40        |
| Produto      | × 4           | 20        |
| Engenharia   | × 4           | 20        |
| Ideia        | × 2           | 10        |
| Apresentação | × 2           | 10        |
| _Total_      |               | _100_     |
