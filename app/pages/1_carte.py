"""
Page de cartographie.

Fonctionnalités :
- Affichage interactif de la carte de France.
- Visualisation de l'Indice de Besoin de Mobilisation (IBM).
- Application de filtres géographiques.
- Affichage des informations principales d'un territoire.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402
from common import BLANK_MAP_STYLE, MAP_PROVIDER, communes_geo, legend_html, number, require_results, setup, source_note  # noqa: E402

from src import dashboard  # noqa: E402

setup("Carte")
df = require_results()
st.title("Carte des communes")

# --- Filtres (une ligne au-dessus de la carte) ------------------------------
deps = dashboard.department_options(df)
f1, f2, f3 = st.columns([1, 2, 1])
indicator = f1.radio(
    "Indicateur",
    list(dashboard.INDICATORS),
    format_func=lambda k: {"IBM": "IBM — besoin de mobilisation", "IED": "IED — enjeu extrême droite"}[k],
)
selected = f2.multiselect(
    "Départements", options=list(deps), format_func=deps.get, placeholder="Toute la métropole"
)
only_priority = f3.toggle("Seulement les communes prioritaires", help="Les 20 % de communes à l'IBM le plus élevé.")

filters = dashboard.Filters(departments=selected, only_priority=only_priority)
shown = filters.apply(df)

# --- Carte -----------------------------------------------------------------
geo = communes_geo()
if selected:
    geo = geo[geo["DEP"].isin(selected)]
highlight = set(shown.index) if only_priority else None


@st.cache_data(show_spinner="Préparation de la carte…", max_entries=4)
def features(indicator: str, deps_key: tuple, only_priority: bool):
    return dashboard.map_features(geo, indicator, highlight)


data = features(indicator, tuple(sorted(selected)), only_priority)

bounds = geo.total_bounds  # xmin, ymin, xmax, ymax
view = pdk.data_utils.compute_view([[bounds[0], bounds[1]], [bounds[2], bounds[3]]])
view.zoom = view.zoom if selected else 5.0

layer = pdk.Layer(
    "GeoJsonLayer",
    data,
    pickable=True,
    stroked=True,
    filled=True,
    get_fill_color="properties.fill",
    get_line_color="properties.fill",  # liseré de la couleur de la commune : pas de jointures blanches
    line_width_min_pixels=0.5,
    auto_highlight=True,
    highlight_color=[11, 11, 11, 90],
)
tooltip = {
    "html": "<b>{LIBGEO}</b> · {departement}<br/>{population}<br/>"
    "IBM <b>{IBM}</b> · IED <b>{IED}</b><br/>D {D} · V {V} · J {J}",
    "style": {"backgroundColor": "#fcfcfb", "color": "#0b0b0b", "fontSize": "13px",
              "boxShadow": "0 1px 4px rgba(0,0,0,.25)"},
}

left, right = st.columns([4, 1])
left.pydeck_chart(
    pdk.Deck(layers=[layer], initial_view_state=view, map_style=BLANK_MAP_STYLE, map_provider=MAP_PROVIDER, tooltip=tooltip),
    height=680,
)
with right:
    st.markdown(legend_html(dashboard.legend(indicator, df), indicator), unsafe_allow_html=True)
    if only_priority:
        st.markdown(legend_html([("#ebeae6", "Commune non prioritaire")]), unsafe_allow_html=True)
    st.caption("Classes calculées sur toute la métropole : les couleurs ne changent pas quand on filtre.")
    stats = dashboard.summary(shown, df)
    st.metric("Communes affichées", number(stats["communes"]))
    st.metric("Habitants", number(stats["population"]))
    if not only_priority:
        st.metric("dont communes prioritaires", number(stats["prioritaires"]))

st.caption("Survoler une commune pour voir ses indicateurs. Détail complet : page Fiche territoire.")
source_note()
