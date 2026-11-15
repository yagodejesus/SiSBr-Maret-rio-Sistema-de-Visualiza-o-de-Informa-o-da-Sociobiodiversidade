"""
Dashboard de ocorrências de espécies costeiras e marinhas do Brasil.

Local:    python app.py                      -> http://127.0.0.1:8050
Railway:  gunicorn app:server (ver Procfile / railway.json)
"""

import math
import os

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash.exceptions import PreventUpdate

import contribuicoes as contrib
import dados

AZUL, OURO, CREME, VERDE = "#054163", "#cab54b", "#f3f2e6", "#64c5b0"
TINTA, TINTA2, GRADE = "#17252f", "#4b5a63", "#ebe8d8"
ESCALA = [[0, "#d7f0ea"], [0.45, VERDE], [1, AZUL]]  # sequencial: um só tom, claro -> escuro

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

BASES = {
    "HUMAN_OBSERVATION": "Observação humana",
    "PRESERVED_SPECIMEN": "Espécime preservado",
    "MATERIAL_SAMPLE": "Amostra de material",
    "MACHINE_OBSERVATION": "Observação por máquina",
    "OCCURRENCE": "Ocorrência",
    "LIVING_SPECIMEN": "Espécime vivo",
    "MATERIAL_CITATION": "Citação de material",
    "FOSSIL_SPECIMEN": "Fóssil",
}

MAPAS_BASE = {
    "claro": {"style": "carto-positron"},
    "oceano": {"style": "white-bg", "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/"
               "Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}", "attr": "Esri, GEBCO, NOAA"},
    "satelite": {"style": "white-bg", "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/"
                 "World_Imagery/MapServer/tile/{z}/{y}/{x}", "attr": "Esri, Maxar"},
    "ruas": {"style": "open-street-map"},
}

CENTRO_INICIAL = {"lat": -16.5, "lon": -44.0}
ZOOM_INICIAL = 3.5


def fmt(n):
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return "—"
    return f"{int(n):,}".replace(",", ".")


# ===================================================================== dados
ANO_MIN, ANO_MAX = dados.faixa_anos()
OPC_REINO = dados.opcoes("reino")
OPC_UF = dados.opcoes("uf")
OPC_BASE = [{"label": BASES.get(o["value"], o["value"]) + o["label"][len(o["value"]):],
             "value": o["value"]} for o in dados.opcoes("base_registro")]
OPC_CONJ = dados.opcoes("conjunto_dados", limite=400)

# ===================================================================== app
app = Dash(
    __name__,
    title=f"SiSBr-Maretório: Sistema de Visualização de Informação da Sociobiodiversidade "
          f"nos Maretórios {ANO_MIN} - {ANO_MAX}",
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
    ],
    suppress_callback_exceptions=True,
)
server = app.server


def rotulo(txt):
    return html.Label(txt, className="rotulo")


def dropdown(id_, opcoes=None, ph="Todos", **kw):
    return dcc.Dropdown(id=id_, options=opcoes or [], multi=True, placeholder=ph, **kw)


filtros = html.Div(className="cartao painel-filtros", children=[
    html.H3("Filtros"),
    html.Div("Todos os gráficos, o mapa e os números respondem a estes filtros.", className="sub"),

    rotulo("Recorte geográfico"),
    dcc.Checklist(id="f-recorte", value=["costeiro", "marinho"], inline=True,
                  options=[{"label": " Municípios costeiros", "value": "costeiro"},
                           {"label": " Sistema Marinho", "value": "marinho"}],
                  inputStyle={"marginRight": "4px"}, labelStyle={"marginRight": "14px"}),

    html.Div(className="grupo", children=[
        html.Div("Taxonomia", className="grupo-titulo"),
        rotulo("Espécie ou nome popular"),
        dropdown("f-especie", ph="Digite para buscar..."),
        rotulo("Reino"), dropdown("f-reino", OPC_REINO),
        rotulo("Classe"), dropdown("f-classe"),
        rotulo("Ordem"), dropdown("f-ordem"),
        rotulo("Família"), dropdown("f-familia"),
        dcc.Checklist(id="f-so-especie", value=[], className="mt-2",
                      options=[{"label": " Só registros identificados até espécie", "value": "s"}],
                      inputStyle={"marginRight": "4px"}),
    ]),

    html.Div(className="grupo", children=[
        html.Div("Local", className="grupo-titulo"),
        rotulo("Estado (UF)"), dropdown("f-uf", OPC_UF),
        rotulo("Município costeiro"), dropdown("f-municipio", ph="Todos (escolha a UF antes)"),
    ]),

    html.Div(className="grupo", children=[
        html.Div("Registro", className="grupo-titulo"),
        rotulo("Ano da observação"),
        dcc.RangeSlider(id="f-anos", min=ANO_MIN, max=ANO_MAX, step=1, value=[ANO_MIN, ANO_MAX],
                        marks={a: str(a) for a in range(1700, ANO_MAX + 1, 100) if a >= ANO_MIN},
                        tooltip={"placement": "bottom", "always_visible": False}),
        dcc.Checklist(id="f-sem-ano", value=["s"],
                      options=[{"label": " Incluir registros sem ano", "value": "s"}],
                      inputStyle={"marginRight": "4px"}),
        rotulo("Tipo de registro"), dropdown("f-base", OPC_BASE),
        rotulo("Conjunto de dados (fonte)"), dropdown("f-conjunto", OPC_CONJ),
    ]),

    html.Div(className="d-flex gap-2 mt-3", children=[
        dbc.Button("Limpar filtros", id="b-limpar", className="btn-contorno btn-sm"),
        dbc.Button("Baixar CSV", id="b-baixar", className="btn-azul btn-sm"),
    ]),
    html.Div("O CSV traz até 200 mil registros filtrados.", className="sub mt-1"),
    dcc.Download(id="download"),
])


