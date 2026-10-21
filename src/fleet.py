import random
from math import ceil, cos, radians
from collections import defaultdict

from src.geohash import calcular_haversine, decode_geohash, encode_geohash
from src.trie import RadixTree

_NAMES = (
    "Ana", "Bruno", "Caio", "Cris", "Eduardo", "Fernanda", "Gabriel",
    "Alison", "Igor", "Daniel", "Laís", "Larissa", "Marcos", "Salomão",
    "Otávio", "Luisa", "Rafael", "Sofia", "Tiago", "Vitória",
)
_LAST_NAMES = (
    "Almeida", "Barbosa", "Costa", "Dias", "Esteves", "Ferreira", "Gomes",
    "Lima", "Mendes", "Nogueira", "Oliveira", "Pereira", "Ribeiro",
    "Souza", "Teixeira",
)
AVERAGE_DELIVERER_SPEED_KMH = 25.0
GEOHASH_INDEX_PRECISION = 8


def geohash_prefixes_for_radius(
    latitude: float,
    longitude: float,
    radius_km: float,
    max_precision: int = GEOHASH_INDEX_PRECISION,
) -> set[str]:
    """Retorna os prefixos da célula central e das células adjacentes.

    O prefixo é escolhido para que um raio de busca não atravesse mais de
    uma célula em cada direção; a consulta cobre então a grade 3x3.
    """
    if max_precision < 1:
        raise ValueError("max_precision deve ser maior que zero")
    if radius_km < 0:
        raise ValueError("radius_km não pode ser negativo")

    precision = max_precision
    precision_found = radius_km == 0
    if radius_km > 0:
        latitude_delta = radius_km / 110.574
        furthest_latitude = min(89.999999, abs(latitude) + latitude_delta)
        for candidate_precision in range(max_precision, 0, -1):
            total_bits = candidate_precision * 5
            longitude_bits = (total_bits + 1) // 2
            latitude_bits = total_bits // 2
            cell_height_km = 180 / (2**latitude_bits) * 110.574
            cell_width_km = (
                360
                / (2**longitude_bits)
                * 111.32
                * cos(radians(furthest_latitude))
            )
            if min(cell_height_km, cell_width_km) >= radius_km:
                precision = candidate_precision
                precision_found = True
                break
    if not precision_found:
        raise ValueError(
            "O raio é muito grande para cobrir a busca com células adjacentes."
        )

    center_hash = encode_geohash(latitude, longitude, precision)
    center_latitude, center_longitude = decode_geohash(center_hash)
    total_bits = precision * 5
    longitude_bits = (total_bits + 1) // 2
    latitude_bits = total_bits // 2
    cell_width = 360 / (2**longitude_bits)
    cell_height = 180 / (2**latitude_bits)

    prefixes = set()
    for latitude_offset in (-1, 0, 1):
        neighbor_latitude = center_latitude + latitude_offset * cell_height
        if not -90 <= neighbor_latitude <= 90:
            continue
        for longitude_offset in (-1, 0, 1):
            neighbor_longitude = (
                center_longitude + longitude_offset * cell_width + 180
            ) % 360 - 180
            prefixes.add(
                encode_geohash(
                    neighbor_latitude,
                    neighbor_longitude,
                    precision,
                )
            )
    return prefixes


class GeohashFleetIndex:
    """Índice Radix reutilizável para candidatos espaciais da frota."""

    def __init__(self, deliverers: list[dict]):
        self.deliverers_by_hash: dict[str, list[dict]] = defaultdict(list)
        self.tree = RadixTree()
        for deliverer in deliverers:
            geohash = deliverer.get("geohash") or encode_geohash(
                float(deliverer["latitude"]),
                float(deliverer["longitude"]),
                precision=GEOHASH_INDEX_PRECISION,
            )
            if geohash not in self.deliverers_by_hash:
                self.tree.insert(geohash)
            self.deliverers_by_hash[geohash].append(deliverer)

    def candidates(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[dict]:
        prefixes = geohash_prefixes_for_radius(
            latitude,
            longitude,
            radius_km,
            max_precision=GEOHASH_INDEX_PRECISION,
        )
        return [
            deliverer
            for prefix in prefixes
            for geohash in self.tree.search_by_prefix(prefix)
            for deliverer in self.deliverers_by_hash[geohash]
        ]


def generate_deliverers(count: int = 60, seed: int | None = None) -> list[dict]:
    """Gera entregadores ficticios """
    if count < 1:
        raise ValueError("count deve ser maior que zero")

    generator = random.Random(seed)
    deliverers = []
    for index in range(count):
        latitude = generator.uniform(-19.99, -19.82)
        longitude = generator.uniform(-44.02, -43.88)
        deliverers.append(
            {
                "id": f"{index + 1:03d}",
                "nome": (
                    f"{generator.choice(_NAMES)} "
                    f"{generator.choice(_LAST_NAMES)}"
                ),
                "latitude": latitude,
                "longitude": longitude,
                "geohash": encode_geohash(latitude, longitude, precision=8),
                "status": "Disponível" if generator.random() < 0.8 else "Em entrega",
            }
        )
    return deliverers


def find_deliverers_for_restaurant(
    restaurant: dict,
    radius_km: float = 5.0,
    include_unavailable: bool = False,
    *,
    index: GeohashFleetIndex,
) -> list[dict]:
    """Retorna entregadores no raio, disponíveis por padrão.

    A Radix Tree consulta a célula Geohash adequada ao raio e suas oito
    vizinhas. O índice pré-construído é reutilizado entre consultas;
    Haversine aplica o raio real aos candidatos.
    ``include_unavailable`` inclui entregadores ocupados para exibição no mapa.
    A consulta retorna em O(m + k), sem ordenar os resultados, sendo ``m``
    o tamanho dos prefixos consultados e ``k`` o número de candidatos.
    """
    if radius_km < 0:
        raise ValueError("radius_km não pode ser negativo")

    candidates = index.candidates(
        float(restaurant["latitude"]),
        float(restaurant["longitude"]),
        radius_km,
    )
    matches = []
    for deliverer in candidates:
        is_available = deliverer.get("status", "Disponível") == "Disponível"
        if not is_available and not include_unavailable:
            continue
        distance = calcular_haversine(
            float(restaurant["latitude"]),
            float(restaurant["longitude"]),
            float(deliverer["latitude"]),
            float(deliverer["longitude"]),
        )
        if distance <= radius_km:
            estimated_minutes = ceil(
                distance / AVERAGE_DELIVERER_SPEED_KMH * 60
            )
            matches.append(
                {
                    **deliverer,
                    "distancia_km": distance,
                    "tempo_estimado_min": estimated_minutes,
                }
            )

    return matches


__all__ = [
    "AVERAGE_DELIVERER_SPEED_KMH",
    "GeohashFleetIndex",
    "geohash_prefixes_for_radius",
    "generate_deliverers",
    "find_deliverers_for_restaurant",
]
