import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./creche.db")

# WhatsApp Cloud API (Meta) -- ver app/whatsapp.py para onde obter cada um.
META_WHATSAPP_TOKEN = os.getenv("META_WHATSAPP_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")

ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"

# Janela em dias que o responsavel tem para trocar a unidade escolhida.
JANELA_TROCA_DIAS = int(os.getenv("JANELA_TROCA_DIAS", "7"))

# Intervalo do job de verificacao mensal de telefone (dias).
INTERVALO_VERIFICACAO_TELEFONE_DIAS = int(
    os.getenv("INTERVALO_VERIFICACAO_TELEFONE_DIAS", "30")
)

# Prazo (a partir da convocacao/escolha da unidade) para a familia comparecer
# e matricular a crianca presencialmente. Usado em GET /status-matricula.
PRAZO_MATRICULA_DIAS = int(os.getenv("PRAZO_MATRICULA_DIAS", "15"))

# Login da familia por telefone + codigo via WhatsApp (ver app/auth.py).
CODIGO_LOGIN_VALIDADE_MINUTOS = int(os.getenv("CODIGO_LOGIN_VALIDADE_MINUTOS", "10"))
SESSAO_VALIDADE_DIAS = int(os.getenv("SESSAO_VALIDADE_DIAS", "90"))
