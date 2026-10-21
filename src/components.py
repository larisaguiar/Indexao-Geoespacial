from dash import html
import dash_leaflet as dl

from src.interface import inline_style

MAP_CENTER = [-19.9167, -43.9345]
OSM_TILE_URL = "https://a.tile.openstreetmap.de/{z}/{x}/{y}.png"
MOTORCYCLE_ICON_URL = "/assets/moto-vermelha-png.jpg"
OSM_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">'
    "OpenStreetMap contributors</a>"
)


def create_base_map_layer() -> dl.TileLayer:
    """Cria uma camada OSM alternativa, sem chave de API."""
    return dl.TileLayer(url=OSM_TILE_URL, attribution=OSM_ATTRIBUTION)


def create_map_markers(
    deliverers: list[dict],
    restaurant: dict | None = None,
    result_ids: set[str] | None = None,
) -> list:
    """Cria marcadores para a frota e para o restaurante selecionado."""
    result_ids = result_ids or set()
    markers = []
    if restaurant:
        location_label = (
            f"Localização aproximada do bairro {restaurant['neighborhood']}"
            if restaurant.get("localizacao_aproximada")
            else "Restaurante"
        )
        markers.append(
            dl.CircleMarker(
                id="restaurant-marker",
                center=[restaurant["latitude"], restaurant["longitude"]],
                radius=13,
                color="#7f0000",
                weight=3,
                fillColor="#e31b23",
                fillOpacity=1,
                pathOptions={
                    "color": "#7f0000",
                    "weight": 3,
                    "fillColor": "#e31b23",
                    "fillOpacity": 1,
                },
                children=[
                    dl.Tooltip(
                        f"{location_label}: {restaurant['nome']}"
                    )
                ],
            )
        )

    for deliverer in deliverers:
        is_in_radius = deliverer["id"] in result_ids
        is_available = deliverer.get("status", "Disponível") == "Disponível"
        if is_in_radius and is_available:
            icon_class = "courier-map-icon--matched"
            status_label = "Disponível no raio"
            icon_color = "#00a650"
            image_filter = "filter:hue-rotate(120deg) saturate(2)"
        elif not is_available:
            icon_class = "courier-map-icon--busy"
            status_label = (
                "Indisponível no raio" if is_in_radius else "Em entrega"
            )
            icon_color = "#78818c"
            image_filter = ""
        else:
            icon_class = "courier-map-icon--available"
            status_label = "Disponível"
            icon_color = "#1677ff"
            image_filter = ""
        details = f"{deliverer['nome']} · {status_label}"
        if "distancia_km" in deliverer:
            details += f" · {deliverer['distancia_km']:.2f} km"
        markers.append(
            dl.DivMarker(
                id={"type": "courier-marker", "id": deliverer["id"]},
                position=[deliverer["latitude"], deliverer["longitude"]],
                title=details,
                iconOptions={
                    "html": (
                        f'<div class="courier-map-icon {icon_class}" '
                        f'style="background-color:{icon_color}" '
                        f'aria-label="{status_label}">'
                        f'<img src="{MOTORCYCLE_ICON_URL}" alt="" '
                        f'style="{image_filter}" '
                        'aria-hidden="true"></div>'
                    ),
                    "className": "courier-div-icon",
                    "iconSize": [36, 36],
                    "iconAnchor": [18, 18],
                },
                children=[dl.Tooltip(details)],
            )
        )
    return markers


