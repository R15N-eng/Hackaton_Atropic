import datetime as dt
import logging

from fastapi import Depends, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.twiml.messaging_response import MessagingResponse

from app import classification_engine, config, crud, models, schemas, scheduler, whatsapp
from app.database import get_db, init_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Fila de Creches - API (Back B)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    scheduler.iniciar_scheduler()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------
# Programas (unidades)
# --------------------------------------------------------------------------

@app.post("/programas", response_model=schemas.ProgramaOut)
def criar_programa(dados: schemas.ProgramaIn, db: Session = Depends(get_db)):
    programa = models.Programa(**dados.model_dump())
    db.add(programa)
    db.commit()
    db.refresh(programa)
    return _serializar_programa(programa, db)


@app.get("/programas", response_model=list[schemas.ProgramaOut])
def listar_programas(db: Session = Depends(get_db)):
    programas = db.query(models.Programa).all()
    return [_serializar_programa(p, db) for p in programas]


@app.get("/programa/{programa_id}", response_model=schemas.ProgramaOut)
def obter_programa(programa_id: int, db: Session = Depends(get_db)):
    programa = db.get(models.Programa, programa_id)
    if programa is None:
        raise HTTPException(404, "Programa nao encontrado")
    return _serializar_programa(programa, db)


def _serializar_programa(programa: models.Programa, db: Session) -> schemas.ProgramaOut:
    inscritos = (
        db.query(models.Preferencia).filter(models.Preferencia.programa_id == programa.id).count()
    )
    return schemas.ProgramaOut(
        id=programa.id,
        nome=programa.nome,
        bairro=programa.bairro,
        endereco=programa.endereco,
        capacidade=programa.capacidade,
        inscritos=inscritos,
        nota_corte_atual=classification_engine.nota_corte_atual(programa.id, db),
    )


# --------------------------------------------------------------------------
# Etapa 1: inscricao
# --------------------------------------------------------------------------

@app.post("/inscricao", response_model=schemas.InscricaoOut)
def inscrever(dados: schemas.InscricaoIn, db: Session = Depends(get_db)):
    crianca = crud.criar_inscricao(db, dados)
    whatsapp.enviar_whatsapp(
        db,
        crianca.responsavel_telefone,
        whatsapp.montar_mensagem_confirmacao_inscricao(crianca),
        tipo="confirmacao_inscricao",
        crianca_id=crianca.id,
    )
    return _serializar_inscricao(crianca)


def _serializar_inscricao(crianca: models.Crianca) -> schemas.InscricaoOut:
    return schemas.InscricaoOut(
        id=crianca.id,
        nome=crianca.nome,
        responsavel_telefone=crianca.responsavel_telefone,
        bairro=crianca.bairro,
        status=crianca.status,
        score=crianca.score,
        canal_inscricao=crianca.canal_inscricao,
        programa_escolhido_id=crianca.programa_escolhido_id,
        preferencias=[
            schemas.PreferenciaOut(
                ordem=p.ordem,
                programa_id=p.programa_id,
                programa_nome=p.programa.nome if p.programa else "",
                faixa_etaria=p.faixa_etaria,
                turno=p.turno,
            )
            for p in crianca.preferencias
        ],
    )


# --------------------------------------------------------------------------
# Etapa 2: verificacao de documentos -> define a unidade (sugerida ou forcada)
# --------------------------------------------------------------------------

@app.post("/verificacao_documentos/{crianca_id}", response_model=schemas.InscricaoOut)
def verificar_documentos(
    crianca_id: int, programa_id: int | None = None, db: Session = Depends(get_db)
):
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")

    ids_preferencias = [p.programa_id for p in crianca.preferencias]
    if programa_id is not None:
        if programa_id not in ids_preferencias:
            raise HTTPException(400, "programa_id nao esta entre as preferencias da crianca")
        crianca.programa_escolhido_id = programa_id
    elif crianca.programa_escolhido_id is None:
        if not ids_preferencias:
            raise HTTPException(
                400, "Crianca sem preferencias cadastradas: nao ha unidade para sugerir/forcar"
            )
        # TODO(Pessoa 1): trocar pela unidade geograficamente mais proxima quando o
        # motor de classificacao incorporar localizacao. Por ora usamos a 1a preferencia.
        crianca.programa_escolhido_id = ids_preferencias[0]

    crianca.status = models.StatusInscricao.VERIFICACAO_DOCUMENTOS.value
    crianca.escolhido_em = dt.datetime.utcnow()
    db.add(crianca)
    db.commit()
    db.refresh(crianca)
    return _serializar_inscricao(crianca)


