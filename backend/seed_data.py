"""Popula o SQLite com algumas unidades de exemplo para demo/testes manuais.

Uso:
    python seed_data.py
"""

from app.database import SessionLocal, init_db
from app.models import Programa


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(Programa).count() > 0:
            print("Ja existem programas cadastrados, nada a fazer.")
            return
        programas = [
            Programa(
                nome="Creche Municipal Vila Esperanca",
                bairro="Bangu",
                endereco="Rua das Flores, 100",
                capacidade=2,
                faixas_etarias="0-2,2-4",
                turnos="manha,tarde,integral",
            ),
            Programa(
                nome="Creche Municipal Sol Nascente",
                bairro="Bangu",
                endereco="Av. Brasil, 500",
                capacidade=1,
                faixas_etarias="2-4",
                turnos="integral",
            ),
            Programa(
                nome="Creche Municipal Pequeno Passo",
                bairro="Realengo",
                endereco="Rua da Paz, 20",
                capacidade=3,
                faixas_etarias="0-2,2-4",
                turnos="manha,tarde",
            ),
        ]
        db.add_all(programas)
        db.commit()
        print(f"{len(programas)} programas criados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
