import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./creche.db")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"

# Janela em dias que o responsavel tem para trocar a unidade escolhida.
JANELA_TROCA_DIAS = int(os.getenv("JANELA_TROCA_DIAS", "7"))

# Intervalo do job de verificacao mensal de telefone (dias).
INTERVALO_VERIFICACAO_TELEFONE_DIAS = int(
    os.getenv("INTERVALO_VERIFICACAO_TELEFONE_DIAS", "30")
)