# --------------------------------------------------------------------------
# Etapa 3: classificacao (posicao na fila + troca de escolha em ate 7 dias)
# --------------------------------------------------------------------------

@app.get("/classificacao/{crianca_id}", response_model=schemas.ClassificacaoOut)
def classificacao(crianca_id: int, db: Session = Depends(get_db)):
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")

    posicao = total = None
    nota_corte = None
    programa_nome = None
    pode_alterar = False
    pode_alterar_ate = None

    if crianca.programa_escolhido_id is not None:
        posicao, total = classification_engine.posicao_na_fila(
            crianca.id, crianca.programa_escolhido_id, db
        )
        nota_corte = classification_engine.nota_corte_atual(crianca.programa_escolhido_id, db)
        programa_nome = crianca.programa_escolhido.nome if crianca.programa_escolhido else None
        if crianca.escolhido_em is not None:
            pode_alterar_ate = crianca.escolhido_em + dt.timedelta(days=config.JANELA_TROCA_DIAS)
            pode_alterar = dt.datetime.utcnow() <= pode_alterar_ate

    sugestoes = []
    for pref in crianca.preferencias:
        if pref.programa_id == crianca.programa_escolhido_id:
            continue
        pos, tot = classification_engine.posicao_na_fila(crianca.id, pref.programa_id, db)
        sugestoes.append(
            schemas.SugestaoOut(
                programa_id=pref.programa_id,
                programa_nome=pref.programa.nome if pref.programa else "",
                posicao_na_fila=pos,
                nota_corte_atual=classification_engine.nota_corte_atual(pref.programa_id, db),
            )
        )

    return schemas.ClassificacaoOut(
        crianca_id=crianca.id,
        status=crianca.status,
        programa_escolhido_id=crianca.programa_escolhido_id,
        programa_escolhido_nome=programa_nome,
        posicao_na_fila=posicao,
        total_na_fila=total,
        nota_corte_atual=nota_corte,
        pode_alterar_escolha=pode_alterar,
        pode_alterar_ate=pode_alterar_ate,
        sugestoes=sugestoes,
    )


