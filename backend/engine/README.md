# Match Carioca

Motor de alocação de vagas de creche para a SME-Rio, com simulador de política.

> **Este motor não é mais usado pela API.** `backend/app/engine_service.py`
> passou a chamar o motor da Pessoa 1 (`pessoa_1/` na raiz do repo), que
> preserva os critérios reais de desempate por pergunta (irmão na creche,
> mãe adolescente) — este parquet aqui só guarda o score somado. `simulate.py`
> e `evidencia_injustica.py` continuam usando `deferred_acceptance.py` daqui
> como ferramenta de análise/comparação, independente da API.

Substitui a classificação **por opção** (atual) por uma alocação **por criança**
usando Deferred Acceptance, e mede o resultado contra o processo real de 2025.

## Por que

A própria SME descreve o problema no briefing do hackathon:

> "O processo de classificação é orientado pelo total de escolhas por unidade, e não por CPF (...).
> O sistema classifica as opções simultaneamente: ofertando até 5 vagas para o mesmo CPF."

> "A fila reflete menos uma escassez global de matrículas e mais um descompasso entre a oferta
> disponível e a demanda por territórios e turnos específicos. Trata-se, em grande parte, de uma
> fila de preferência, e não de ausência de vaga."

Isso é um problema de *school choice*, com solução conhecida e em produção em Nova York,
Boston, Amsterdã e no Chile.

## Setup

```bash
git clone https://github.com/CIT-SME-RJ/dadoscreche.git    # dados de entrada
pip install -r requirements.txt
python pipeline/01_build_aggregates.py --repo dadoscreche --ano 2025
```

## Rodar

```bash
python engine/evidencia_injustica.py     # mede a injustiça no resultado real
python engine/simulate.py                # compara real x Deferred Acceptance
python engine/simulate.py --peso-cadunico 25 --max-opcoes 3
```

## Resultados sobre o processo real de 2025

| | Real (por opção) | Deferred Acceptance |
|---|---:|---:|
| crianças colocadas | 48.680 | 47.768 |
| % na 1ª opção | 72,2% | **83,9%** |
| preferência média obtida | 1,47 | **1,24** |
| % famílias vulneráveis atendidas | 78,0% | **93,5%** |
| % demais famílias atendidas | 76,8% | 59,2% |

Com **os mesmos assentos**, a regra que a própria SME escreveu passa a ser cumprida.

Também medido no resultado real: **9.221 crianças** (64,8% das que terminaram 2025 sem vaga)
tinham pontuação acima do corte de entrada de uma unidade que elas mesmas escolheram.
É "inveja justificada" — exatamente o que o Deferred Acceptance elimina por construção.

E o peso do CadÚnico é irrelevante entre 5 e 80 pontos: a ordem da fila não muda, porque
ele domina a soma de todos os outros critérios. A revisão de pesos de 2024 (100 → 51) foi
cosmética.

## Limitações declaradas

1. **Capacidade é proxy.** Não existe base de vagas ofertadas por processo. Usamos as
   confirmações observadas em 2025. A pergunta respondida é "com os mesmos assentos, dava
   para alocar melhor?", não "quantas vagas faltam".
2. **Não há timestamp de mudança de status** — só `data_criacao`. Tempo de fila não é medível.
3. **Anonimização.** A SME avisa que os indicadores não representam a realidade. Os números
   demonstram o comportamento do mecanismo, não estatística oficial do município.
4. **A oferta simultânea de até 5 vagas ao mesmo CPF não é medível** nestes dados: a base
   guarda o estado final, depois que o sistema já desfez as duplicatas. É simulável, não medível.

## Estrutura

```
pipeline/01_build_aggregates.py   bases brutas -> parquet
engine/deferred_acceptance.py     Gale-Shapley, ~90 linhas, sem dependência
engine/evidencia_injustica.py     mede inveja justificada no resultado real
engine/simulate.py                compara cenários e imprime as métricas
```
