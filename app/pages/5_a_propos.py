"""
Page « À propos » : auteur, contact, citation, licences, crédits et date
des données, limites. Contenu lu dans config/apropos.yaml.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from common import require_results, setup  # noqa: E402

from src import dashboard  # noqa: E402

setup("À propos")
df = require_results()
info = dashboard.about()
author, project, licences = info["auteur"], info["projet"], info["licences"]
dates = dashboard.data_dates()

st.title("À propos")
st.markdown(
    f"**{project['titre']}** est un outil d'aide à la décision qui classe les communes de France "
    "métropolitaine selon leur besoin de mobilisation citoyenne, à partir de données publiques."
)

# --- Auteur ------------------------------------------------------------------
st.header("Auteur et contact")
st.markdown(
    f"""
Conçu et développé par **{author['nom']}**.

- Courriel : [{author['email']}](mailto:{author['email']})
- GitHub : [{author['github'].removeprefix('https://')}]({author['github']})
- Code source et documentation : [{project['depot'].removeprefix('https://')}]({project['depot']})
"""
)

st.subheader("Citer cet outil")
st.markdown("Toute réutilisation de l'outil ou de sa méthodologie doit citer l'auteur :")
st.code(
    f"{author['nom'].split()[-1]}, {author['nom'].split()[0][0]}. ({project['annee']}). "
    f"{project['titre']} — Indice de Besoin de Mobilisation (IBM). {project['depot']}",
    language=None,
    wrap_lines=True,
)

# --- Licences ----------------------------------------------------------------
st.header("Licences")
code, method, data = licences["code"], licences["methodologie"], info["licence_donnees"]
st.markdown(
    f"""
| Élément | Licence | Ce qu'elle impose |
|---|---|---|
| Code source | [{code['nom']}]({code['url']}) | Conserver la mention de l'auteur et de la licence dans toute copie |
| Méthodologie (indicateurs, formules, pondérations, documentation) | [{method['nom']}]({method['url']}) | Citer l'auteur, indiquer les modifications |
| Données sources | [{data['nom']}]({data['url']}) | Citer le producteur et la date de mise à jour (voir ci-dessous) |

Textes complets dans le dépôt : `{code['fichier']}` et `{method['fichier']}`.
"""
)

# --- Données -----------------------------------------------------------------
st.header("Sources et date des données")
st.markdown(
    f"Indicateurs calculés le **{dashboard.format_date(dates.get('calcul'))}**, "
    f"à partir des fichiers suivants, tous publiés sous {data['nom']} :"
)
st.markdown(
    "\n".join(
        f"- **{s['producteur']}** — {s['donnees']}. *{s['millesime']}.* [Source]({s['url']})"
        for s in info["sources"]
    )
)
downloads = dates.get("telechargements") or {}
if downloads:
    with st.expander("Date de téléchargement de chaque fichier"):
        st.table({"Fichier": list(downloads), "Téléchargé le": [dashboard.format_date(d) for d in downloads.values()]})
st.caption(
    "Les données ont été retraitées (agrégation par commune, recalage sur la géographie 2025, "
    "calcul des indicateurs) : les résultats n'engagent pas les producteurs des données."
)

# --- Limites -----------------------------------------------------------------
st.header("Limites à connaître")
st.markdown("\n".join(f"- {line}" for line in dashboard.limits(df)))
st.markdown("📐 [Méthodologie détaillée](/methodologie)")
