import math
from typing import Tuple
import numpy as np
import pandas as pd

#Base32 geohash alfanumerico
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def _as_numpy_array(values, name: str) -> np.ndarray:
    if isinstance(values, pd.Series):
        values = values.to_numpy()
    elif isinstance(values, pd.DataFrame):
        raise TypeError(f"{name} não pode ser um DataFrame; use uma coluna ou array.")

    try:
        return np.asarray(values, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} deve conter valores numéricos") from error


def encode_geohash(latitude: float, longitude: float, precision: int = 12) -> str:
    """Codifica  latitude/longitude em um geohash.
    """
    if not -90 <= latitude <= 90:
        raise ValueError("latitude deve estar entre -90 e 90 graus")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude deve estar entre -180 e 180 graus")
    if precision <= 0:
        raise ValueError("precision deve ser maior que zero")

    lat_min, lat_max = -90.0, 90.0
    lon_min, lon_max = -180.0, 180.0
    bits: list[int] = []
    is_even = True

    while len(bits) < precision * 5:
        if is_even:
            mid = (lon_min + lon_max) / 2.0
            if longitude >= mid:
                bits.append(1)
                lon_min = mid
            else:
                bits.append(0)
                lon_max = mid
        else:
            mid = (lat_min + lat_max) / 2.0
            if latitude >= mid:
                bits.append(1)
                lat_min = mid
            else:
                bits.append(0)
                lat_max = mid
        is_even = not is_even

    encoded = ""
    for index in range(0, len(bits), 5):
        chunk = bits[index:index + 5]
        value = 0
        for bit in chunk:
            value = (value << 1) | bit
        encoded += _BASE32[value]

    return encoded[:precision]


def decode_geohash(geohash: str) -> Tuple[float, float]:
    """Decodifica um geohash e retorna (latitude, longitude) do centro da região."""
    if not geohash:
        raise ValueError("geohash não pode ser vazio")

    geohash = geohash.lower()
    for char in geohash:
        if char not in _BASE32:
            raise ValueError(f"caractere inválido no geohash: {char!r}")

    lat_min, lat_max = -90.0, 90.0
    lon_min, lon_max = -180.0, 180.0
    is_even = True

    bits = []
    for char in geohash:
        value = _BASE32.index(char)
        for bit_index in range(4, -1, -1):
            bits.append((value >> bit_index) & 1)

    for bit in bits:
        if is_even:
            mid = (lon_min + lon_max) / 2.0
            if bit == 1:
                lon_min = mid
            else:
                lon_max = mid
        else:
            mid = (lat_min + lat_max) / 2.0
            if bit == 1:
                lat_min = mid
            else:
                lat_max = mid
        is_even = not is_even

    latitude = (lat_min + lat_max) / 2.0
    longitude = (lon_min + lon_max) / 2.0
    return latitude, longitude


def calcular_haversine(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    unit: str = "km",
) -> float:
    """Calcula a distancia em linha reta entre dois pontos geograficos.

  """
    radius_by_unit = {
        "km": 6371.0,
        "m": 6371000.0,
        "mi": 3958.8,
    }

    if unit.lower() not in radius_by_unit:
        raise ValueError("unit deve ser 'km', 'm' ou 'mi'")

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius_by_unit[unit.lower()] * c


def encode_geohash_batch(
    latitudes,
    longitudes,
    precision: int = 12,
):
    """Codifica  coordenadas em geohashes """
    lat = _as_numpy_array(latitudes, "latitudes")
    lon = _as_numpy_array(longitudes, "longitudes")

    if lat.shape != lon.shape:
        raise ValueError("latitudes e longitudes devem ter o mesmo formato")

    result = np.empty(lat.shape, dtype=object)
    for index in np.ndindex(lat.shape):
        result[index] = encode_geohash(float(lat[index]), float(lon[index]), precision)
    return result


def calcular_haversine_batch(
    lat1,
    lon1,
    lat2,
    lon2,
    unit: str = "km",
):

    lat1_arr = _as_numpy_array(lat1, "lat1")
    lon1_arr = _as_numpy_array(lon1, "lon1")
    lat2_arr = _as_numpy_array(lat2, "lat2")
    lon2_arr = _as_numpy_array(lon2, "lon2")

    if not (lat1_arr.shape == lon1_arr.shape == lat2_arr.shape == lon2_arr.shape):
        raise ValueError("Todas as entradas devem ter o mesmo formato")

    radius_by_unit = {
        "km": 6371.0,
        "m": 6371000.0,
        "mi": 3958.8,
    }
    unit_key = unit.lower()
    if unit_key not in radius_by_unit:
        raise ValueError("unit deve ser 'km', 'm' ou 'mi'")

    lat1_rad = np.radians(lat1_arr)
    lon1_rad = np.radians(lon1_arr)
    lat2_rad = np.radians(lat2_arr)
    lon2_rad = np.radians(lon2_arr)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        np.sin(delta_lat / 2) ** 2
        + np.cos(lat1_rad)
        * np.cos(lat2_rad)
        * np.sin(delta_lon / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    return radius_by_unit[unit_key] * c


def adicionar_geohash_dataframe(df, latitude_col: str, longitude_col: str, precision: int = 12, nova_coluna: str = "geohash"):
    """Adiciona uma coluna de geohash em um DataFrame pandas."""
    if pd is None:
        raise ImportError("Pandas não está instalado. Instale com: pip install pandas")
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df deve ser um pandas.DataFrame")

    df = df.copy()
    df[nova_coluna] = encode_geohash_batch(
        df[latitude_col].to_numpy(),
        df[longitude_col].to_numpy(),
        precision=precision,
    )
    return df


__all__ = [
    "encode_geohash",
    "decode_geohash",
    "calcular_haversine",
    "encode_geohash_batch",
    "calcular_haversine_batch",
    "adicionar_geohash_dataframe",
]
