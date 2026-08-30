"""Job mensal de verificacao de telefone, via APScheduler.

So e ativado se ENABLE_SCHEDULER=true no .env (evita disparar mensagens de
verdade sempre que alguem sobe a API em desenvolvimento). Para testar sem
esperar um mes, use o endpoint POST /jobs/verificar_telefones.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app import config, whatsapp
from app.database import SessionLocal

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None


def _job_verificar_telefones() -> None:
    db = SessionLocal()
    try:
        enviados = whatsapp.disparar_verificacao_mensal_telefone(db)
        logger.info("Verificacao mensal de telefone disparada para %s criancas", enviados)
    finally:
        db.close()


def iniciar_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not config.ENABLE_SCHEDULER:
        logger.info("Scheduler desativado (ENABLE_SCHEDULER=false)")
        return None
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _job_verificar_telefones,
        "interval",
        days=config.INTERVALO_VERIFICACAO_TELEFONE_DIAS,
        id="verificacao_mensal_telefone",
    )
    _scheduler.start()
    logger.info(
        "Scheduler iniciado: verificacao de telefone a cada %s dias",
        config.INTERVALO_VERIFICACAO_TELEFONE_DIAS,
    )
    return _scheduler