def kpi(id_, rot, destaque=False):
    return dbc.Col(html.Div(className="kpi" + (" destaque" if destaque else ""), children=[
        html.Div(rot, className="rot"), html.Div("…", id=id_, className="val")]),
        xs=6, md=4, xl=2, className="mb-2")


kpis = dbc.Row([
    kpi("k-registros", "Registros"), kpi("k-especies", "Espécies"),
    kpi("k-familias", "Famílias"), kpi("k-municipios", "Municípios"),
    kpi("k-periodo", "Período"), kpi("k-contrib", "Contribuições", destaque=True),
], className="g-2 mb-2")


form_contrib = html.Div(className="form-contrib", children=[
    html.H3("Adicionar contribuição"),
    html.Div("Registre uma nova característica num ponto do mapa. Ela fica visível para "
             "todos como um marcador dourado.", className="sub"),
    html.Div("1. Escolha o local", className="grupo-titulo"),
    html.Div("Clique num ponto/célula do mapa, ou centralize o mapa na mira e use o botão.",
             className="sub mb-1"),
    dbc.Row([
        dbc.Col([html.Label("Latitude"), dbc.Input(id="c-lat", type="number", step="any",
                                                   placeholder="-23.5")], width=6),
        dbc.Col([html.Label("Longitude"), dbc.Input(id="c-lon", type="number", step="any",
                                                    placeholder="-45.1")], width=6),
    ], className="g-2"),
    dbc.Button("Usar o centro do mapa (mira)", id="b-centro", size="sm",
               className="btn-contorno w-100 mt-2"),
    html.Div("2. Descreva", className="grupo-titulo mt-3"),
    html.Label("Categoria *"),
    dbc.Select(id="c-categoria", options=[{"label": c, "value": c} for c in contrib.CATEGORIAS],
               value=contrib.CATEGORIAS[0]),
    html.Label("Característica *"),
    dbc.Input(id="c-caracteristica", maxLength=200,
              placeholder="Ex.: ninho de tartaruga, banco de algas, lixo na praia"),
    dbc.Row([
        dbc.Col([html.Label("Valor / medida"),
                 dbc.Input(id="c-valor", maxLength=200, placeholder="Ex.: 12 ninhos")], width=6),
        dbc.Col([html.Label("Data da observação"),
                 dbc.Input(id="c-data", type="date")], width=6),
    ], className="g-2"),
    html.Label("Espécie relacionada"),
    dbc.Input(id="c-especie", maxLength=200, placeholder="Opcional"),
    html.Label("Descrição"),
    dbc.Textarea(id="c-descricao", maxLength=2000, rows=3, placeholder="Opcional"),
    html.Label("Seu nome"),
    dbc.Input(id="c-autor", maxLength=120, placeholder="Opcional"),
    dbc.Button("Salvar contribuição", id="b-salvar", className="btn-ouro w-100 mt-3"),
    html.Div(id="c-msg", className="mt-2"),
])


aba_mapa = html.Div([
    dbc.Row([
        dbc.Col(md=8, children=[
            html.Div(className="cartao", children=[
                dbc.Row([
                    dbc.Col([rotulo("Visualização"),
                             dbc.RadioItems(id="m-modo", value="grade", inline=True,
                                            options=[{"label": "Grade agregada", "value": "grade"},
                                                     {"label": "Calor", "value": "calor"},
                                                     {"label": "Pontos (amostra)", "value": "pontos"}])],
                            lg=6),
                    dbc.Col([rotulo("Mapa base"),
                             dbc.Select(id="m-base", value="claro", size="sm",
                                        options=[{"label": "Claro", "value": "claro"},
                                                 {"label": "Oceano (batimetria)", "value": "oceano"},
                                                 {"label": "Satélite", "value": "satelite"},
                                                 {"label": "Ruas", "value": "ruas"}])], lg=3, xs=6),
                    dbc.Col([rotulo("Camadas"),
                             dbc.Checklist(id="m-camadas", value=["dados", "contrib", "mira"],
                                           options=[{"label": "Ocorrências", "value": "dados"},
                                                    {"label": "Contribuições", "value": "contrib"},
                                                    {"label": "Mira", "value": "mira"}],
                                           inline=True, switch=True)], lg=3, xs=6),
                ], className="g-2"),
                html.Div(className="mapa-wrap mt-2", children=[
                    dcc.Graph(id="mapa", style={"height": "640px"},
                              config={"scrollZoom": True, "displaylogo": False}),
                    html.Div(id="mira", className="mira"),
                ]),
                html.Div(className="d-flex justify-content-between align-items-start gap-2", children=[
                    html.Div(id="m-legenda", className="legenda-mapa"),
                    dbc.Button("Enquadrar resultados", id="b-enquadrar", size="sm",
                               className="btn-contorno mt-1 text-nowrap"),
                ]),
            ]),
        ]),
        dbc.Col(md=4, children=[
            html.Div(className="cartao", children=[
                html.H3("Detalhes"),
                html.Div(id="detalhe", className="detalhe",
                         children=html.Div("Clique num ponto, célula ou contribuição do mapa.",
                                           className="sub")),
            ]),
            html.Div(className="cartao", children=form_contrib),
        ]),
    ]),
])


