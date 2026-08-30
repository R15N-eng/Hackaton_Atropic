"""Regras de negocio compartilhadas entre o endpoint REST de inscricao e o
fluxo de inscricao via WhatsApp -- para as duas portas de entrada (site e
WhatsApp) caírem exatamente na mesma logica de gravacao e pontuacao.
"""

import datetime as dt

from sqlalchemy.orm import Session

from app import classification_engine, models, schemas


def criar_inscricao(db: Session, dados: schemas.InscricaoIn) -> models.Crianca:
    crianca = models.Crianca(
        nome=dados.nome,
        data_nascimento=dados.data_nascimento,
        responsavel_nome=dados.responsavel_nome,
        responsavel_telefone=dados.responsavel_telefone,
        bairro=dados.bairro,
        cep=dados.cep,
        respostas_vulnerabilidade=dados.respostas_vulnerabilidade,
        canal_inscricao=dados.canal_inscricao,
        status=models.StatusInscricao.INSCRITO.value,
        telefone_confirmado_em=dt.datetime.utcnow(),
    )
    crianca.score = classification_engine.calcular_score(dados.respostas_vulnerabilidade)
    db.add(crianca)
    db.flush()

    for ordem, pref in enumerate(dados.preferencias[:5], start=1):
        db.add(
            models.Preferencia(
                crianca_id=crianca.id,
                programa_id=pref.programa_id,
                ordem=ordem,
                faixa_etaria=pref.faixa_etaria,
                turno=pref.turno,
            )
        )
    db.commit()
    db.refresh(crianca)
    return crianca


def criar_inscricao_a_partir_de_dict(
    db: Session, dados: dict, telefone: str, canal: str = "whatsapp"
) -> models.Crianca:
    """Usado pela maquina de estados do WhatsApp (app/whatsapp.py), onde os
    dados sao coletados mensagem a mensagem em vez de vir de um JSON unico."""
    preferencias = []
    if dados.get("programa_id"):
        preferencias.append(
            schemas.PreferenciaIn(
                programa_id=dados["programa_id"], faixa_etaria="", turno=""
            )
        )
    inscricao = schemas.InscricaoIn(
        nome=dados.get("nome", ""),
        data_nascimento=dados.get("data_nascimento", ""),
        responsavel_nome=dados.get("responsavel_nome", ""),
        responsavel_telefone=telefone,
        bairro=dados.get("bairro", ""),
        cep=dados.get("cep", ""),
        preferencias=preferencias,
        respostas_vulnerabilidade=dados.get("respostas_vulnerabilidade", {}),
        canal_inscricao=canal,
    )
    return criar_inscricao(db, inscricao)
