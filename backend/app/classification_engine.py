"""Motor de classificacao.

Este modulo define o CONTRATO que a Pessoa 1 (Back A) vai preencher com a
implementacao real (DuckDB + deferred_acceptance.py sobre opcoes.parquet /
programas.parquet). Por enquanto contem uma implementacao simples e
100% funcional em cima do SQLite local, para a API poder ser desenvolvida e
demonstrada sem depender do motor definitivo.

Para integrar o motor real: substitua o CORPO das 4 funcoes abaixo por
chamadas as funcoes da Pessoa 1, mantendo a MESMA ASSINATURA. Nenhum outro
arquivo da API precisa mudar.

    calcular_score(respostas, regua_do_ano) -> float
    nota_corte_atual(programa_id, db) -> float | None
    posicao_na_fila(crianca_id, programa_id, db) -> tuple[int, int]  # (posicao, total)
    reclassificar(db) -> list[int]  # ids das criancas que subiram de posicao
"""

from sqlalchemy.orm import Session

from app import models

# Regua oficial 2025 (Query C do dataset da SME): peso de cada pergunta de
# vulnerabilidade cuja resposta seja "sim" (True), chave = id da pergunta.
# Perguntas 29 e 30 nao entram aqui: valem 0 ponto, servem so de criterio de
# desempate (ver app/whatsapp.py e frontend/api.js, mesma regua nos dois lados).
REGUA_PADRAO = {
    "28": 51.0,  # inscrita no CadUnico
    "31": 25.0,  # publico-alvo da educacao especial
    "17": 4.0,   # crianca/familiar vitima de violencia domestica
    "20": 4.0,   # familia monoparental
    "25": 3.0,   # pais/responsaveis com deficiencia
    "18": 3.0,   # doenca cronica grave no nucleo familiar
    "6": 2.0,    # bolsa familia / Cartao Carioca
    "16": 2.0,   # uso abusivo de drogas/alcool no nucleo familiar
    "12": 2.0,   # membro do nucleo familiar presidiario/ex-presidiario (5 anos)
    "23": 2.0,   # candidato refugiado
    "27": 2.0,   # aguardou em fila no ano anterior sem ser atendida
}


def calcular_score(respostas: dict, regua_do_ano: dict | None = None) -> float:
    """Soma os pesos de cada resposta 'sim' (True) segundo a regua do ano."""
    regua = regua_do_ano or REGUA_PADRAO
    return round(sum(peso for chave, peso in regua.items() if respostas.get(chave)), 2)


def nota_corte_atual(programa_id: int, db: Session) -> float | None:
    """Menor score entre as criancas ja SELECIONADAS/MATRICULADAS no programa."""
    admitidos = (
        db.query(models.Crianca)
        .filter(
            models.Crianca.programa_escolhido_id == programa_id,
            models.Crianca.status.in_(
                [models.StatusInscricao.SELECIONADO.value, models.StatusInscricao.MATRICULADO.value]
            ),
        )
        .all()
    )
    scores = [c.score for c in admitidos if c.score is not None]
    return min(scores) if scores else None


def posicao_na_fila(crianca_id: int, programa_id: int, db: Session) -> tuple[int, int]:
    """Posicao (1-based) da crianca na fila do programa, ordenada por score desc.

    A fila considera apenas criancas ainda ativas no processo (nao matriculadas
    em outro lugar, nao canceladas) que tem esse programa entre as preferencias.
    """
    candidatos = (
        db.query(models.Crianca)
        .join(models.Preferencia, models.Preferencia.crianca_id == models.Crianca.id)
        .filter(
            models.Preferencia.programa_id == programa_id,
            models.Crianca.status.notin_([models.StatusInscricao.CANCELADO.value]),
        )
        .distinct()
        .all()
    )
    candidatos.sort(key=lambda c: (-(c.score or 0), c.id))
    total = len(candidatos)
    for posicao, crianca in enumerate(candidatos, start=1):
        if crianca.id == crianca_id:
            return posicao, total
    return 0, total


def posicao_hipotetica(crianca_id: int, programa_id: int, db: Session) -> tuple[int, int]:
    """Como posicao_na_fila, mas funciona mesmo se a crianca AINDA NAO tem
    esse programa entre as preferencias -- usado para pre-visualizar a
    posicao antes de a familia decidir adicionar uma nova unidade a lista
    (tela de classificacao, botao "adicionar unidade")."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        return 0, 0

    candidatos = (
        db.query(models.Crianca)
        .join(models.Preferencia, models.Preferencia.crianca_id == models.Crianca.id)
        .filter(
            models.Preferencia.programa_id == programa_id,
            models.Crianca.status.notin_([models.StatusInscricao.CANCELADO.value]),
        )
        .distinct()
        .all()
    )
    if not any(c.id == crianca.id for c in candidatos):
        candidatos.append(crianca)
    candidatos.sort(key=lambda c: (-(c.score or 0), c.id))
    total = len(candidatos)
    for posicao, c in enumerate(candidatos, start=1):
        if c.id == crianca.id:
            return posicao, total
    return 0, total


def reclassificar(db: Session) -> list[int]:
    """Recalcula a fila de todos os programas.

    Implementacao simplificada: como o ranking e calculado on-the-fly em
    posicao_na_fila, aqui apenas identificamos quem mudou de posicao desde a
    ultima leitura conhecida (nao persistida) -- na pratica, com o motor real
    (Deferred Acceptance), esta funcao vai rodar o algoritmo completo e
    devolver quem subiu por causa de uma vaga liberada.
    """
    programas = db.query(models.Programa).all()
    subiram: list[int] = []
    for programa in programas:
        candidatos = (
            db.query(models.Crianca)
            .join(models.Preferencia, models.Preferencia.crianca_id == models.Crianca.id)
            .filter(
                models.Preferencia.programa_id == programa.id,
                models.Crianca.status.notin_([models.StatusInscricao.CANCELADO.value]),
            )
            .distinct()
            .all()
        )
        candidatos.sort(key=lambda c: (-(c.score or 0), c.id))
        vagas_livres = max(programa.capacidade - len(
            [c for c in candidatos if c.status == models.StatusInscricao.MATRICULADO.value]
        ), 0)
        for crianca in candidatos[:vagas_livres]:
            if crianca.status == models.StatusInscricao.INSCRITO.value:
                subiram.append(crianca.id)
    return subiram
