"""
Deferred Acceptance (Gale-Shapley), lado das crianças propondo.

Substitui a lógica atual da SME — que classifica POR OPÇÃO, permitindo que uma
mesma criança ocupe até 5 vagas simultaneamente — por uma alocação POR CRIANÇA,
em que cada criança mantém no máximo uma oferta em aberto por vez.

Garantias do algoritmo:
  · estabilidade — nenhuma criança fica fora de um programa onde outra criança
    com pontuação menor entrou (ausência de "inveja justificada");
  · à prova de estratégia para a família — declarar a preferência verdadeira é
    a melhor jogada, então a ordem declarada passa a ser informação confiável
    para o planejamento;
  · determinístico e auditável — mesma entrada, mesma saída, sem modelo treinado.

Complexidade O(total de opções). Roda em segundos sobre um processo inteiro.
"""
from collections import defaultdict
import hashlib


def _loteria(crianca: str, semente: str) -> int:
    """Desempate único e reprodutível (single tie-breaking).

    A mesma loteria vale para todos os programas — é o que a literatura de
    school choice recomenda: usar loterias independentes por programa piora
    a eficiência do resultado sem ganho de justiça.
    """
    return int(hashlib.sha256(f"{semente}:{crianca}".encode()).hexdigest()[:12], 16)


def deferred_acceptance(opcoes, capacidades, semente="rio2025"):
    """
    opcoes:      lista de dicts {crianca, programa, pref, score}
    capacidades: dict {programa: int}
    retorna:     dict {crianca: programa} com as alocações finais
    """
    # Lista de preferências por criança, da mais desejada para a menos
    prefs = defaultdict(list)
    for o in opcoes:
        prefs[o["crianca"]].append((o["pref"], o["programa"]))
    for cr in prefs:
        prefs[cr] = [p for _, p in sorted(set(prefs[cr]))]

    score = {}
    for o in opcoes:
        # a pontuação é da inscrição; se a criança tiver mais de uma, vale a maior
        score[o["crianca"]] = max(score.get(o["crianca"], 0), o["score"])

    prioridade = {cr: (score[cr], _loteria(cr, semente)) for cr in prefs}

    proxima = defaultdict(int)              # índice da próxima opção a propor
    retidas = defaultdict(list)             # programa -> crianças retidas
    livres = [cr for cr in prefs if prefs[cr]]

    while livres:
        cr = livres.pop()
        i = proxima[cr]
        if i >= len(prefs[cr]):
            continue                        # esgotou as opções, fica sem vaga
        prog = prefs[cr][i]
        proxima[cr] += 1

        cap = capacidades.get(prog, 0)
        if cap <= 0:
            livres.append(cr)               # programa sem vaga, tenta a próxima
            continue

        retidas[prog].append(cr)
        if len(retidas[prog]) > cap:
            # devolve para a fila a criança de menor prioridade entre as retidas
            pior = min(retidas[prog], key=lambda x: prioridade[x])
            retidas[prog].remove(pior)
            livres.append(pior)

    return {cr: prog for prog, crs in retidas.items() for cr in crs}
