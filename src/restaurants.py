import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

import pandas as pd

CSV_PATH = Path(__file__).resolve().with_name("bares.csv")
_Colunas_csv = {
    "_id",
    "DESC_LOGRADOURO",
    "NOME_LOGRADOURO",
    "NUMERO_IMOVEL",
    "COMPLEMENTO",
    "NOME_BAIRRO",
    "NOME",
    "NOME_FANTASIA",
}
_Tipo_Endereco = {
    "ALA": "Alameda",
    "AVE": "Avenida",
    "BEC": "Beco",
    "EST": "Estrada",
    "PCA": "Praça",
    "ROD": "Rodovia",
    "RUA": "Rua",
    "TRV": "Travessa",
    "VDP": "Viela",
    "VIA": "Via",
}


class GeocodingError(RuntimeError):
    """Erro ao consultar o geocodificador ou interpretar sua resposta."""


class AddressNotFoundError(GeocodingError):
    """O geocodificador não encontrou o endereço informado."""


@lru_cache(maxsize=1)
def load_restaurants() -> tuple[dict, ...]:
    """Carrega o CSV uma vez e transforma seus registros em opções pesquisáveis."""
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"Arquivo de restaurantes não encontrado: {CSV_PATH}")

    frame = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    missing_columns = _Colunas_csv - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Colunas ausentes em {CSV_PATH.name}: {missing}")

    restaurants = []
    for row in frame.to_dict(orient="records"):
        establishment_id = row["_id"].strip()
        street_type = _Tipo_Endereco.get(row["DESC_LOGRADOURO"].strip().upper(), "")
        street_name = row["NOME_LOGRADOURO"].strip()
        street = " ".join(part for part in (street_type, street_name) if part)
        number = row["NUMERO_IMOVEL"].strip()
        complement = row["COMPLEMENTO"].strip()
        neighborhood = row["NOME_BAIRRO"].strip()
        name = row["NOME_FANTASIA"].strip() or row["NOME"].strip()

        address_parts = [
            f"{street}, {number}" if number else street,
            complement,
            neighborhood,
            "Belo Horizonte",
            "Minas Gerais",
            "Brasil",
        ]
        address = ", ".join(part for part in address_parts if part)
        restaurants.append(
            {
                "id": establishment_id,
                "nome": name,
                "address": address,
                "neighborhood": neighborhood,
                "label": f"{name} — {address}",
                "_search_text": f"{name} {address}".casefold(),
            }
        )

    return tuple(restaurants)


def search_restaurants(search_value: str | None, limit: int = 25) -> list[dict]:
    """Pesquisa nome, logradouro ou bairro sem enviar todo o CSV ao navegador."""
    if limit < 1:
        raise ValueError("limit deve ser maior que zero")

    query = (search_value or "").strip().casefold()
    matches = []
    for restaurant in load_restaurants():
        if not query or query in restaurant["_search_text"]:
            matches.append(restaurant)
            if len(matches) >= limit:
                break
    return matches


def get_restaurant(restaurant_id: str) -> dict:
    """Retorna um estabelecimento do CSV pelo identificador da linha."""
    for restaurant in load_restaurants():
        if restaurant["id"] == str(restaurant_id):
            return dict(restaurant)
    raise KeyError(f"Restaurante não encontrado no CSV: {restaurant_id}")


class NominatimGeocoder:
    """Geocodificador com limite de uma consulta por segundo."""

    _request_lock = threading.Lock()
    _last_request_at = 0.0

    def __init__(
        self,
        min_delay_seconds: float = 1.0,
        timeout_seconds: float = 12.0,
    ):
        if min_delay_seconds < 1.0:
            raise ValueError("Nominatim exige no máximo uma solicitação por segundo")
        self.min_delay_seconds = min_delay_seconds
        self.timeout_seconds = timeout_seconds

    def geocode(self, address: str) -> tuple[float, float]:
        """Retorna (latitude, longitude) consultando a API pública."""
        normalized_address = " ".join(address.split())
        if not normalized_address:
            raise ValueError("O endereço para geocodificação não pode estar vazio.")

        with self._request_lock:
            elapsed = time.monotonic() - self._last_request_at
            delay = self.min_delay_seconds - elapsed
            if delay > 0:
                time.sleep(delay)
            type(self)._last_request_at = time.monotonic()

            parameters = urllib.parse.urlencode(
                {
                    "q": normalized_address,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "br",
                    "accept-language": "pt-BR",
                }
            )
            request = urllib.request.Request(
                f"https://nominatim.openstreetmap.org/search?{parameters}",
                headers={
                    "User-Agent": "TP01-Fleet-Monitor/1.0",
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    results = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code == 429:
                    raise GeocodingError(
                        "O geocodificador limitou as consultas. Aguarde antes de tentar novamente."
                    ) from error
                raise GeocodingError(
                    f"O geocodificador retornou HTTP {error.code}."
                ) from error
            except (urllib.error.URLError, TimeoutError) as error:
                raise GeocodingError(
                    f"Não foi possível acessar o geocodificador: {error}"
                ) from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise GeocodingError(
                    "O geocodificador retornou uma resposta inválida."
                ) from error

            if not isinstance(results, list):
                raise GeocodingError("O geocodificador retornou um formato inesperado.")
            if not results:
                raise AddressNotFoundError(
                    "O serviço não encontrou coordenadas para este endereço."
                )

            try:
                latitude = float(results[0]["lat"])
                longitude = float(results[0]["lon"])
            except (KeyError, TypeError, ValueError) as error:
                raise GeocodingError(
                    "coordenadas invalidas"
                ) from error
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise GeocodingError(
                    "coordenadas fora dos limites válidos."
                )

            return latitude, longitude

    def geocode_with_neighborhood_fallback(
        self, address: str, neighborhood: str
    ) -> tuple[tuple[float, float], bool]:
        """Tenta o endereço; se falhar, retorna o centro aproximado do bairro."""
        try:
            return self.geocode(address), False
        except AddressNotFoundError:
            normalized_neighborhood = " ".join(neighborhood.split())
            if not normalized_neighborhood:
                raise
            fallback_address = (
                f"{normalized_neighborhood}, Belo Horizonte, Minas Gerais, Brasil"
            )
            return self.geocode(fallback_address), True


__all__ = [
    "AddressNotFoundError",
    "GeocodingError",
    "NominatimGeocoder",
    "get_restaurant",
    "load_restaurants",
    "search_restaurants",
]
