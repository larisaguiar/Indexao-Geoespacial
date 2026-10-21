"""Interface para visualização e consulta da frota ."""

from collections import OrderedDict
from uuid import uuid4

import dash
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
import dash_leaflet as dl

from src.components import (
    MAP_CENTER,
    create_base_map_layer,
    create_map_legend,
    create_map_markers,
    create_results_list,
)
from src.fleet import (
    GeohashFleetIndex,
    find_deliverers_for_restaurant,
    generate_deliverers,
)
from src.restaurants import (
    AddressNotFoundError,
    GeocodingError,
    NominatimGeocoder,
    get_restaurant,
    search_restaurants,
)
from src.interface import inline_style

app = dash.Dash(
    __name__,
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Quicksand:wght@400;600;700&display=swap"
    ],
)
app.title = "TPHEll"

initial_fleet = generate_deliverers(60, seed=2026)
fleet_indexes = OrderedDict(
    [("initial", GeohashFleetIndex(initial_fleet))]
)
geocoder = NominatimGeocoder()


def get_fleet_index(index_key: str, fleet: list[dict]) -> GeohashFleetIndex:
    index = fleet_indexes.get(index_key)
    if index is not None:
        fleet_indexes.move_to_end(index_key)
        return index

    index = GeohashFleetIndex(fleet)
    fleet_indexes[index_key] = index
    while len(fleet_indexes) > 64:
        fleet_indexes.popitem(last=False)
    return index