def cartao_grafico(titulo, sub, id_, altura=340):
    return html.Div(className="cartao", children=[
        html.H3(titulo), html.Div(sub, className="sub"),
        dcc.Loading(type="dot", color=AZUL, children=dcc.Graph(
            id=id_, style={"height": f"{altura}px"}, config={"displaylogo": False})),
    ])


aba_analises = html.Div([
    dbc.Row([
        dbc.Col(cartao_grafico("Registros por ano", "Ocorrências registradas a cada ano (arraste para ver anos anteriores)",
                               "g-ano"), lg=6),
        dbc.Col(cartao_grafico("Espécies registradas por ano",
                               "Quantas espécies diferentes foram registradas a cada ano",
                               "g-riqueza"), lg=6),
    ]),
    dbc.Row([
        dbc.Col(cartao_grafico("Espécies mais registradas", "15 espécies com mais ocorrências",
                               "g-especies", 460), lg=6),
        dbc.Col(cartao_grafico("Classes mais registradas", "12 classes com mais ocorrências",
                               "g-classes", 460), lg=6),
    ]),
    dbc.Row([
        dbc.Col(cartao_grafico("Registros por estado", "Ocorrências por UF", "g-uf"), lg=7),
        dbc.Col(cartao_grafico("Tipo de registro", "Como a ocorrência foi documentada",
                               "g-base"), lg=5),
    ]),
    html.Div(className="cartao", children=[
        html.H3("Tabela de espécies"),
        html.Div("Até 500 espécies com mais registros. Clique no cabeçalho para ordenar e use a "
                 "linha de filtro para buscar.", className="sub"),
        dcc.Loading(type="dot", color=AZUL, children=dash_table.DataTable(
            id="t-especies", page_size=15, sort_action="native", filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"fontFamily": "Inter, sans-serif", "fontSize": 13, "padding": "6px 10px",
                        "textAlign": "left", "border": f"1px solid {GRADE}", "color": TINTA},
            style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#faf9f2"}],
        )),
    ]),
])


aba_contrib = html.Div([
    dbc.Row([
        dbc.Col(lg=4, children=[
            cartao_grafico("Contribuições por categoria", "Total enviado pelos usuários",
                           "g-contrib-cat", 300),
            cartao_grafico("Características mais citadas", "10 características mais frequentes",
                           "g-contrib-car", 300),
        ]),
        dbc.Col(lg=8, children=[html.Div(className="cartao", children=[
            html.Div(className="d-flex justify-content-between align-items-start", children=[
                html.Div([html.H3("Todas as contribuições"),
                          html.Div("Selecione uma linha para centralizar o mapa nela.",
                                   className="sub")]),
                dbc.Button("Baixar contribuições (CSV)", id="b-baixar-contrib", size="sm",
                           className="btn-azul"),
            ]),
            dash_table.DataTable(
                id="t-contrib", page_size=12, sort_action="native", filter_action="native",
                row_selectable="multi",
                columns=[{"name": n, "id": i} for i, n in [
                    ("id", "#"), ("categoria", "Categoria"), ("caracteristica", "Característica"),
                    ("valor", "Valor"), ("especie", "Espécie"), ("autor", "Autor"),
                    ("data_observacao", "Data obs."), ("lat", "Lat"), ("lon", "Lon")]],
                style_table={"overflowX": "auto"},
                style_cell={"fontFamily": "Inter, sans-serif", "fontSize": 13,
                            "padding": "6px 10px", "textAlign": "left",
                            "border": f"1px solid {GRADE}", "color": TINTA,
                            "maxWidth": 260, "overflow": "hidden", "textOverflow": "ellipsis"},
            ),
            dcc.Download(id="download-contrib"),
            html.Div(className="d-flex gap-2 mt-3 align-items-center", children=[
                dbc.Input(id="admin-token", type="password", size="sm",
                          placeholder="Senha de administrador", style={"maxWidth": 220}),
                dbc.Button("Excluir selecionadas", id="b-excluir", size="sm", color="danger",
                           outline=True),
                html.Div(id="excluir-msg", className="sub mb-0"),
            ]) if ADMIN_TOKEN else None,
        ])]),
    ]),
])


app.layout = html.Div([
    dcc.Store(id="filtros"),
    dcc.Store(id="vista", data={"center": CENTRO_INICIAL, "zoom": ZOOM_INICIAL}),
    dcc.Store(id="grade-cfg", data={"passo": 0.5, "caixa": None}),
    dcc.Store(id="contribs-versao", data=0),
    dcc.Store(id="contribs"),
    dcc.Interval(id="relogio", interval=60_000),  # atualiza contribuições de outros usuários
    html.Header(className="topo", children=[
        html.Div([
            html.H1(["SiSBr-Maretório: Sistema de Visualização de Informação da Sociobiodiversidade "
                     "nos Maretórios ", html.Span(f"{ANO_MIN} - {ANO_MAX}", className="periodo")]),
            html.P("Ocorrências de espécies nos municípios costeiros e no Sistema Marinho "
                   "· filtre, analise e contribua com novas características no mapa"),
        ]),
        html.Div(className="selo", children=[
            html.B(fmt(dados.kpis({})["registros"])), " registros na base"]),
    ]),
    html.Div(className="conteudo", children=dbc.Row([
        dbc.Col(filtros, lg=3),
        dbc.Col([
            kpis,
            dbc.Tabs(id="abas", active_tab="mapa", className="abas", children=[
                dbc.Tab(aba_mapa, label="Mapa", tab_id="mapa"),
                dbc.Tab(aba_analises, label="Análises", tab_id="analises"),
                dbc.Tab(aba_contrib, label="Contribuições", tab_id="contrib"),
            ]),
        ], lg=9),
    ])),
])


