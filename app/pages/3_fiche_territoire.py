"""
Page de fiche territoire.

Fonctionnalités :
- Présentation détaillée d'une commune.
- Affichage des composantes de l'IBM.
- Visualisation des principaux indicateurs.
- Historique des résultats électoraux.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402
from common import BLANK_MAP_STYLE, MAP_PROVIDER, communes_geo, number, require_results, setup, source_note  # noqa: E402

from src import dashboard, mapping  # noqa: E402

setup("Fiche territoire")
df = require_results()

labels = df["recherche"].sort_values()
options = list(labels.index)
# Commune passée dans l'adresse (…/fiche?commune=59512), pour partager une fiche
# Un nouveau paramètre d'adresse est appliqué une seule fois : ensuite, le
# choix fait dans la liste l'emporte (et met l'adresse à jour).
requested = st.query_params.get("commune")
if requested in options and requested != st.session_state.get("_commune_from_url"):
    st.session_state["commune"] = requested
    st.session_state["_commune_from_url"] = requested
code = st.selectbox(
    "Commune",
    options=options,
    key="commune",
    index=None,
    format_func=lambda c: labels[c],
    placeholder="Taper le nom d'une commune…",
)
if code is None:
    st.title("Fiche territoire")
    st.info("Choisir une commune pour afficher sa fiche.")
    st.stop()

st.query_params["commune"] = code
st.session_state["_commune_from_url"] = code
row = df.loc[code]
n_ibm, n_ied = df["IBM"].notna().sum(), df["IED"].notna().sum()
st.title(row["LIBGEO"])
st.markdown(
    f"{row['departement']} ({row['DEP']}) · code INSEE {code} · {number(row['population'])} habitants"
    + (" · **commune prioritaire**" if row["prioritaire"] else "")
)
if row["population"] < dashboard.SMALL_COMMUNE:
    st.warning(
        f"Commune de moins de {number(dashboard.SMALL_COMMUNE)} habitants : les taux reposent sur peu de "
        "personnes et peuvent varier fortement d'une année à l'autre. À interpréter avec prudence.",
        icon="⚠️",
    )

# --- Indicateurs principaux ----------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
fmt = lambda v: "—" if pd.isna(v) else f"{v:.2f}".replace(".", ",")  # noqa: E731
c1.metric("IBM", fmt(row["IBM"]), help=dashboard.INDICATORS["IBM"])
c2.metric("Rang IBM", "—" if pd.isna(row["rang_IBM"]) else f"{number(row['rang_IBM'])} / {number(n_ibm)}",
          help="1 = IBM le plus élevé de métropole")
c3.metric("IED", fmt(row["IED"]), help=dashboard.INDICATORS["IED"])
c4.metric("Rang IED", "—" if pd.isna(row["rang_IED"]) else f"{number(row['rang_IED'])} / {number(n_ied)}")

# --- Composantes de l'IBM -----------------------------------------------------
st.subheader("Composantes de l'IBM")
st.caption("Chaque composante va de 0 (besoin le plus faible de métropole) à 1 (le plus fort). "
           "Le trait gris marque la médiane métropolitaine.")
comp = pd.DataFrame(
    {
        "composante": [f"{k} — {v}" for k, v in dashboard.COMPONENTS.items()],
        "commune": [row[k] for k in dashboard.COMPONENTS],
        "médiane": [df[k].median() for k in dashboard.COMPONENTS],
    }
)
base = alt.Chart(comp).encode(y=alt.Y("composante:N", title=None, sort=None, axis=alt.Axis(labelLimit=320, labelFontSize=13)))
bars = base.mark_bar(color=mapping.PALETTES["IBM"][2], cornerRadiusEnd=4, height=18).encode(
    x=alt.X("commune:Q", scale=alt.Scale(domain=[0, 1]), title=None, axis=alt.Axis(tickCount=5, format=".1f")),
    tooltip=[alt.Tooltip("composante:N", title="Composante"), alt.Tooltip("commune:Q", title="Commune", format=".2f"),
             alt.Tooltip("médiane:Q", title="Médiane métropole", format=".2f")],
)
ticks = base.mark_tick(color="#52514e", thickness=2, size=26).encode(x="médiane:Q")
labels_ = base.mark_text(align="left", dx=6, color="#0b0b0b").encode(
    x="commune:Q", text=alt.Text("commune:Q", format=".2f")
)
st.altair_chart(
    (bars + ticks + labels_).properties(height=140).configure_view(stroke=None)
    .configure_axis(gridColor="#e4e3df", domainColor="#c3c2b7", labelColor="#52514e"),
    width="stretch",
)

# --- Variables brutes ---------------------------------------------------------
st.subheader("Données de la commune")
profile = dashboard.commune_profile(df, code)
shown = pd.DataFrame(
    {
        "Indicateur": profile["libellé"],
        "Commune": [dashboard.format_value(v, u, dashboard.VARIABLES[k][2])
                    for k, v, u in zip(profile.index, profile["commune"], profile["unité"])],
        "Département (médiane)": [dashboard.format_value(v, u, dashboard.VARIABLES[k][2])
                                  for k, v, u in zip(profile.index, profile["département (médiane)"], profile["unité"])],
        "Métropole (médiane)": [dashboard.format_value(v, u, dashboard.VARIABLES[k][2])
                                for k, v, u in zip(profile.index, profile["France (médiane)"], profile["unité"])],
        "Centile": profile["centile"],
    }
)
st.dataframe(
    shown,
    hide_index=True,
    width="stretch",
    column_config={
        "Centile": st.column_config.ProgressColumn(
            "Position en métropole", min_value=0, max_value=100, format="%.0f",
            help="Part des communes ayant une valeur plus faible. Pour le niveau de vie, "
                 "une position basse traduit un besoin plus fort.",
        )
    },
)
notes = []
if row.get("P_source") == "epci":
    notes.append("le taux de pauvreté est celui de l'intercommunalité (secret statistique au niveau communal)")
if row.get("R_source") == "epci":
    notes.append("le niveau de vie médian est celui de l'intercommunalité")
if notes:
    st.caption("Note : " + " ; ".join(notes) + ".")

# --- Historique électoral -----------------------------------------------------
st.subheader("Participation et vote")
elections = pd.DataFrame(
    {
        "scrutin": ["Présidentielle 2017", "Présidentielle 2022", "Législatives 2024"],
        "Commune": [row["A2017"], row["A2022"], row["A2024"]],
        "Médiane métropole": [df["A2017"].median(), df["A2022"].median(), df["A2024"].median()],
    }
)
e1, e2 = st.columns([3, 2])
with e1:
    st.caption("Abstention au 1er tour (%)")
    long = elections.melt("scrutin", var_name="série", value_name="abstention")
    chart = (
        alt.Chart(long)
        .mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=70, filled=True))
        .encode(
            x=alt.X("scrutin:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("abstention:Q", title=None, scale=alt.Scale(zero=True)),
            color=alt.Color("série:N", scale=alt.Scale(domain=["Commune", "Médiane métropole"],
                                                      range=["#2a78d6", "#8a8984"]),
                            legend=alt.Legend(orient="top", title=None)),
            strokeDash=alt.StrokeDash("série:N", scale=alt.Scale(domain=["Commune", "Médiane métropole"],
                                                                 range=[[1, 0], [4, 3]]), legend=None),
            tooltip=[alt.Tooltip("scrutin:N", title="Scrutin"), alt.Tooltip("série:N", title="Série"),
                     alt.Tooltip("abstention:Q", title="Abstention (%)", format=".1f")],
        )
        .properties(height=220)
        .configure_view(stroke=None)
        .configure_axis(gridColor="#e4e3df", domainColor="#c3c2b7", labelColor="#52514e")
    )
    st.altair_chart(chart, width="stretch")
with e2:
    st.metric("Score RN, présidentielle 2022 (1er tour)", dashboard.format_value(row["RN"], "%", 1),
              delta=None if pd.isna(row["delta_RN"]) else dashboard.format_value(row["delta_RN"], "pts depuis 2017", 1),
              delta_color="off")
    st.metric("Médiane métropole", dashboard.format_value(df["RN"].median(), "%", 1))

# --- Carte du département -----------------------------------------------------
st.subheader(f"La commune dans son département — {row['departement']}")
geo = communes_geo()
dep_geo = geo[geo["DEP"] == row["DEP"]]
data = dashboard.map_features(dep_geo, "IBM")
selected = dep_geo[dep_geo["code_commune"] == code]
b = dep_geo.total_bounds
view = pdk.data_utils.compute_view([[b[0], b[1]], [b[2], b[3]]])
layers = [
    pdk.Layer("GeoJsonLayer", data, pickable=True, stroked=True, filled=True,
              get_fill_color="properties.fill", get_line_color="properties.fill", line_width_min_pixels=0.5),
    pdk.Layer("GeoJsonLayer", selected.__geo_interface__, stroked=True, filled=False,
              get_line_color=[11, 11, 11], line_width_min_pixels=3),
]
m1, m2 = st.columns([3, 2])
m1.pydeck_chart(
    pdk.Deck(layers=layers, initial_view_state=view, map_style=BLANK_MAP_STYLE, map_provider=MAP_PROVIDER,
             tooltip={"html": "<b>{LIBGEO}</b><br/>IBM {IBM} · IED {IED}",
                      "style": {"backgroundColor": "#fcfcfb", "color": "#0b0b0b"}}),
    height=420,
)
with m2:
    st.caption("Communes du département à l'IBM le plus proche")
    near = dashboard.neighbours(df, code, n=8)
    st.dataframe(
        near[["LIBGEO", "population", "IBM", "IED"]],
        hide_index=True,
        width="stretch",
        column_config={
            "LIBGEO": "Commune",
            "population": st.column_config.NumberColumn("Habitants", format="localized"),
            "IBM": st.column_config.NumberColumn("IBM", format="%.2f"),
            "IED": st.column_config.NumberColumn("IED", format="%.2f"),
        },
    )
source_note()
