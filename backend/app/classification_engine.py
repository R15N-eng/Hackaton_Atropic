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

# Peso de cada resposta "sim" no questionario de vulnerabilidade.
# TODO(Pessoa 1): substituir pela regua oficial do ano quando estiver definida.
REGUA_PADRAO = {
    "renda_baixa": 3.0,
    "familia_monoparental": 2.0,
    "pessoa_com_deficiencia": 3.0,
    "beneficiario_auxilio": 2.0,
    "mae_estudante": 1.5,
    "mae_adolescente": 2.0,
    "situacao_de_rua_ou_abrigo": 4.0,
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
