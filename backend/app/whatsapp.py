"""Integracao com Twilio WhatsApp Sandbox.

Contem:
- envio de mensagens (convocacao, confirmacao de inscricao, verificacao mensal
  de telefone) com tratamento de erro que NUNCA derruba a API;
- a maquina de estados da inscricao 100% por WhatsApp (etapa 1 do processo);
- o fluxo de resposta da verificacao mensal de numero de telefone.
"""

import datetime as dt
import logging
import re

from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app import classification_engine, config, models

logger = logging.getLogger("whatsapp")

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
    return _client


def _telefone_whatsapp(numero: str) -> str:
    """Garante o prefixo 'whatsapp:' exigido pela API do Twilio."""
    return numero if numero.startswith("whatsapp:") else f"whatsapp:{numero}"


def enviar_whatsapp(
    db: Session,
    telefone: str,
    corpo: str,
    tipo: str,
    crianca_id: int | None = None,
) -> models.Notificacao:
    """Envia uma mensagem de WhatsApp e registra o resultado (sucesso ou falha).

    Nunca levanta excecao: uma falha no Twilio (sandbox fora do ar, numero
    invalido, credenciais erradas) fica registrada em Notificacao.status =
    'falhou', mas nao interrompe o fluxo da API que chamou esta funcao.
    """
    notificacao = models.Notificacao(
        crianca_id=crianca_id, telefone=telefone, tipo=tipo, corpo=corpo, status="enviado"
    )
    try:
        if not config.TWILIO_ACCOUNT_SID or not config.TWILIO_AUTH_TOKEN:
            raise RuntimeError("Credenciais do Twilio nao configuradas (.env)")
        mensagem = get_client().messages.create(
            from_=_telefone_whatsapp(config.TWILIO_WHATSAPP_FROM),
            to=_telefone_whatsapp(telefone),
            body=corpo,
        )
        notificacao.twilio_sid = mensagem.sid
    except (TwilioRestException, RuntimeError, Exception) as exc:  # noqa: BLE001
        notificacao.status = "falhou"
        notificacao.erro = str(exc)
        logger.warning("Falha ao enviar WhatsApp para %s: %s", telefone, exc)
    finally:
        db.add(notificacao)
        db.commit()
        db.refresh(notificacao)
    return notificacao


# --------------------------------------------------------------------------
# Templates de mensagem
# --------------------------------------------------------------------------

def montar_mensagem_convocacao(crianca: models.Crianca, programa: models.Programa) -> str:
    return (
        f"Ola, {crianca.responsavel_nome}! A crianca {crianca.nome} foi *selecionada* "
        f"na creche {programa.nome} ({programa.bairro}). "
        f"Compareca a unidade com os documentos para efetivar a matricula. "
        f"Endereco: {programa.endereco or 'a confirmar'}."
    )


def montar_mensagem_confirmacao_inscricao(crianca: models.Crianca) -> str:
    return (
        f"Inscricao de {crianca.nome} recebida com sucesso! "
        f"Voce pode acompanhar a classificacao a qualquer momento por aqui. "
        f"Responda STATUS para ver sua posicao na fila."
    )


def montar_mensagem_verificacao_telefone(crianca: models.Crianca) -> str:
    return (
        f"Ola, {crianca.responsavel_nome}! Este ainda e o seu numero de WhatsApp "
        f"de contato para a inscricao de {crianca.nome} na fila de creches? "
        f"Responda *SIM* para confirmar, ou envie o *novo numero* (com DDD) se ele mudou."
    )


# --------------------------------------------------------------------------
# Verificacao mensal de telefone (feature extra da Pessoa 2)
# --------------------------------------------------------------------------

def disparar_verificacao_mensal_telefone(db: Session) -> int:
    """Envia a mensagem de verificacao para todas as criancas com inscricao ativa
    cujo numero nao foi confirmado nos ultimos N dias (config.INTERVALO_VERIFICACAO_TELEFONE_DIAS).

    Retorna a quantidade de mensagens disparadas. Pensado para ser chamado por
    um job mensal (ver app/scheduler.py) ou manualmente via
    POST /jobs/verificar_telefones (util para demonstrar no hackathon).
    """
    limite = dt.datetime.utcnow() - dt.timedelta(days=config.INTERVALO_VERIFICACAO_TELEFONE_DIAS)
    criancas = (
        db.query(models.Crianca)
        .filter(
            models.Crianca.status.notin_(
                [models.StatusInscricao.CANCELADO.value, models.StatusInscricao.MATRICULADO.value]
            ),
        )
        .filter(
            (models.Crianca.telefone_confirmado_em.is_(None))
            | (models.Crianca.telefone_confirmado_em <= limite)
        )
        .all()
    )
    enviados = 0
    for crianca in criancas:
        if crianca.telefone_confirmado_em and crianca.telefone_confirmado_em > limite:
            continue
        crianca.telefone_verificacao_pendente = True
        db.add(crianca)
        db.commit()
        enviar_whatsapp(
            db,
            crianca.responsavel_telefone,
            montar_mensagem_verificacao_telefone(crianca),
            tipo="verificacao_telefone",
            crianca_id=crianca.id,
        )
        enviados += 1
    return enviados


_REGEX_TELEFONE = re.compile(r"^\+?\d{10,15}$")


def _normaliza_telefone(texto: str) -> str | None:
    digitos = re.sub(r"[^\d+]", "", texto)
    if _REGEX_TELEFONE.match(digitos):
        return digitos if digitos.startswith("+") else f"+{digitos}"
    return None


