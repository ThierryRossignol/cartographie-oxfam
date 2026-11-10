"""
Page d'accueil : présentation, chiffres clés, accès aux autres pages.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402
from common import TITLE, number, require_results, source_note  # noqa: E402

from src import dashboard  # noqa: E402

df = require_results()
stats = dashboard.summary(df, df)

st.title(TITLE)
st.markdown(
    "Où concentrer les campagnes de mobilisation citoyenne d'Oxfam France ? "
    "L'**Indice de Besoin de Mobilisation (IBM)** classe les communes de métropole selon "
    "leur abstention chronique, leur vulnérabilité socio-économique et la part de jeunes. "
    "L'**Indice d'Enjeu Extrême Droite (IED)** complète la lecture, sans entrer dans l'IBM."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Communes couvertes", number(stats["communes"]))
c2.metric("Habitants", number(stats["population"]))
c3.metric("Communes prioritaires", number(stats["prioritaires"]), help="Les 20 % de communes à l'IBM le plus élevé.")
c4.metric(
    "Habitants en commune prioritaire",
    f"{stats['part_population_prioritaire']:.0%}".replace("%", " %"),
    help=f"{number(stats['population_prioritaire'])} habitants vivent dans une commune prioritaire.",
)

st.subheader("Parcourir")
st.page_link("pages/1_carte.py", label="Carte — IBM et IED commune par commune", icon="🗺️")
st.page_link("pages/2_classement.py", label="Classement — trier, filtrer, exporter", icon="📋")
st.page_link("pages/3_fiche_territoire.py", label="Fiche territoire — le détail d'une commune", icon="📍")
st.page_link("pages/4_methodologie.py", label="Méthodologie — formules, sources, limites", icon="📐")

st.subheader("Les plus grandes communes prioritaires")
st.caption("Communes prioritaires de plus de 20 000 habitants, par IBM décroissant.")
top = dashboard.ranking(df[df["prioritaire"] & (df["population"] >= 20_000)]).head(15)
st.dataframe(
    top[["LIBGEO", "departement", "population", "IBM", "IED", "rang_IBM"]],
    hide_index=True,
    width="stretch",
    column_config={
        "LIBGEO": "Commune",
        "departement": "Département",
        "population": st.column_config.NumberColumn("Habitants", format="localized"),
        "IBM": st.column_config.ProgressColumn("IBM", min_value=0, max_value=1, format="%.2f"),
        "IED": st.column_config.ProgressColumn("IED", min_value=0, max_value=1, format="%.2f"),
        "rang_IBM": st.column_config.NumberColumn("Rang IBM", help="1 = IBM le plus élevé de métropole"),
    },
)
source_note()