def create_map_legend() -> html.Div:
    """legenda das cores usadas nos marcadores do mapa."""
    entries = [
        ("#e31b23", "Restaurante selecionado"),
        ("#00a650", "Disponível no raio"),
        ("#1677ff", "Disponível sem filtro"),
        ("#78818c", "Indisponível no raio / em entrega"),
    ]
    return html.Div(
        [
            html.Div(
                [
                    html.Span(
                        className="legend-swatch legend-swatch--courier",
                        children=html.Img(
                            src=MOTORCYCLE_ICON_URL,
                            alt="",
                            style=(
                                {"filter": "hue-rotate(120deg) saturate(2)"}
                                if label == "Disponível no raio"
                                else None
                            ),
                            className="legend-motorcycle-image",
                            **{"aria-hidden": "true"},
                        ),
                        style={
                            "display": "inline-grid",
                            "width": "25px",
                            "height": "25px",
                            "placeItems": "center",
                            "border": 0,
                            "borderRadius": "50%",
                            "backgroundColor": color,
                        },
                    )
                    if label != "Restaurante selecionado"
                    else html.Span(
                        className="legend-swatch legend-swatch--restaurant",
                        style={"backgroundColor": color},
                    ),
                    html.Span(label),
                ],
                className="map-legend-item",
                style={
                    "display": "inline-flex",
                    "alignItems": "center",
                    "gap": "6px",
                    "color": "#596779",
                    "fontSize": "10px",
                    "fontWeight": 700,
                    "whiteSpace": "nowrap",
                },
            )
            for color, label in entries
        ],
        role="list",
        **{"aria-label": "Legenda do mapa"},
        className="map-legend",
        style={
            "display": "flex",
            "flexWrap": "wrap",
            "gap": "7px 12px",
            "margin": 0,
            "padding": "9px 11px",
            "border": 0,
            "backgroundColor": "transparent",
        },
    )


def create_results_list(deliverers: list[dict]) -> html.Div:
    """tabela de resultados com ação para focar o mapa."""
    if not deliverers:
        return html.Div(
            html.P(
                "Nenhum entregador disponível no raio escolhido.",
                className="empty-state",
                style=inline_style("empty-state"),
            ),
            className="results-table-wrap",
        )

    return html.Div(
        html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th(
                                "ID",
                                scope="col",
                                style=inline_style("deliverer-results-header"),
                            ),
                            html.Th(
                                "Nome",
                                scope="col",
                                style=inline_style("deliverer-results-header"),
                            ),
                            html.Th(
                                "Distância",
                                scope="col",
                                style=inline_style("deliverer-results-header"),
                            ),
                            html.Th(
                                "Tempo estimado",
                                scope="col",
                                style=inline_style("deliverer-results-header"),
                            ),
                        ],
                        style={"display": "table-row"},
                    ),
                    style={"display": "table-header-group"},
                ),
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Td(
                                    html.Button(
                                        deliverer["id"],
                                        id={
                                            "type": "deliverer-result",
                                            "id": deliverer["id"],
                                        },
                                        n_clicks=0,
                                        title=(
                                            f"Mostrar {deliverer['nome']} no mapa"
                                        ),
                                        **{
                                            "aria-label": (
                                                f"Mostrar {deliverer['nome']} "
                                                f"({deliverer['id']}) no mapa"
                                            )
                                        },
                                        className="deliverer-result-button",
                                        style=inline_style("deliverer-result-button"),
                                    ),
                                    style=inline_style(
                                        "deliverer-results-cell",
                                        {
                                            "borderLeft": "1px solid #edf0f4",
                                            "borderRadius": "8px 0 0 8px",
                                        },
                                    ),
                                ),
                                html.Td(
                                    deliverer["nome"],
                                    className="deliverer-results-cell",
                                    style=inline_style(
                                        "deliverer-results-cell"
                                    ),
                                ),
                                html.Td(
                                    f"{deliverer['distancia_km']:.2f} km",
                                    className="deliverer-results-cell",
                                    style=inline_style("deliverer-results-cell"),
                                ),
                                html.Td(
                                    f"{deliverer['tempo_estimado_min']} min",
                                    className="deliverer-results-cell",
                                    style=inline_style(
                                        "deliverer-results-cell",
                                        {
                                            "borderRight": "1px solid #edf0f4",
                                            "borderRadius": "0 8px 8px 0",
                                        },
                                    ),
                                ),
                            ],
                            className="deliverer-result-row",
                            style={"display": "table-row"},
                        )
                        for deliverer in deliverers
                    ]
                ),
            ],
            className="deliverer-results-table",
            style=inline_style("deliverer-results-table"),
        ),
        className="results-table-wrap",
        style=inline_style("results-table-wrap"),
    )