app.layout = html.Main(
    [
        dcc.Store(id="fleet-store", data=initial_fleet),
        dcc.Store(id="fleet-index-key", data="initial"),
        dcc.Store(id="selected-deliverer-store"),
        html.Section(
            [
                html.Div(
                    [
                        html.Label(
                            "Restaurante ou região",
                            htmlFor="restaurant-select",
                            className="control-label",
                            style=inline_style("control-label"),
                        ),
                        dcc.Dropdown(
                            id="restaurant-select",
                            options=[],
                            value=None,
                            placeholder="Busque por nome, rua ou bairro",
                            searchable=True,
                            clearable=True,
                            optionHeight=56,
                            maxHeight=280,
                            className="restaurant-dropdown",
                        ),
                    ],
                    className="control-field restaurant-field",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "Raio de busca",
                                    htmlFor="radius-slider",
                                    className="control-label",
                                    style=inline_style("control-label"),
                                ),
                                html.Span(
                                    id="radius-value",
                                    children="5 km",
                                    className="control-value",
                                    style=inline_style("control-value"),
                                ),
                            ],
                            className="control-label-row",
                            style=inline_style("control-label-row"),
                        ),
                        dcc.Slider(
                            id="radius-slider",
                            min=1,
                            max=20,
                            step=1,
                            value=5,
                            marks={1: "1", 5: "5", 10: "10", 15: "15", 20: "20 km"},
                            className="radius-slider",
                        ),
                    ],
                    className="control-field radius-field",
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "Tamanho da frota",
                                    htmlFor="deliverer-count",
                                    className="control-label",
                                    style=inline_style("control-label"),
                                ),
                                html.Span(
                                    id="deliverer-count-value",
                                    children="60",
                                    className="control-value",
                                    style=inline_style("control-value"),
                                ),
                            ],
                            className="control-label-row",
                            style=inline_style("control-label-row"),
                        ),
                        dcc.Slider(
                            id="deliverer-count",
                            min=10,
                            max=200,
                            step=10,
                            value=60,
                            marks={10: "10", 100: "100", 200: "200"},
                            className="radius-slider",
                        ),
                    ],
                    className="control-field fleet-field",
                ),
                html.Button(
                    [html.Span("↻", className="button-icon"), "Gerar frota"],
                    id="generate-button",
                    n_clicks=0,
                    className="button button-secondary",
                    style=inline_style("button button-secondary"),
                ),
                html.Button(
                    [html.Span("⌕", className="button-icon"), "Buscar próximos"],
                    id="search-button",
                    n_clicks=0,
                    className="button button-primary",
                    style=inline_style("button button-primary"),
                ),
            ],
            className="control-panel",
            style=inline_style("control-panel"),
        ),
        html.Div(
            [
                html.Span(className="status-indicator"),
                html.Div(id="status-message", role="status"),
            ],
            id="status-banner",
            className="status-banner",
            style=inline_style("status-banner"),
        ),
        html.Div(
            [
                html.Section(
                    [
                        html.Div(
                            [
                                html.Span(className="map-status-dot"),
                                html.Div(
                                    [
                                        html.Strong("MAPA"),
                                        html.Span("Belo Horizonte, MG"),
                                    ],
                                    className="map-overlay-copy",
                                    style={
                                        "display": "grid",
                                        "gap": "3px",
                                    },
                                )
                            ],
                            className="map-overlay-heading",
                            style={
                                "display": "flex",
                                "alignItems": "center",
                                "gap": "10px",
                                "padding": "11px 14px",
                                "border": "1px solid rgb(225 231 238 / 90%)",
                                "borderRadius": "11px",
                                "backgroundColor": "rgb(255 255 255 / 95%)",
                                "boxShadow": "0 3px 12px rgb(16 42 67 / 14%)",
                                "backdropFilter": "blur(8px)",
                            },
                        ),
                        dl.Map(
                            id="fleet-map",
                            children=[create_base_map_layer()]
                            + create_map_markers(initial_fleet),
                            center=MAP_CENTER,
                            zoom=12,
                            className="fleet-map",
                        ),
                        html.Div(
                            create_map_legend(),
                            className="map-legend-overlay",
                            style={
                                "maxWidth": "min(68%, 560px)",
                                "border": "1px solid rgb(225 231 238 / 90%)",
                                "borderRadius": "11px",
                                "backgroundColor": "rgb(255 255 255 / 95%)",
                                "boxShadow": "0 3px 12px rgb(16 42 67 / 14%)",
                                "backdropFilter": "blur(8px)",
                            },
                        ),
                        html.Aside(
                            [
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.H2(
                                                    "Entregadores",
                                                    className="results-title",
                                                    style=inline_style("results-title"),
                                                ),
                                                html.P(
                                                    "Resultados por proximidade",
                                                    className="section-subtitle",
                                                    style=inline_style("section-subtitle"),
                                                ),
                                            ],
                                            className="results-heading-copy",
                                            style=inline_style("results-heading-copy"),
                                        ),
                                        html.Span(
                                            "0",
                                            id="matches-count",
                                            className="count-badge",
                                            style=inline_style("count-badge"),
                                        ),
                                        html.Button(
                                            "−",
                                            id="results-toggle",
                                            n_clicks=0,
                                            title="Recolher painel",
                                            **{"aria-label": "Recolher painel"},
                                            className="results-toggle",
                                            style=inline_style("results-toggle"),
                                        ),
                                    ],
                                    className="card-heading results-heading",
                                    style=inline_style("results-heading"),
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Span(
                                                    className="result-dot",
                                                    style={
                                                        "width": "8px",
                                                        "height": "8px",
                                                        "flex": "0 0 auto",
                                                        "borderRadius": "50%",
                                                        "backgroundColor": "#00a650",
                                                    },
                                                ),
                                                html.Span(
                                                    "No raio selecionado",
                                                    style={
                                                        "fontSize": "10px",
                                                        "fontWeight": 800,
                                                        "textTransform": "uppercase",
                                                        "letterSpacing": "0.55px",
                                                    },
                                                ),
                                            ],
                                            className="results-filter-label",
                                            style=inline_style("results-filter-label"),
                                        ),
                                        html.Div(
                                            html.P(
                                                "Selecione um restaurante e clique em "
                                                "“Buscar próximos”.",
                                                className="empty-state",
                                                style=inline_style("empty-state"),
                                            ),
                                            id="search-results",
                                            className="results-list",
                                        ),
                                    ],
                                    className="results-content",
                                    style=inline_style("results-content"),
                                ),
                                html.Div(
                                    "Tempo aproximado a 25 km/h, sem considerar trânsito.",
                                    className="results-footer",
                                    style=inline_style("results-footer"),
                                ),
                            ],
                            id="results-card",
                            className="results-card results-card--expanded",
                            style=inline_style("results-card"),
                        ),
                    ],
                    className="map-stage",
                ),
                html.Section(
                    [
                        html.Div(
                            [
                                html.Span(
                                    "FROTA TOTAL",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    str(len(initial_fleet)),
                                    id="fleet-total",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "entregadores no mapa",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-total",
                            style=inline_style("metric-card"),
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "DISPONÍVEIS",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    str(
                                        sum(
                                            item["status"] == "Disponível"
                                            for item in initial_fleet
                                        )
                                    ),
                                    id="fleet-available",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "prontos para entrega",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-available",
                            style=inline_style("metric-card"),
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "ENCONTRADOS",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    "0",
                                    id="fleet-matches",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "dentro do raio",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-matches",
                            style=inline_style("metric-card"),
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "RAIO DE BUSCA",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    "5 km",
                                    id="radius-summary",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "distância em linha reta",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-radius",
                            style=inline_style("metric-card"),
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "DISTÂNCIA MÉDIA",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    "—",
                                    id="average-distance",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "dos encontrados",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-distance",
                            style=inline_style("metric-card"),
                        ),
                        html.Div(
                            [
                                html.Span(
                                    "TEMPO MÉDIO",
                                    className="metric-label",
                                    style=inline_style("metric-label"),
                                ),
                                html.Strong(
                                    "—",
                                    id="average-eta",
                                    className="metric-value",
                                    style=inline_style("metric-value"),
                                ),
                                html.Span(
                                    "estimativa até o ponto",
                                    className="metric-hint",
                                    style=inline_style("metric-hint"),
                                ),
                            ],
                            className="metric-card metric-eta",
                            style=inline_style("metric-card"),
                        ),
                    ],
                    className="metrics-grid",
                    style={
                        "display": "grid",
                        "alignContent": "stretch",
                        "gap": "12px",
                        "minWidth": 0,
                    },
                ),
            ],
            className="workspace-grid",
        ),
        html.Footer(
            "Endereços do CSV · Geocodificação sob demanda · Entregadores fictícios",
            className="app-footer",
            style=inline_style("app-footer"),
        ),
    ],
    className="dashboard-shell",
    style=inline_style("dashboard-shell"),
)