# ===================================================================== helpers
def estilo(fig, legenda=False):
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Inter, sans-serif", size=12, color=TINTA2),
        margin=dict(l=8, r=12, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legenda,
        hoverlabel=dict(bgcolor="white", bordercolor=AZUL, font=dict(color=TINTA, size=12)),
        separators=",.",
    )
    fig.update_xaxes(gridcolor=GRADE, linecolor=GRADE, zeroline=False, tickfont=dict(color=TINTA2))
    fig.update_yaxes(gridcolor=GRADE, linecolor=GRADE, zeroline=False, tickfont=dict(color=TINTA2))
    return fig


def vazio(msg="Sem dados para os filtros escolhidos"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=TINTA2, size=13),
                       x=0.5, y=0.5, xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return estilo(fig)


def barras_h(df, cor, rotulos=None, hover_nome="Registros"):
    df = df.iloc[::-1]
    y = rotulos.iloc[::-1] if rotulos is not None else df.categoria
    fig = go.Figure(go.Bar(
        x=df.registros, y=y, orientation="h", marker=dict(color=cor, cornerradius=4),
        hovertemplate="%{y}<br>" + hover_nome + ": %{x:,.0f}<extra></extra>"))
    # Reserva espaço para ~12 barras: poucas categorias não viram blocos gigantes
    fig.update_layout(bargap=max(0.25, 1 - len(df) / 12))
    fig.update_yaxes(automargin=True, gridcolor="rgba(0,0,0,0)")
    if df.registros.max() < 10:
        fig.update_xaxes(dtick=1)
    return estilo(fig)


def passo_para_zoom(z):
    for limite, passo in [(4, 0.5), (5.5, 0.25), (7, 0.1), (8.5, 0.05), (10, 0.02)]:
        if z < limite:
            return passo
    return 0.01


def caixa_vista(rel, centro, zoom):
    """[lon_min, lat_min, lon_max, lat_max] visível (com folga de 50%)."""
    der = (rel or {}).get("map._derived", {}).get("coordinates")
    if der:
        lons = [c[0] for c in der]
        lats = [c[1] for c in der]
        lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    else:
        meia = 360 / (2 ** zoom) * 1.6
        lo0, lo1 = centro["lon"] - meia, centro["lon"] + meia
        la0, la1 = centro["lat"] - meia * 0.7, centro["lat"] + meia * 0.7
    dl, da = (lo1 - lo0) * 0.5, (la1 - la0) * 0.5
    return [lo0 - dl, la0 - da, lo1 + dl, la1 + da]


# ===================================================================== callbacks: filtros
@app.callback(
    Output("filtros", "data"),
    Input("f-recorte", "value"), Input("f-especie", "value"), Input("f-reino", "value"),
    Input("f-classe", "value"), Input("f-ordem", "value"), Input("f-familia", "value"),
    Input("f-so-especie", "value"), Input("f-uf", "value"), Input("f-municipio", "value"),
    Input("f-anos", "value"), Input("f-sem-ano", "value"), Input("f-base", "value"),
    Input("f-conjunto", "value"),
)
def juntar_filtros(recorte, especie, reino, classe, ordem, familia, so_esp, uf, mun, anos,
                   sem_ano, base, conj):
    f = {"recorte": recorte, "especie": especie, "reino": reino, "classe": classe,
         "ordem": ordem, "familia": familia, "uf": uf, "municipio": mun,
         "base_registro": base, "conjunto_dados": conj,
         "so_especie": bool(so_esp), "sem_ano": bool(sem_ano)}
    if anos and (anos[0] > ANO_MIN or anos[1] < ANO_MAX):
        f["anos"] = anos
    return {k: v for k, v in f.items() if v not in (None, [], "")}


@app.callback(
    Output("f-classe", "options"), Output("f-ordem", "options"), Output("f-familia", "options"),
    Input("f-reino", "value"), Input("f-classe", "value"), Input("f-ordem", "value"),
    Input("f-recorte", "value"),
)
def cascata_taxonomia(reino, classe, ordem, recorte):
    base = {"recorte": recorte, "reino": reino}
    return (dados.opcoes("classe", base),
            dados.opcoes("ordem", dict(base, classe=classe)),
            dados.opcoes("familia", dict(base, classe=classe, ordem=ordem)))


@app.callback(Output("f-municipio", "options"), Input("f-uf", "value"), Input("f-recorte", "value"))
def cascata_municipio(uf, recorte):
    return dados.opcoes("municipio", {"recorte": recorte, "uf": uf}, limite=1000)


