"""
Page de classement des territoires.

Fonctionnalités :
- Classement des communes selon leur IBM.
- Tri et filtrage des résultats.
- Recherche d'une commune.
- Comparaison entre plusieurs territoires.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from common import fiche_url, number, require_results, setup, source_note  # noqa: E402

from src import dashboard, mapping  # noqa: E402

setup("Classement")
df = require_results()
st.title("Classement des communes")

# --- Filtres ----------------------------------------------------------------
deps = dashboard.department_options(df)
f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
selected = f1.multiselect("Départements", list(deps), format_func=deps.get, placeholder="Toute la métropole")
min_pop = f2.selectbox(
    "Habitants (minimum)", [0, 500, 2_000, 5_000, 10_000, 20_000, 50_000],
    format_func=lambda v: "Toutes les communes" if v == 0 else f"{number(v)} et plus",
)
ied_classes = f3.multiselect(
    "Classe d'IED", [5, 4, 3, 2, 1],
    format_func=lambda c: {5: "5 — 20 % les plus élevés", 1: "1 — 20 % les plus faibles"}.get(c, str(c)),
    placeholder="Toutes",
)
sort_by = f4.radio("Trier par", ["IBM", "IED"], horizontal=True)
only_priority = st.toggle("Seulement les communes prioritaires (20 % d'IBM le plus élevé)")
query = st.text_input("Rechercher une commune", placeholder="Nom de commune…")

filters = dashboard.Filters(selected, min_pop, only_priority, ied_classes)
table = dashboard.ranking(filters.apply(df), sort_by)
if query:
    table = table[table["LIBGEO"].str.contains(query, case=False, regex=False)]

stats = dashboard.summary(table, df)
st.caption(
    f"{number(stats['communes'])} communes · {number(stats['population'])} habitants · "
    f"{number(stats['prioritaires'])} communes prioritaires"
)

table = table.assign(fiche=[fiche_url(c) for c in table.index])
columns = ["LIBGEO", "fiche", "departement", "population", "IBM", "rang_IBM", "IED", "rang_IED", "D", "V", "J",
           "A2022", "P", "C", "Y", "RN"]
st.dataframe(
    table[columns],
    hide_index=True,
    width="stretch",
    height=480,
    column_config={
        "LIBGEO": st.column_config.TextColumn("Commune", pinned=True),
        "fiche": st.column_config.LinkColumn("Fiche", display_text="Ouvrir", help="Fiche détaillée de la commune"),
        "departement": "Département",
        "population": st.column_config.NumberColumn("Habitants", format="localized"),
        "IBM": st.column_config.ProgressColumn("IBM", min_value=0, max_value=1, format="%.2f"),
        "rang_IBM": st.column_config.NumberColumn("Rang IBM", help="1 = IBM le plus élevé de métropole"),
        "IED": st.column_config.ProgressColumn("IED", min_value=0, max_value=1, format="%.2f"),
        "rang_IED": st.column_config.NumberColumn("Rang IED"),
        "D": st.column_config.NumberColumn("D", help=dashboard.COMPONENTS["D"], format="%.2f"),
        "V": st.column_config.NumberColumn("V", help=dashboard.COMPONENTS["V"], format="%.2f"),
        "J": st.column_config.NumberColumn("J", help=dashboard.COMPONENTS["J"], format="%.2f"),
        "A2022": st.column_config.NumberColumn("Abst. 2022 (%)", format="%.1f"),
        "P": st.column_config.NumberColumn("Pauvreté (%)", format="%.1f"),
        "C": st.column_config.NumberColumn("Chômage (%)", format="%.1f"),
        "Y": st.column_config.NumberColumn("19-25 ans (%)", format="%.1f"),
        "RN": st.column_config.NumberColumn("RN 2022 (%)", format="%.1f"),
    },
)
export = table[["LIBGEO", "DEP", "departement", "population", *dashboard.VARIABLES, "PC", "D", "V", "J",
                "IBM", "rang_IBM", "IED", "rang_IED", "prioritaire"]]
st.download_button(
    "Télécharger la sélection (CSV)",
    export.to_csv(sep=";", decimal=",", encoding="utf-8-sig"),  # s'ouvre directement dans Excel
    file_name="classement_communes.csv",
    mime="text/csv",
)

# --- Comparaison ------------------------------------------------------------
st.subheader("Comparer des communes")
default = list(table.index[:3])
codes = st.multiselect(
    "Communes à comparer (jusqu'à 6)",
    options=list(df.index),
    default=default,
    format_func=lambda c: df.at[c, "recherche"],
    max_selections=6,
)
if codes:
    comp = df.loc[codes]
    long = comp[["recherche", *dashboard.COMPONENTS, "IBM", "IED"]].melt(
        id_vars="recherche", var_name="indicateur", value_name="valeur"
    )
    order = [*dashboard.COMPONENTS, "IBM", "IED"]
    # Une petite barre par indicateur et par commune ; une seule couleur
    # (couleur IBM) : la commune est nommée sur l'axe, pas codée par la couleur.
    chart = (
        alt.Chart(long)
        .mark_bar(color=mapping.PALETTES["IBM"][2], cornerRadiusEnd=4, height=14)
        .encode(
            x=alt.X("valeur:Q", scale=alt.Scale(domain=[0, 1]), title=None, axis=alt.Axis(grid=True, tickCount=5)),
            y=alt.Y("recherche:N", title=None, sort=codes),
            tooltip=[alt.Tooltip("recherche:N", title="Commune"), alt.Tooltip("indicateur:N", title="Indicateur"),
                     alt.Tooltip("valeur:Q", title="Valeur", format=".2f")],
        )
        .properties(width=150, height=alt.Step(22))
        .facet(column=alt.Column("indicateur:N", sort=order, title=None,
                                 header=alt.Header(labelFontWeight="bold")))
        .configure_view(stroke=None)
        .configure_axis(gridColor="#e4e3df", domainColor="#c3c2b7", labelColor="#52514e")
    )
    st.altair_chart(chart)
    st.dataframe(
        pd.DataFrame(
            {c: [dashboard.format_value(df.at[c, v], u, d) for v, (_, u, d) in dashboard.VARIABLES.items()]
             for c in codes},
            index=[label for label, _, _ in dashboard.VARIABLES.values()],
        ).rename(columns=lambda c: df.at[c, "recherche"]),
        width="stretch",
    )
source_note()