def processar_resposta_verificacao_telefone(
    db: Session, crianca: models.Crianca, texto: str
) -> str:
    """Trata a resposta do responsavel a mensagem de verificacao mensal.

    - 'SIM' -> confirma o numero atual.
    - um numero de telefone -> atualiza o cadastro para o novo numero.
    - qualquer outra coisa -> pede para repetir.
    """
    texto_normalizado = texto.strip().lower()
    if texto_normalizado in {"sim", "s", "yes"}:
        crianca.telefone_confirmado_em = dt.datetime.utcnow()
        crianca.telefone_verificacao_pendente = False
        db.add(crianca)
        db.commit()
        return "Obrigado! Numero de contato confirmado com sucesso."

    novo_numero = _normaliza_telefone(texto)
    if novo_numero:
        crianca.responsavel_telefone = novo_numero
        crianca.telefone_confirmado_em = dt.datetime.utcnow()
        crianca.telefone_verificacao_pendente = False
        db.add(crianca)
        db.commit()
        return f"Numero atualizado para {novo_numero}. Obrigado por avisar!"

    return (
        "Nao entendi sua resposta. Responda *SIM* se este numero continua correto, "
        "ou envie o novo numero de telefone com DDD."
    )


# --------------------------------------------------------------------------
# Inscricao via WhatsApp (etapa 1 do processo, feita pelo webhook)
# --------------------------------------------------------------------------

PERGUNTAS_VULNERABILIDADE = list(classification_engine.REGUA_PADRAO.keys())

ETAPAS = [
    "nome",
    "data_nascimento",
    "responsavel_nome",
    "bairro",
    "cep",
    "programa_id",
    "vulnerabilidade",
]


def _pergunta_para_etapa(etapa: str, programas: list[models.Programa]) -> str:
    if etapa == "nome":
        return "Vamos iniciar a inscricao na fila de creches. Qual o *nome completo* da crianca?"
    if etapa == "data_nascimento":
        return "Qual a *data de nascimento* da crianca? (formato AAAA-MM-DD)"
    if etapa == "responsavel_nome":
        return "Qual o *nome do responsavel*?"
    if etapa == "bairro":
        return "Em qual *bairro* voces moram?"
    if etapa == "cep":
        return "Qual o *CEP* da residencia? (ou responda 'pular')"
    if etapa == "programa_id":
        lista = "\n".join(f"{p.id} - {p.nome} ({p.bairro})" for p in programas)
        return (
            "Escolha ate uma unidade de preferencia digitando o *numero* da lista abaixo "
            "(voce podera ajustar as demais preferencias depois pelo site):\n" + lista
        )
    if etapa == "vulnerabilidade":
        return (
            "Ultima etapa: responda *sim* ou *nao* para cada pergunta, uma por vez.\n"
            "Pergunta 1: familia tem renda baixa?"
        )
    return "Digite qualquer coisa para continuar."


def iniciar_ou_continuar_inscricao(
    db: Session, telefone: str, texto: str
) -> str:
    """Avanca a maquina de estados de inscricao por WhatsApp em um passo.

    Cada mensagem recebida do numero avanca exatamente uma etapa. Ao final,
    cria a Crianca (mesma funcao usada pelo endpoint POST /inscricao) com
    canal_inscricao='whatsapp'.
    """
    from app import crud  # import tardio evita ciclo de import

    sessao = db.get(models.WhatsappSessao, telefone)
    programas = db.query(models.Programa).all()

    if sessao is None:
        sessao = models.WhatsappSessao(telefone=telefone, estado="nome", dados_parciais={})
        db.add(sessao)
        db.commit()
        return _pergunta_para_etapa("nome", programas)

    dados = dict(sessao.dados_parciais or {})
    etapa = sessao.estado

    if etapa == "finalizado":
        sessao.estado = "nome"
        sessao.dados_parciais = {}
        db.add(sessao)
        db.commit()
        return _pergunta_para_etapa("nome", programas)

    if etapa == "vulnerabilidade":
        # Copia nova do dict aninhado: mutar o objeto que já está em
        # sessao.dados_parciais faria o SQLAlchemy achar que "nada mudou"
        # (old == new, mesmo com top-level dict novo) e pular o UPDATE.
        respostas = dict(dados.get("respostas_vulnerabilidade", {}))
        indice = len(respostas)
        if indice < len(PERGUNTAS_VULNERABILIDADE):
            chave_atual = PERGUNTAS_VULNERABILIDADE[indice]
            respostas[chave_atual] = texto.strip().lower() in {"sim", "s", "yes"}
            dados["respostas_vulnerabilidade"] = respostas
            sessao.dados_parciais = dados
            db.add(sessao)
            db.commit()
            proximo_indice = len(respostas)
            if proximo_indice < len(PERGUNTAS_VULNERABILIDADE):
                proxima_chave = PERGUNTAS_VULNERABILIDADE[proximo_indice]
                return f"Pergunta {proximo_indice + 1}: {proxima_chave.replace('_', ' ')}?"
            crianca = crud.criar_inscricao_a_partir_de_dict(db, dados, telefone, canal="whatsapp")
            sessao.estado = "finalizado"
            sessao.crianca_id = crianca.id
            db.add(sessao)
            db.commit()
            return montar_mensagem_confirmacao_inscricao(crianca)

    indice_etapa = ETAPAS.index(etapa)
    if etapa == "programa_id":
        programa_escolhido = next((p for p in programas if str(p.id) == texto.strip()), None)
        dados["programa_id"] = programa_escolhido.id if programa_escolhido else None
    elif etapa == "cep" and texto.strip().lower() == "pular":
        dados["cep"] = ""
    else:
        dados[etapa] = texto.strip()

    proxima_etapa = ETAPAS[indice_etapa + 1]
    sessao.estado = proxima_etapa
    sessao.dados_parciais = dados
    db.add(sessao)
    db.commit()
    return _pergunta_para_etapa(proxima_etapa, programas)