@app.callback(
    Output("f-especie", "options"),
    Input("f-especie", "search_value"), Input("f-reino", "value"), Input("f-classe", "value"),
    Input("f-ordem", "value"), Input("f-familia", "value"), State("f-especie", "value"),
)
def buscar_especie(texto, reino, classe, ordem, familia, selecionadas):
    if ctx.triggered_id == "f-especie" and texto is not None and len(texto.strip()) == 1:
        raise PreventUpdate
    tax = {"reino": reino, "classe": classe, "ordem": ordem, "familia": familia}
    opcoes = dados.busca_especie(texto, {k: v for k, v in tax.items() if v})
    valores = {o["value"] for o in opcoes}
    # As já selecionadas precisam continuar na lista, senão o Dropdown as descarta
    extras = [{"label": s, "value": s} for s in (selecionadas or []) if s not in valores]
    return extras + opcoes


@app.callback(
    Output("f-recorte", "value"), Output("f-especie", "value"), Output("f-reino", "value"),
    Output("f-classe", "value"), Output("f-ordem", "value"), Output("f-familia", "value"),
    Output("f-so-especie", "value"), Output("f-uf", "value"), Output("f-municipio", "value"),
    Output("f-anos", "value"), Output("f-sem-ano", "value"), Output("f-base", "value"),
    Output("f-conjunto", "value"),
    Input("b-limpar", "n_clicks"), prevent_initial_call=True,
)
def limpar(_):
    return (["costeiro", "marinho"], [], [], [], [], [], [], [], [], [ANO_MIN, ANO_MAX], ["s"],
            [], [])


@app.callback(Output("download", "data"), Input("b-baixar", "n_clicks"), State("filtros", "data"),
              prevent_initial_call=True)
def baixar(_, f):
    df = dados.exportar(f or {})
    return dcc.send_data_frame(df.to_csv, "ocorrencias_filtradas.csv", index=False)


# ===================================================================== callbacks: KPIs
@app.callback(
    Output("k-registros", "children"), Output("k-especies", "children"),
    Output("k-familias", "children"), Output("k-municipios", "children"),
    Output("k-periodo", "children"),
    Input("filtros", "data"),
)
def atualizar_kpis(f):
    k = dados.kpis(f or {})
    periodo = "—" if pd.isna(k["ano_min"]) else f"{int(k['ano_min'])}–{int(k['ano_max'])}"
    return (fmt(k["registros"]), fmt(k["especies"]), fmt(k["familias"]),
            fmt(k["municipios"]), periodo)


# ===================================================================== callbacks: contribuições
@app.callback(Output("contribs", "data"), Input("contribs-versao", "data"),
              Input("relogio", "n_intervals"))
def carregar_contribs(*_):
    df = contrib.listar()
    df["criado_em"] = df["criado_em"].astype(str)
    return df.to_dict("records")


@app.callback(Output("k-contrib", "children"), Input("contribs", "data"))
def kpi_contrib(dados_c):
    return fmt(len(dados_c or []))