@app.callback(
    Output("restaurant-select", "options"),
    Input("restaurant-select", "search_value"),
    State("restaurant-select", "value"),
)
def atualizar_opcoes_restaurantes(search_value, selected_id):
    restaurants = search_restaurants(search_value, limit=25)
    if selected_id and all(item["id"] != selected_id for item in restaurants):
        restaurants.insert(0, get_restaurant(selected_id))
    return [
        {"label": item["label"], "value": item["id"]}
        for item in restaurants
    ]


@app.callback(
    Output("fleet-store", "data"),
    Output("fleet-index-key", "data"),
    Output("fleet-map", "children"),
    Output("fleet-map", "center"),
    Output("status-message", "children"),
    Output("search-results", "children"),
    Output("fleet-total", "children"),
    Output("fleet-available", "children"),
    Output("fleet-matches", "children"),
    Output("matches-count", "children"),
    Output("average-distance", "children"),
    Output("average-eta", "children"),
    Input("generate-button", "n_clicks"),
    Input("search-button", "n_clicks"),
    State("radius-slider", "value"),
    State("deliverer-count", "value"),
    State("restaurant-select", "value"),
    State("fleet-store", "data"),
    State("fleet-index-key", "data"),
)
def atualizar_interface(
    n_gerar,
    n_buscar,
    raio,
    num_entregadores,
    restaurante_id,
    frota,
    fleet_index_key,
):
    triggered = ctx.triggered_id
    if triggered == "generate-button":
        frota = generate_deliverers(int(num_entregadores))
        fleet_index_key = uuid4().hex
        fleet_indexes[fleet_index_key] = GeohashFleetIndex(frota)
        while len(fleet_indexes) > 64:
            fleet_indexes.popitem(last=False)
        available_count = sum(item["status"] == "Disponível" for item in frota)
        return (
            frota,
            fleet_index_key,
            [create_base_map_layer()] + create_map_markers(frota),
            MAP_CENTER,
            f"Nova frota pronta: {len(frota)} entregadores gerados.",
            html.P(
                "Selecione um restaurante e clique em “Buscar próximos”.",
                className="empty-state",
            ),
            str(len(frota)),
            str(available_count),
            "0",
            "0",
            "—",
            "—",
        )

    if triggered == "search-button":
        if not restaurante_id:
            return (
                frota or [],
                fleet_index_key or "initial",
                [create_base_map_layer()] + create_map_markers(frota or []),
                MAP_CENTER,
                "Pesquise e selecione um estabelecimento do CSV antes da busca.",
                html.P(
                    "Selecione um restaurante para procurar entregadores.",
                    className="empty-state",
                ),
                str(len(frota or [])),
                str(sum(item["status"] == "Disponível" for item in (frota or []))),
                "0",
                "0",
                "—",
                "—",
            )
        try:
            restaurant = get_restaurant(restaurante_id)
            (
                (restaurant["latitude"], restaurant["longitude"]),
                approximate_location,
            ) = geocoder.geocode_with_neighborhood_fallback(
                restaurant["address"],
                restaurant["neighborhood"],
            )
            restaurant["localizacao_aproximada"] = approximate_location
        except GeocodingError as error:
            if isinstance(error, AddressNotFoundError):
                result_message = html.Div(
                    [
                        html.Strong("Endereço não encontrado no mapa."),
                        html.P(f"Endereço consultado: {restaurant['address']}"),
                        html.P(
                            "Confira o logradouro, número e bairro no CSV. "
                            "Você pode tentar novamente após conferir os dados."
                        ),
                    ]
                )
            else:
                result_message = html.Div(
                    [
                        html.Strong("Falha ao consultar o serviço de mapas."),
                        html.P(str(error)),
                        html.P(
                            f"Endereço consultado: {restaurant['address']}"
                        ),
                        html.P(
                            "Confira a conexão com a internet e tente a busca novamente."
                        ),
                    ]
                )
            return (
                frota or [],
                fleet_index_key or "initial",
                [create_base_map_layer()] + create_map_markers(frota or []),
                MAP_CENTER,
                f"Busca interrompida: {error}",
                result_message,
                str(len(frota or [])),
                str(sum(item["status"] == "Disponível" for item in (frota or []))),
                "0",
                "0",
                "—",
                "—",
            )

        radius_deliverers = find_deliverers_for_restaurant(
            restaurant,
            radius_km=float(raio),
            include_unavailable=True,
            index=get_fleet_index(fleet_index_key or "initial", frota or []),
        )
        available_matches = [
            item
            for item in radius_deliverers
            if item.get("status", "Disponível") == "Disponível"
        ]
        result_ids = {item["id"] for item in radius_deliverers}
        average_distance = (
            sum(item["distancia_km"] for item in available_matches)
            / len(available_matches)
            if available_matches
            else None
        )
        average_eta = (
            sum(item["tempo_estimado_min"] for item in available_matches)
            / len(available_matches)
            if available_matches
            else None
        )
        return (
            frota,
            fleet_index_key or "initial",
            [create_base_map_layer()]
            + create_map_markers(radius_deliverers, restaurant, result_ids),
            [restaurant["latitude"], restaurant["longitude"]],
            (
                (
                    f"Endereço exato não localizado; usando posição aproximada "
                    f"do bairro {restaurant['neighborhood']}. "
                    if approximate_location
                    else ""
                )
                + f"{len(available_matches)} entregador(es) disponível(is) em até "
                f"{raio} km de {restaurant['nome']}."
            ),
            create_results_list(available_matches),
            str(len(frota or [])),
            str(sum(item["status"] == "Disponível" for item in (frota or []))),
            str(len(available_matches)),
            str(len(available_matches)),
            f"{average_distance:.2f} km" if average_distance is not None else "—",
            f"{average_eta:.1f} min" if average_eta is not None else "—",
        )

    available_count = sum(
        item["status"] == "Disponível" for item in (frota or [])
    )
    return (
        frota or [],
        fleet_index_key or "initial",
        [create_base_map_layer()] + create_map_markers(frota or []),
        MAP_CENTER,
        f"Frota pronta: {len(frota or [])} entregadores no mapa.",
        html.P(
            "Selecione um restaurante e clique em “Buscar próximos”.",
            className="empty-state",
        ),
        str(len(frota or [])),
        str(available_count),
        "0",
        "0",
        "—",
        "—",
    )


