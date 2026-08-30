"""Geometria pura: um ponto (lat/lon) e distancia entre dois pontos.

Sem I/O, sem geocodificacao -- as coordenadas chegam prontas de fora. Se um dia
precisarmos converter CEP/bairro em lat/lon de verdade, isso vira outro modulo
(com rede ou uma tabela auxiliar); este aqui so faz a conta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RAIO_TERRA_KM = 6371.0088


@dataclass(frozen=True)
class Localizacao:
    """Um ponto geografico em graus decimais."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"latitude fora do intervalo: {self.latitude!r}")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"longitude fora do intervalo: {self.longitude!r}")


def distancia_km(a: Localizacao, b: Localizacao) -> float:
    """Distancia em linha reta entre dois pontos (formula de haversine).

    E aproximada -- trata a Terra como esfera perfeita, ~0,5% de erro nesta
    escala. Suficiente para comparar "mais perto"/"mais longe"; se precisar de
    distancia de deslocamento real (rota a pe/carro), isto nao serve.
    """
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(min(1.0, h)))
