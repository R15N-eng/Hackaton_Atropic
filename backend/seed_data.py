"""Popula o SQLite com as unidades usadas na demo.

30 creches/CEIs reais que estavam na fila 2025 (mesmo catalogo usado no modo
mock do frontend, frontend/api.js:UNIDADES_2025), concentradas nos bairros com
pior taxa de atendimento. Capacidade = soma das vagas reais confirmadas em
2025 por unidade (frontend/api.js:PROGRAMAS_REAIS_2025); onde nao ha dado real
publicado para a unidade, usamos um valor padrao (20).

Uso:
    python seed_data.py
"""

from app.database import SessionLocal, init_db
from app.models import Programa

# (nome, bairro, capacidade, lat, lon)
UNIDADES_2025 = [
    ("Creche Municipal Ladeira dos Funcionários", "Caju", 20, -22.879151, -43.224306),
    ("Creche Municipal Virgínia Lemos", "Caju", 40, -22.886423, -43.233212),
    ("Creche Municipal Senninha", "Caju", 20, -22.882989, -43.228696),
    ("Creche Municipal Casa Branca - Professor Paulo Freire", "Tijuca", 20, -22.936602, -43.248803),
    ("Creche Municipal Raízes do Salgueiro", "Tijuca", 20, -22.928219, -43.225674),
    ("Creche Municipal Tia Bela", "Tijuca", 20, -22.93817, -43.243002),
    ("Creche Municipal Luís Carlos de Oliveira Câmara", "Cordovil", 16, -22.81681, -43.290269),
    ("Creche Municipal Chico Mendes", "Cordovil", 49, -22.818898, -43.292015),
    ("CP Casa de Joel", "Cordovil", 20, -22.8298666, -43.30749742),
    ("CP Instituto Josefa Laurentino", "Maré", 20, -22.84825182, -43.24773693),
    ("Espaço de Desenvolvimento Infantil Medalhista Olímpico Luiz Felipe Marques Fonteles", "Maré", 20, -22.87059, -43.234365),
    ("Espaço de Desenvolvimento Infantil Medalhista Olímpico Evandro Motta Marcondes Guerra", "Maré", 20, -22.870255, -43.234242),
    ("Creche Municipal Otávio Henrique de Oliveira", "Jacarepaguá", 94, -22.974934, -43.331015),
    ("Creche Municipal Tia Tereza", "Taquara", 56, -22.910162, -43.371421),
    ("Creche Municipal Criança do Futuro", "Jacarepaguá", 38, -22.944254, -43.384456),
    ("Creche Municipal Germinio de Souza Estrela", "Jacarepaguá", 20, -22.960454, -43.352685),
    ("Creche Municipal Emília Joana da Fonseca Marques", "Praça Seca", 65, -22.907555, -43.353033),
    ("Creche Municipal Irmã Dulce", "Praça Seca", 110, -22.900935, -43.362466),
    ("Creche Municipal Tia Malu", "Taquara", 47, -22.918418, -43.410069),
    ("Creche Municipal Augusto de Carvalho Torres Filho", "Curicica", 41, -22.955267, -43.390377),
    ("Creche Municipal Luzes do Amanhã", "Cidade de Deus", 54, -22.952939, -43.364891),
    ("Creche Municipal Margarida Gabinal", "Cidade de Deus", 45, -22.950792, -43.355759),
    ("Creche Municipal Sempre Vida Josué", "Cidade de Deus", 29, -22.942892, -43.363848),
    ("CP Creche Jardim Clarice", "Anil", 76, -22.96408, -43.33653),
    ("Espaço de Desenvolvimento Infantil Arthur Bispo do Rosário", "Curicica", 109, -22.93725, -43.390376),
    ("Espaço de Desenvolvimento Infantil Compositor Roberto Ribeiro", "Anil", 64, -22.957616, -43.331432),
    ("Espaço de Desenvolvimento Infantil Rodrigo Lopes da Silva - Tikinho", "Curicica", 59, -22.945659, -43.378626),
    ("Espaço de Desenvolvimento Infantil Professora Edília Coelho Garcia", "Taquara", 20, -22.912042, -43.419526),
    ("Espaço de Desenvolvimento Infantil Professor Roberto Luiz Pereira", "Praça Seca", 20, -22.904538, -43.34563),
    ("Espaço de Desenvolvimento Infantil Professora Norma Andrade Nogueira", "Anil", 20, -22.96226, -43.343769),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.query(Programa).count() > 0:
            print("Ja existem programas cadastrados, nada a fazer.")
            return
        programas = [
            Programa(
                nome=nome,
                bairro=bairro,
                capacidade=capacidade,
                faixas_etarias="Berçário,Maternal I,Maternal II",
                turnos="Integral,Parcial",
                lat=lat,
                lon=lon,
            )
            for nome, bairro, capacidade, lat, lon in UNIDADES_2025
        ]
        db.add_all(programas)
        db.commit()
        print(f"{len(programas)} programas criados.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