@app.get("/status-matricula/{crianca_id}", response_model=schemas.StatusMatriculaOut)
def status_matricula(crianca_id: int, db: Session = Depends(get_db)):
    """Usado pela tela 4 do front (status.html): resultado final da inscricao,
    fora do contrato original da Pessoa 2 (adicionado para o front consumir a
    API real em vez do mock)."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")

    if crianca.status in (
        models.StatusInscricao.SELECIONADO.value,
        models.StatusInscricao.MATRICULADO.value,
    ):
        base = crianca.escolhido_em or crianca.created_at
        return schemas.StatusMatriculaOut(
            status=crianca.status,
            unidade=crianca.programa_escolhido.nome if crianca.programa_escolhido else None,
            prazo_matricula=base + dt.timedelta(days=config.PRAZO_MATRICULA_DIAS),
        )

    return schemas.StatusMatriculaOut(status="aguardando", unidade=None, prazo_matricula=None)


def _garantir_dentro_da_janela(crianca: models.Crianca) -> None:
    """Bloqueia mudanca de preferencias fora da janela de N dias a partir da
    1a escolha (verificacao de documentos) -- mesma regra usada em
    /escolher_unidade, tambem aplicada em /preferencias/*."""
    if crianca.escolhido_em is not None:
        prazo = crianca.escolhido_em + dt.timedelta(days=config.JANELA_TROCA_DIAS)
        if dt.datetime.utcnow() > prazo:
            raise HTTPException(400, f"Janela de troca de {config.JANELA_TROCA_DIAS} dias encerrada")


@app.get(
    "/classificacao/{crianca_id}/pre-visualizar/{programa_id}",
    response_model=schemas.PreVisualizacaoOut,
)
def pre_visualizar_posicao(crianca_id: int, programa_id: int, db: Session = Depends(get_db)):
    """Mostra em que posicao a crianca ficaria numa unidade ANTES de ela ser
    adicionada as preferencias -- usado pela tela de classificacao para a
    familia decidir se vale a pena adicionar essa opcao a lista."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")
    programa = db.get(models.Programa, programa_id)
    if programa is None:
        raise HTTPException(404, "Programa nao encontrado")

    posicao, total = classification_engine.posicao_hipotetica(crianca_id, programa_id, db)
    return schemas.PreVisualizacaoOut(
        programa_id=programa.id,
        programa_nome=programa.nome,
        posicao_hipotetica=posicao,
        total_na_fila_hipotetico=total,
        capacidade=programa.capacidade,
    )


@app.post("/preferencias/{crianca_id}/adicionar", response_model=schemas.InscricaoOut)
def adicionar_preferencia(
    crianca_id: int, dados: schemas.PreferenciaAdicionarIn, db: Session = Depends(get_db)
):
    """Adiciona uma nova unidade a lista de preferencias (max 5) -- diferente
    de /escolher_unidade, que so troca qual das preferencias JA existentes
    esta ativa."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")
    _garantir_dentro_da_janela(crianca)

    if len(crianca.preferencias) >= 5:
        raise HTTPException(400, "Ja existem 5 preferencias cadastradas (o maximo permitido)")
    if any(p.programa_id == dados.programa_id for p in crianca.preferencias):
        raise HTTPException(400, "Essa unidade ja esta entre as preferencias")
    if db.get(models.Programa, dados.programa_id) is None:
        raise HTTPException(404, "Programa nao encontrado")

    db.add(
        models.Preferencia(
            crianca_id=crianca.id,
            programa_id=dados.programa_id,
            ordem=len(crianca.preferencias) + 1,
            faixa_etaria=dados.faixa_etaria,
            turno=dados.turno,
        )
    )
    db.commit()
    db.refresh(crianca)
    return _serializar_inscricao(crianca)


@app.delete("/preferencias/{crianca_id}/{programa_id}", response_model=schemas.InscricaoOut)
def remover_preferencia(crianca_id: int, programa_id: int, db: Session = Depends(get_db)):
    """Remove uma unidade da lista de preferencias. Se ela era a unidade
    ativa (programa_escolhido_id), a 1a preferencia restante assume o lugar."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")
    _garantir_dentro_da_janela(crianca)

    if len(crianca.preferencias) <= 1:
        raise HTTPException(400, "Nao e possivel remover a unica opcao restante")
    preferencia = next((p for p in crianca.preferencias if p.programa_id == programa_id), None)
    if preferencia is None:
        raise HTTPException(404, "Essa unidade nao esta entre as preferencias")

    crianca.preferencias.remove(preferencia)  # cascade="all, delete-orphan" apaga a linha
    for nova_ordem, p in enumerate(sorted(crianca.preferencias, key=lambda p: p.ordem), start=1):
        p.ordem = nova_ordem

    if crianca.programa_escolhido_id == programa_id:
        crianca.programa_escolhido_id = crianca.preferencias[0].programa_id if crianca.preferencias else None

    db.add(crianca)
    db.commit()
    db.refresh(crianca)
    return _serializar_inscricao(crianca)


@app.post("/escolher_unidade", response_model=schemas.ClassificacaoOut)
def escolher_unidade(crianca_id: int, programa_id: int, db: Session = Depends(get_db)):
    """Troca a unidade escolhida, respeitando a janela de N dias definida em
    config.JANELA_TROCA_DIAS a partir da 1a escolha (verificacao de documentos)."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")
    if programa_id not in [p.programa_id for p in crianca.preferencias]:
        raise HTTPException(400, "programa_id nao esta entre as preferencias da crianca")
    _garantir_dentro_da_janela(crianca)
    crianca.programa_escolhido_id = programa_id
    db.add(crianca)
    db.commit()
    return classificacao(crianca_id, db)


# --------------------------------------------------------------------------
# Etapa 3/4: avancar status do processo (classificado, selecionado, matriculado...)
# --------------------------------------------------------------------------

@app.post("/avancar_processo", response_model=schemas.InscricaoOut)
def avancar_processo(dados: schemas.AvancarProcessoIn, db: Session = Depends(get_db)):
    crianca = db.get(models.Crianca, dados.crianca_id)
    if crianca is None:
        raise HTTPException(404, "Crianca nao encontrada")

    try:
        novo_status = models.StatusInscricao(dados.novo_status)
    except ValueError:
        raise HTTPException(400, f"Status invalido: {dados.novo_status}")

    if dados.programa_id is not None:
        crianca.programa_escolhido_id = dados.programa_id

    status_anterior = crianca.status
    crianca.status = novo_status.value
    db.add(crianca)
    db.commit()
    db.refresh(crianca)

    if novo_status == models.StatusInscricao.SELECIONADO:
        if crianca.programa_escolhido_id is None:
            raise HTTPException(400, "Crianca sem unidade escolhida: nao e possivel convocar")
        programa = db.get(models.Programa, crianca.programa_escolhido_id)
        whatsapp.enviar_whatsapp(
            db,
            crianca.responsavel_telefone,
            whatsapp.montar_mensagem_convocacao(crianca, programa),
            tipo="convocacao",
            crianca_id=crianca.id,
        )

    # Uma vaga foi liberada (crianca cancelou ou foi matriculada em outro lugar):
    # roda a reclassificacao e avisa quem subiu na fila.
    if novo_status in (models.StatusInscricao.CANCELADO, models.StatusInscricao.MATRICULADO) and (
        status_anterior != novo_status.value
    ):
        subiram = classification_engine.reclassificar(db)
        for crianca_id_subiu in subiram:
            criancq = db.get(models.Crianca, crianca_id_subiu)
            if criancq:
                whatsapp.enviar_whatsapp(
                    db,
                    criancq.responsavel_telefone,
                    "Boas noticias! Uma vaga foi liberada e voce subiu na fila. "
                    "Confira sua nova posicao na area de classificacao.",
                    tipo="reclassificacao",
                    crianca_id=criancq.id,
                )

    return _serializar_inscricao(crianca)


# --------------------------------------------------------------------------
# WhatsApp: webhook do Twilio (inscricao por WhatsApp + verificacao mensal)
# --------------------------------------------------------------------------

@app.post("/whatsapp/webhook")
def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):
    telefone = From.replace("whatsapp:", "")
    texto = Body.strip()

    crianca_pendente = (
        db.query(models.Crianca)
        .filter(
            models.Crianca.responsavel_telefone == telefone,
            models.Crianca.telefone_verificacao_pendente.is_(True),
        )
        .first()
    )
    sessao_ativa = db.get(models.WhatsappSessao, telefone)

    if sessao_ativa is not None and sessao_ativa.estado != "finalizado":
        texto_resposta = whatsapp.iniciar_ou_continuar_inscricao(db, telefone, texto)
    elif crianca_pendente is not None:
        texto_resposta = whatsapp.processar_resposta_verificacao_telefone(
            db, crianca_pendente, texto
        )
    elif texto.lower() in {"inscricao", "inscrição", "matricula", "matrícula"}:
        texto_resposta = whatsapp.iniciar_ou_continuar_inscricao(db, telefone, texto)
    elif texto.lower() == "status":
        crianca = (
            db.query(models.Crianca)
            .filter(models.Crianca.responsavel_telefone == telefone)
            .order_by(models.Crianca.created_at.desc())
            .first()
        )
        if crianca is None:
            texto_resposta = "Nao encontramos inscricao para este numero. Digite INSCRICAO para comecar."
        else:
            info = classificacao(crianca.id, db)
            texto_resposta = (
                f"Status de {crianca.nome}: {info.status}. "
                f"Posicao na fila: {info.posicao_na_fila or '—'} de {info.total_na_fila or '—'}."
            )
    else:
        texto_resposta = (
            "Ola! Digite INSCRICAO para iniciar uma inscricao na fila de creches, "
            "ou STATUS para ver a posicao de uma inscricao existente."
        )

    twiml = MessagingResponse()
    twiml.message(texto_resposta)
    return Response(content=str(twiml), media_type="application/xml")


@app.post("/whatsapp/enviar_convocacao/{crianca_id}")
def enviar_convocacao_manual(crianca_id: int, db: Session = Depends(get_db)):
    """Endpoint auxiliar para reenviar a convocacao manualmente (ex: falha anterior)."""
    crianca = db.get(models.Crianca, crianca_id)
    if crianca is None or crianca.programa_escolhido_id is None:
        raise HTTPException(404, "Crianca ou unidade escolhida nao encontrada")
    programa = db.get(models.Programa, crianca.programa_escolhido_id)
    notificacao = whatsapp.enviar_whatsapp(
        db,
        crianca.responsavel_telefone,
        whatsapp.montar_mensagem_convocacao(crianca, programa),
        tipo="convocacao",
        crianca_id=crianca.id,
    )
    return {"status": notificacao.status, "erro": notificacao.erro}


# --------------------------------------------------------------------------
# Job mensal de verificacao de telefone (trigger manual para demo/teste)
# --------------------------------------------------------------------------

@app.post("/jobs/verificar_telefones")
def disparar_verificacao_telefones(db: Session = Depends(get_db)):
    enviados = whatsapp.disparar_verificacao_mensal_telefone(db)
    return {"mensagens_enviadas": enviados}