@app.callback(
    Output("c-msg", "children"), Output("contribs-versao", "data"),
    Output("c-caracteristica", "value"), Output("c-valor", "value"),
    Output("c-especie", "value"), Output("c-descricao", "value"),
    Input("b-salvar", "n_clicks"),
    State("c-lat", "value"), State("c-lon", "value"), State("c-categoria", "value"),
    State("c-caracteristica", "value"), State("c-valor", "value"), State("c-especie", "value"),
    State("c-descricao", "value"), State("c-autor", "value"), State("c-data", "value"),
    State("contribs-versao", "data"),
    prevent_initial_call=True,
)
def salvar(_, lat, lon, cat, car, valor, esp, desc, autor, data_obs, versao):
    def erro(msg):
        return dbc.Alert(msg, color="warning", className="py-2 mb-0"), no_update, *[no_update] * 4

    if lat is None or lon is None:
        return erro("Escolha o local: clique no mapa ou use o centro do mapa.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return erro("Coordenadas inválidas.")
    if not (car or "").strip():
        return erro("Informe a característica observada.")
    if cat not in contrib.CATEGORIAS:
        return erro("Categoria inválida.")

    def limpo(v, n):
        v = (v or "").strip()
        return v[:n] or None

    contrib.adicionar(lat=float(lat), lon=float(lon), categoria=cat,
                      caracteristica=limpo(car, 200), valor=limpo(valor, 200),
                      especie=limpo(esp, 200), descricao=limpo(desc, 2000),
                      autor=limpo(autor, 120), data_observacao=limpo(data_obs, 10))
    ok = dbc.Alert("Contribuição salva! Ela já aparece no mapa.", color="success",
                   className="py-2 mb-0", duration=5000)
    return ok, (versao or 0) + 1, "", "", "", ""


@app.callback(Output("c-lat", "value", allow_duplicate=True),
              Output("c-lon", "value", allow_duplicate=True),
              Input("b-centro", "n_clicks"), State("vista", "data"), prevent_initial_call=True)
def usar_centro(_, vista):
    c = (vista or {}).get("center", CENTRO_INICIAL)
    return round(c["lat"], 6), round(c["lon"], 6)


@app.callback(
    Output("g-contrib-cat", "figure"), Output("g-contrib-car", "figure"),
    Output("t-contrib", "data"),
    Input("contribs", "data"),
)
def painel_contrib(dados_c):
    df = pd.DataFrame(dados_c or [])
    if df.empty:
        msg = "Ainda não há contribuições"
        return vazio(msg), vazio(msg), []
    cat = df.categoria.value_counts().head(10).rename_axis("categoria").reset_index(name="registros")
    car = (df.caracteristica.str.strip().str.lower().value_counts().head(10)
           .rename_axis("categoria").reset_index(name="registros"))
    tabela = df.assign(lat=df.lat.round(5), lon=df.lon.round(5)).to_dict("records")
    return (barras_h(cat, OURO, hover_nome="Contribuições"),
            barras_h(car, VERDE, hover_nome="Contribuições"), tabela)


@app.callback(Output("download-contrib", "data"), Input("b-baixar-contrib", "n_clicks"),
              prevent_initial_call=True)
def baixar_contrib(_):
    return dcc.send_data_frame(contrib.listar().to_csv, "contribuicoes.csv", index=False)


if ADMIN_TOKEN:
    @app.callback(
        Output("excluir-msg", "children"),
        Output("contribs-versao", "data", allow_duplicate=True),
        Input("b-excluir", "n_clicks"),
        State("admin-token", "value"), State("t-contrib", "derived_virtual_data"),
        State("t-contrib", "derived_virtual_selected_rows"), State("contribs-versao", "data"),
        prevent_initial_call=True,
    )
    def excluir(_, token, linhas, sel, versao):
        if token != ADMIN_TOKEN:
            return "Senha incorreta.", no_update
        ids = [linhas[i]["id"] for i in (sel or [])]
        if not ids:
            return "Nenhuma linha selecionada.", no_update
        contrib.excluir(ids)
        return f"{len(ids)} contribuição(ões) excluída(s).", (versao or 0) + 1


# ===================================================================== callbacks: mapa
@app.callback(
    Output("vista", "data"), Output("grade-cfg", "data"),
    Input("mapa", "relayoutData"), State("vista", "data"), State("grade-cfg", "data"),
    prevent_initial_call=True,
)
def acompanhar_vista(rel, vista, cfg):
    if not rel or "map.center" not in rel:
        raise PreventUpdate
    vista = {"center": rel["map.center"], "zoom": rel.get("map.zoom", vista["zoom"]),
             "foco": vista.get("foco", 0)}
    passo = passo_para_zoom(vista["zoom"])
    caixa = caixa_vista(rel, vista["center"], vista["zoom"]) if vista["zoom"] >= 6 else None

    atual = cfg.get("caixa")
    c = vista["center"]
    fora = atual is None or not (atual[0] < c["lon"] < atual[2] and atual[1] < c["lat"] < atual[3])
    # Só recalcula o mapa quando muda o nível de detalhe ou o centro sai da área já carregada
    if passo != cfg.get("passo") or (caixa is None) != (atual is None) or (caixa and fora):
        return vista, {"passo": passo, "caixa": caixa}
    return vista, no_update


@app.callback(
    Output("vista", "data", allow_duplicate=True),
    Output("grade-cfg", "data", allow_duplicate=True),
    Input("b-enquadrar", "n_clicks"), State("filtros", "data"), State("vista", "data"),
    prevent_initial_call=True,
)
def enquadrar(_, f, vista):
    r = dados.limites(f or {})
    if not r:
        raise PreventUpdate
    centro, zoom = r
    nova = {"center": centro, "zoom": zoom, "foco": (vista or {}).get("foco", 0) + 1}
    caixa = caixa_vista(None, centro, zoom) if zoom >= 6 else None
    return nova, {"passo": passo_para_zoom(zoom), "caixa": caixa}


@app.callback(Output("mira", "style"), Input("m-camadas", "value"))
def mostrar_mira(camadas):
    return {} if "mira" in (camadas or []) else {"display": "none"}


@app.callback(
    Output("mapa", "figure"), Output("m-legenda", "children"),
    Input("filtros", "data"), Input("m-modo", "value"), Input("m-base", "value"),
    Input("m-camadas", "value"), Input("contribs", "data"), Input("grade-cfg", "data"),
    State("vista", "data"),
)
def desenhar_mapa(f, modo, base, camadas, dados_c, cfg, vista):
    f = dict(f or {})
    camadas = camadas or []
    cfg = cfg or {"passo": 0.5, "caixa": None}
    if cfg.get("caixa"):
        f["caixa"] = cfg["caixa"]
    passo = cfg["passo"]
    fig = go.Figure()
    legenda = []

    if "dados" in camadas:
        if modo == "pontos":
            df = dados.pontos(f)
            nome = (df.especie.fillna("?") + df.nome_popular.map(
                lambda p: f" ({p})" if isinstance(p, str) else ""))
            local = (df.municipio.fillna("") + df.uf.map(lambda u: f" / {u}" if isinstance(u, str)
                                                        else "")).replace("", "—")
            fig.add_trace(go.Scattermap(
                lat=df.lat, lon=df.lon, mode="markers", name="Ocorrência",
                marker=dict(size=8, color=VERDE, opacity=0.75),
                customdata=list(zip(["p"] * len(df), df.id)),
                text=nome, hovertext=local,
                hovertemplate="<b>%{text}</b><br>%{hovertext}<extra></extra>"))
            legenda.append(html.Span(f"Ocorrência (amostra de até {fmt(len(df))} pontos)",
                                     className="l-dado"))
        else:
            df = dados.grade(f, passo)
            if len(df):
                z = df.registros.apply(math.log10)
                ticks = [v for v in [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000]
                         if v <= df.registros.max() * 1.5]
                barra = dict(title=dict(text="Registros", font=dict(size=11)), thickness=10,
                             len=0.6, tickvals=[math.log10(v) for v in ticks],
                             ticktext=[fmt(v) for v in ticks], tickfont=dict(size=10),
                             bgcolor="rgba(255,255,255,0.8)")
                dica = ("<b>%{customdata[2]:,.0f} registros</b><br>~%{customdata[3]:,.0f} espécies"
                        "<br>%{lat:.2f}, %{lon:.2f}<extra></extra>")
                cdata = list(zip(["g"] * len(df), [passo] * len(df), df.registros, df.especies))
                if modo == "calor":
                    fig.add_trace(go.Densitymap(
                        lat=df.lat, lon=df.lon, z=z, radius=max(8, int(28 - passo * 30)),
                        colorscale=ESCALA, colorbar=barra, customdata=cdata, hovertemplate=dica,
                        opacity=0.85))
                else:
                    tam = max(4, min(18, 5 + 3 * math.log2(max(passo, 0.01) / 0.01) / 2))
                    fig.add_trace(go.Scattermap(
                        lat=df.lat, lon=df.lon, mode="markers", name="Células",
                        marker=dict(size=tam, color=z, colorscale=ESCALA, opacity=0.8,
                                    colorbar=barra),
                        customdata=cdata, hovertemplate=dica))
                legenda.append(html.Span(
                    f"Células de {str(passo).replace('.', ',')}° — cor = nº de registros "
                    f"(escala log). Aproxime o mapa para mais detalhe.", className="l-dado"))

    if "contrib" in camadas and dados_c:
        dc = pd.DataFrame(dados_c)
        texto = dc.caracteristica + dc.valor.map(lambda v: f" — {v}" if isinstance(v, str) else "")
        # Anel azul por baixo + miolo dourado: destaca das ocorrências em qualquer mapa base
        fig.add_trace(go.Scattermap(lat=dc.lat, lon=dc.lon, mode="markers", hoverinfo="skip",
                                    marker=dict(size=17, color=AZUL), showlegend=False))
        fig.add_trace(go.Scattermap(
            lat=dc.lat, lon=dc.lon, mode="markers", name="Contribuição",
            marker=dict(size=12, color=OURO),
            customdata=list(zip(["c"] * len(dc), dc.id)), text=texto, hovertext=dc.categoria,
            hovertemplate="<b>%{text}</b><br>%{hovertext}<extra>Contribuição</extra>"))
        legenda.append(html.Span(f"Contribuição de usuário ({fmt(len(dc))})", className="l-contrib"))

    b = MAPAS_BASE[base]
    vista = vista or {}
    # Redesenha na posição atual; "foco" muda quando a tabela pede para centralizar
    mapa = dict(style=b["style"], center=vista.get("center", CENTRO_INICIAL),
                zoom=vista.get("zoom", ZOOM_INICIAL))
    if "tiles" in b:
        mapa["layers"] = [dict(below="traces", sourcetype="raster", source=[b["tiles"]],
                               sourceattribution=b["attr"])]
    fig.update_layout(map=mapa, margin=dict(l=0, r=0, t=0, b=0), uirevision=f"mapa-{vista.get('foco', 0)}",
                      showlegend=False, paper_bgcolor=CREME,
                      hoverlabel=dict(bgcolor="white", bordercolor=AZUL,
                                      font=dict(family="Inter, sans-serif", color=TINTA)))
    return fig, legenda


def item(rot, val):
    if val is None or (not isinstance(val, str) and pd.isna(val)) or val == "":
        return []
    return [html.Dt(rot), html.Dd(str(val))]


@app.callback(
    Output("detalhe", "children"),
    Output("c-lat", "value"), Output("c-lon", "value"),
    Input("mapa", "clickData"), State("filtros", "data"), State("contribs", "data"),
)
def clicar_mapa(click, f, dados_c):
    if not click:
        raise PreventUpdate
    p = click["points"][0]
    lat, lon = round(p["lat"], 6), round(p["lon"], 6)
    cd = p.get("customdata") or [None]
    tipo = cd[0]

    if tipo == "c":
        c = next((x for x in dados_c or [] if x["id"] == cd[1]), None)
        if not c:
            raise PreventUpdate
        corpo = html.Dl(
            item("Categoria", c["categoria"]) + item("Característica", c["caracteristica"])
            + item("Valor", c.get("valor")) + item("Espécie", c.get("especie"))
            + item("Descrição", c.get("descricao")) + item("Autor", c.get("autor"))
            + item("Data da observação", c.get("data_observacao"))
            + item("Enviada em", (c.get("criado_em") or "")[:16])
            + item("Coordenadas", f"{c['lat']:.5f}, {c['lon']:.5f}"))
        return [dbc.Badge("Contribuição", color="warning", text_color="dark", className="mb-1"),
                corpo], lat, lon

    if tipo == "p":
        r = dados.detalhe(cd[1])
        if not r:
            raise PreventUpdate
        corpo = html.Dl(
            item("Espécie / táxon", r.get("especie") or r.get("taxon"))
            + item("Nome popular", r.get("nome_popular"))
            + item("Família", r.get("familia")) + item("Classe", r.get("classe"))
            + item("Local", " / ".join(x for x in [r.get("municipio"), r.get("uf")]
                                      if isinstance(x, str)))
            + item("Data", "/".join(str(int(x)) for x in [r.get("mes"), r.get("ano")]
                                    if x is not None and not pd.isna(x)))
            + item("Tipo de registro", BASES.get(r.get("base_registro"), r.get("base_registro")))
            + item("Nº de indivíduos", r.get("n_individuos"))
            + item("Fonte", r.get("conjunto_dados"))
            + item("Coordenadas", f"{r['lat']:.5f}, {r['lon']:.5f}"))
        return [dbc.Badge("Ocorrência", color="info", className="mb-1"), corpo], lat, lon

    if tipo == "g":
        passo = cd[1]
        df = dados.celula(f or {}, p["lat"], p["lon"], passo)
        lista = html.Ol([html.Li([html.I(e), f" — {pop}" if isinstance(pop, str) else "",
                                  html.Span(f" ({fmt(n)})", className="text-muted")])
                         for e, pop, n in zip(df.especie, df["pop"], df.n)],
                        className="ps-3 mb-0")
        return [dbc.Badge("Célula da grade", color="primary", className="mb-1"),
                html.Div(f"{fmt(cd[2])} registros · ~{fmt(cd[3])} espécies · "
                         f"{lat:.3f}, {lon:.3f}", className="mb-2"),
                html.Div("Espécies mais registradas aqui:", className="sub"), lista], lat, lon

    return no_update, lat, lon


@app.callback(
    Output("vista", "data", allow_duplicate=True),
    Output("grade-cfg", "data", allow_duplicate=True),
    Output("abas", "active_tab"),
    Input("t-contrib", "selected_rows"), State("t-contrib", "data"), State("vista", "data"),
    prevent_initial_call=True,
)
def focar_contrib(sel, linhas, vista):
    if not sel:
        raise PreventUpdate
    c = linhas[sel[-1]]
    centro, zoom = {"lat": c["lat"], "lon": c["lon"]}, 11
    nova = {"center": centro, "zoom": zoom, "foco": (vista or {}).get("foco", 0) + 1}
    return nova, {"passo": passo_para_zoom(zoom), "caixa": caixa_vista(None, centro, zoom)}, "mapa"


# ===================================================================== callbacks: análises
@app.callback(
    Output("g-ano", "figure"), Output("g-riqueza", "figure"), Output("g-especies", "figure"),
    Output("g-classes", "figure"), Output("g-uf", "figure"), Output("g-base", "figure"),
    Output("t-especies", "data"), Output("t-especies", "columns"),
    Input("filtros", "data"), Input("abas", "active_tab"),
)
def analises(f, aba):
    if aba != "analises":
        raise PreventUpdate
    f = f or {}

    anos = dados.por_ano(f)
    if len(anos):
        g_ano = estilo(go.Figure(go.Scatter(
            x=anos.ano, y=anos.registros, mode="lines", line=dict(color=AZUL, width=2),
            hovertemplate="%{x}: %{y:,.0f} registros<extra></extra>")))
        g_riq = estilo(go.Figure(go.Scatter(
            x=anos.ano, y=anos.especies, mode="lines", line=dict(color=VERDE, width=2),
            hovertemplate="%{x}: %{y:,.0f} espécies<extra></extra>")))
        acum = anos.registros.cumsum() / anos.registros.sum()
        inicio = int(anos.ano[acum >= 0.01].iloc[0])
        for g in (g_ano, g_riq):
            g.update_layout(hovermode="x")
            g.update_xaxes(range=[min(inicio, int(anos.ano.max()) - 5) - 1, int(anos.ano.max()) + 1])
            g.update_xaxes(showspikes=True, spikecolor=TINTA2, spikethickness=1, spikedash="dot")
    else:
        g_ano = g_riq = vazio()

    esp = dados.top("especie", f, 15)
    if len(esp):
        rot = esp.categoria + esp.nome_popular.map(lambda p: f" ({p})" if isinstance(p, str) else "")
        rot = rot.map(lambda s: s if len(s) <= 48 else s[:46] + "…")
        g_esp = barras_h(esp, VERDE, rot)
    else:
        g_esp = vazio()

    cla = dados.top("classe", f, 12)
    g_cla = barras_h(cla, AZUL) if len(cla) else vazio()

    uf = dados.top("uf", f, 30)
    if len(uf):
        g_uf = estilo(go.Figure(go.Bar(
            x=uf.categoria, y=uf.registros, marker=dict(color=AZUL, cornerradius=4),
            hovertemplate="%{x}: %{y:,.0f} registros<extra></extra>")))
        g_uf.update_layout(bargap=max(0.2, 1 - len(uf) / 20))
    else:
        g_uf = vazio()

    base = dados.top("base_registro", f, 10)
    if len(base):
        base = base.assign(categoria=base.categoria.map(lambda b: BASES.get(b, b)))
        g_base = barras_h(base, VERDE)
    else:
        g_base = vazio()

    tab = dados.tabela_especies(f)
    colunas = [{"name": c, "id": c, "type": "numeric" if tab[c].dtype.kind in "iuf" else "text"}
               for c in tab.columns]
    return g_ano, g_riq, g_esp, g_cla, g_uf, g_base, tab.to_dict("records"), colunas


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 8050))
    host = "0.0.0.0" if "PORT" in os.environ else "127.0.0.1"
    if os.environ.get("DEBUG") == "1":
        app.run(host=host, port=porta, debug=True)
    else:
        from waitress import serve
        print(f"Dashboard em http://{host}:{porta}", flush=True)
        serve(server, host=host, port=porta, threads=8)
