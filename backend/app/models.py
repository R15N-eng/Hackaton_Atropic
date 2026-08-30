import datetime as dt
import enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


class StatusInscricao(str, enum.Enum):
    INSCRITO = "inscrito"
    VERIFICACAO_DOCUMENTOS = "verificacao_documentos"
    CLASSIFICADO = "classificado"
    SELECIONADO = "selecionado"
    MATRICULADO = "matriculado"
    CANCELADO = "cancelado"


class CanalInscricao(str, enum.Enum):
    SITE = "site"
    WHATSAPP = "whatsapp"


class Programa(Base):
    """Uma unidade/creche. Equivalente a 'programas.parquet' do motor da Pessoa 1."""

    __tablename__ = "programas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    bairro: Mapped[str] = mapped_column(String, nullable=False)
    endereco: Mapped[str] = mapped_column(String, default="")
    capacidade: Mapped[int] = mapped_column(Integer, default=0)
    faixas_etarias: Mapped[str] = mapped_column(String, default="")  # ex: "0-2,2-4"
    turnos: Mapped[str] = mapped_column(String, default="")  # ex: "manha,tarde,integral"
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    preferencias: Mapped[list["Preferencia"]] = relationship(back_populates="programa")


class Crianca(Base):
    """Uma inscricao de crianca no processo de fila de creche."""

    __tablename__ = "criancas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    data_nascimento: Mapped[str] = mapped_column(String, nullable=False)  # ISO yyyy-mm-dd
    responsavel_nome: Mapped[str] = mapped_column(String, nullable=False)
    responsavel_telefone: Mapped[str] = mapped_column(String, nullable=False, index=True)  # E.164
    bairro: Mapped[str] = mapped_column(String, nullable=False)
    cep: Mapped[str] = mapped_column(String, default="")

    # Respostas do questionario de vulnerabilidade, formato livre (dict).
    respostas_vulnerabilidade: Mapped[dict] = mapped_column(JSON, default=dict)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default=StatusInscricao.INSCRITO.value)
    canal_inscricao: Mapped[str] = mapped_column(String, default=CanalInscricao.SITE.value)

    # Unidade escolhida atualmente (dentro da janela de troca de N dias).
    programa_escolhido_id: Mapped[int | None] = mapped_column(
        ForeignKey("programas.id"), nullable=True
    )
    escolhido_em: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    # Controle de verificacao mensal de telefone (feature extra da Pessoa 2).
    telefone_confirmado_em: Mapped[dt.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    telefone_verificacao_pendente: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    preferencias: Mapped[list["Preferencia"]] = relationship(
        back_populates="crianca", cascade="all, delete-orphan", order_by="Preferencia.ordem"
    )
    programa_escolhido: Mapped["Programa | None"] = relationship()


class Preferencia(Base):
    """Uma preferencia de unidade (ate 5) de uma crianca, em ordem de prioridade."""

    __tablename__ = "preferencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crianca_id: Mapped[int] = mapped_column(ForeignKey("criancas.id"))
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"))
    ordem: Mapped[int] = mapped_column(Integer, default=1)
    faixa_etaria: Mapped[str] = mapped_column(String, default="")
    turno: Mapped[str] = mapped_column(String, default="")

    crianca: Mapped["Crianca"] = relationship(back_populates="preferencias")
    programa: Mapped["Programa"] = relationship(back_populates="preferencias")


class Notificacao(Base):
    """Log de toda mensagem de WhatsApp enviada (auditoria + nao derrubar a API em falha)."""

    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crianca_id: Mapped[int | None] = mapped_column(ForeignKey("criancas.id"), nullable=True)
    telefone: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # convocacao, verificacao_telefone, confirmacao_inscricao...
    corpo: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="enviado")  # enviado, falhou
    erro: Mapped[str | None] = mapped_column(String, nullable=True)
    mensagem_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class WhatsappSessao(Base):
    """Estado da conversa de WhatsApp por numero de telefone (maquina de estados da inscricao)."""

    __tablename__ = "whatsapp_sessoes"

    telefone: Mapped[str] = mapped_column(String, primary_key=True)
    estado: Mapped[str] = mapped_column(String, default="inicio")
    dados_parciais: Mapped[dict] = mapped_column(JSON, default=dict)
    crianca_id: Mapped[int | None] = mapped_column(ForeignKey("criancas.id"), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class CodigoLogin(Base):
    """Codigo de 6 digitos enviado por WhatsApp para a familia entrar depois
    (de outro aparelho, por exemplo) sem precisar de senha -- ver app/auth.py."""

    __tablename__ = "codigos_login"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telefone: Mapped[str] = mapped_column(String, nullable=False, index=True)
    codigo: Mapped[str] = mapped_column(String, nullable=False)
    expira_em: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Sessao(Base):
    """Sessao de login da familia (token opaco), criada apos verificar o
    codigo recebido por WhatsApp -- ou automaticamente ao se inscrever."""

    __tablename__ = "sessoes"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    telefone: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expira_em: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