@app.callback(
    Output("selected-deliverer-store", "data"),
    Output("fleet-map", "center", allow_duplicate=True),
    Output("fleet-map", "zoom"),
    Input({"type": "deliverer-result", "id": ALL}, "n_clicks"),
    State({"type": "deliverer-result", "id": ALL}, "id"),
    State("fleet-store", "data"),
    prevent_initial_call=True,
)
def focar_entregador(n_clicks, result_ids, frota):
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, dict):
        return no_update, no_update, no_update

    deliverer_id = triggered_id.get("id")
    deliverer = next(
        (item for item in (frota or []) if item["id"] == deliverer_id),
        None,
    )
    if deliverer is None:
        return no_update, no_update, no_update

    click_count = next(
        (
            clicks
            for clicks, result_id in zip(n_clicks or [], result_ids or [])
            if result_id.get("id") == deliverer_id
        ),
        0,
    )
    return (
        {"id": deliverer_id, "click": click_count},
        [deliverer["latitude"], deliverer["longitude"]],
        16,
    )


@app.callback(
    Output({"type": "courier-marker", "id": ALL}, "iconOptions"),
    Input("selected-deliverer-store", "data"),
    State({"type": "courier-marker", "id": ALL}, "id"),
    State({"type": "courier-marker", "id": ALL}, "iconOptions"),
    prevent_initial_call=True,
)
def destacar_entregador_selecionado(selected, marker_ids, icon_options):
    if not selected:
        return no_update

    updated_options = []
    for marker_id, options in zip(marker_ids or [], icon_options or []):
        updated = dict(options)
        marker_html = updated["html"].replace(
            "courier-map-icon--selected ", ""
        )
        if marker_id.get("id") == selected["id"]:
            marker_html = marker_html.replace(
                'class="courier-map-icon ',
                'class="courier-map-icon courier-map-icon--selected ',
                1,
            )
        updated["html"] = marker_html
        updated_options.append(updated)
    return updated_options


@app.callback(
    Output("radius-value", "children"),
    Input("radius-slider", "value"),
)
def mostrar_raio(raio):
    return f"{raio} km"


@app.callback(
    Output("deliverer-count-value", "children"),
    Input("deliverer-count", "value"),
)
def mostrar_tamanho_frota(quantidade):
    return str(quantidade)


@app.callback(
    Output("radius-summary", "children"),
    Input("radius-slider", "value"),
)
def mostrar_resumo_raio(raio):
    return f"{raio} km"


@app.callback(
    Output("results-card", "className"),
    Output("results-toggle", "children"),
    Output("results-toggle", "title"),
    Output("results-toggle", "aria-label"),
    Input("results-toggle", "n_clicks"),
    State("results-card", "className"),
)
def alternar_painel_resultados(n_clicks, class_name):
    expanded = "results-card--expanded" in (class_name or "")
    if expanded:
        return (
            "results-card results-card--collapsed",
            "+",
            "Expandir painel",
            "Expandir painel",
        )
    return (
        "results-card results-card--expanded",
        "−",
        "Recolher painel",
        "Recolher painel",
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
