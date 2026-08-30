import datetime as dt

from pydantic import BaseModel, Field


class PreferenciaIn(BaseModel):
    programa_id: int
    faixa_etaria: str
    turno: str


class InscricaoIn(BaseModel):
    nome: str
    data_nascimento: str  # ISO yyyy-mm-dd
    responsavel_nome: str
    responsavel_telefone: str = Field(description="Formato E.164, ex: +5521999999999")
    bairro: str
    cep: str = ""
    preferencias: list[PreferenciaIn] = Field(default_factory=list, max_length=5)
    respostas_vulnerabilidade: dict = Field(default_factory=dict)
    canal_inscricao: str = "site"


class PreferenciaOut(BaseModel):
    ordem: int
    programa_id: int
    programa_nome: str
    faixa_etaria: str
    turno: str

    model_config = {"from_attributes": True}


class InscricaoOut(BaseModel):
    id: int
    nome: str
    responsavel_telefone: str
    bairro: str
    status: str
    score: float | None
    canal_inscricao: str
    programa_escolhido_id: int | None
    preferencias: list[PreferenciaOut]

    model_config = {"from_attributes": True}


class AvancarProcessoIn(BaseModel):
    crianca_id: int
    novo_status: str
    programa_id: int | None = None  # obrigatorio quando o status envolve escolha de unidade


class SugestaoOut(BaseModel):
    programa_id: int
    programa_nome: str
    posicao_na_fila: int
    nota_corte_atual: float | None


class ClassificacaoOut(BaseModel):
    crianca_id: int
    status: str
    programa_escolhido_id: int | None
    programa_escolhido_nome: str | None
    posicao_na_fila: int | None
    total_na_fila: int | None
    nota_corte_atual: float | None
    pode_alterar_escolha: bool
    pode_alterar_ate: dt.datetime | None
    sugestoes: list[SugestaoOut]


class ProgramaOut(BaseModel):
    id: int
    nome: str
    bairro: str
    endereco: str
    capacidade: int
    inscritos: int
    nota_corte_atual: float | None

    model_config = {"from_attributes": True}


class PreferenciaAdicionarIn(BaseModel):
    programa_id: int
    faixa_etaria: str = ""
    turno: str = ""


class PreVisualizacaoOut(BaseModel):
    programa_id: int
    programa_nome: str
    posicao_hipotetica: int
    total_na_fila_hipotetico: int
    capacidade: int


class StatusMatriculaOut(BaseModel):
    status: str
    unidade: str | None
    prazo_matricula: dt.datetime | None


class ProgramaIn(BaseModel):
    nome: str
    bairro: str
    endereco: str = ""
    capacidade: int = 0
    faixas_etarias: str = ""
    turnos: str = ""
    lat: float | None = None
    lon: float | None = None
