"""
Page de méthodologie.

Contenu :
- Présentation de l'IBM.
- Description des variables.
- Formules de calcul.
- Sources des données.
- Limites méthodologiques.
- Documentation du projet.

Les formules et paramètres sont lus dans config/ : la page reste à jour
quand on change une pondération ou un scrutin.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from common import require_results, setup  # noqa: E402

from src import dashboard  # noqa: E402
from src.utils import load_config, load_weights  # noqa: E402

setup("Méthodologie")
df = require_results()
w = load_weights()
elections = load_config("elections")
norm = load_config("normalisation")


def formula(name: str, block: dict) -> str:
    terms = " + ".join(f"{v:.2f}".replace(".", ",") + f" × {k}" for k, v in block.items())
    return f"{name} = {terms}"


st.title("Méthodologie")

st.header("L'Indice de Besoin de Mobilisation (IBM)")
st.markdown(
    "L'IBM repère les communes où une campagne de mobilisation citoyenne a le plus de raisons d'agir : "
    "une participation électorale durablement faible, une population fragile, et un public jeune à toucher."
)
st.code(
    "\n".join([
        formula("IBM", w["IBM"]),
        "",
        formula("PC", w["PC"]) + "      (abstention moyenne pondérée)",
        "D  = PC mise à l'échelle 0–1",
        formula("V", w["V"]) + "   (R inversé : faible revenu = besoin fort)",
        formula("J", w["J"]),
    ]),
    language=None,
)

st.header("L'Indice d'Enjeu Extrême Droite (IED)")
ied = elections["ied"]
st.markdown(
    "Indicateur complémentaire, **qui n'entre pas dans l'IBM**. Il sert à adapter le discours "
    "selon le contexte politique local."
)
st.code(formula("IED", w["IED"]), language=None)
st.markdown(
    f"- **RN** : score cumulé de {', '.join(n.title() for n in ied['candidats'])}, "
    f"{dashboard.election_label(ied['scrutin'])}, en % des exprimés.\n"
    f"- **delta_RN** : RN moins le score de "
    f"{', '.join(n.title() for n in (ied.get('candidats_reference') or ied['candidats']))}, "
    f"{dashboard.election_label(ied['scrutin_reference'])}, en points."
)

st.header("Variables et sources")
abst = elections["abstention"]
st.table(
    {
        "Variable": ["A2022 / A2017 / A2024", "P", "R", "C", "SD", "Y", "RN, delta_RN"],
        "Définition": [
            "Abstentions / inscrits : " + " ; ".join(f"{k} = {dashboard.election_label(v)}" for k, v in abst.items()),
            "Taux de pauvreté au seuil de 60 % du niveau de vie médian",
            "Niveau de vie médian (€)",
            "Chômeurs / actifs de 15 à 64 ans (au sens du recensement)",
            "Part des 15 ans ou plus non scolarisés sans diplôme (ou CEP seul)",
            "Part des 19-25 ans dans la population",
            "Voir IED ci-dessus",
        ],
        "Source": [
            "Ministère de l'Intérieur, via data.gouv.fr",
            "INSEE, Filosofi 2023",
            "INSEE, Filosofi 2023",
            "INSEE, recensement 2023",
            "INSEE, recensement 2023",
            "INSEE, recensement 2023",
            "Ministère de l'Intérieur, via data.gouv.fr",
        ],
    }
)

st.header("Choix de calcul")
st.markdown(
    f"""
- **Géographie** : communes au 1er janvier 2025. Les résultats électoraux anciens sont recalés grâce à la table
  de passage de l'INSEE (communes fusionnées regroupées, communes scindées héritant du taux de l'ancienne).
  Paris, Lyon et Marseille comptent chacune pour une commune.
- **Périmètre** : France métropolitaine ({dashboard.format_value(len(df), '', 0)} communes). Les outre-mer sont
  exclus : leur abstention (45 à 85 % en médiane, contre 20 % en métropole) écraserait l'échelle.
- **Mise à l'échelle** : chaque variable est écrêtée entre ses {norm['quantile_bas']:.0%} et
  {norm['quantile_haut']:.0%} centiles, puis ramenée entre 0 et 1. Les scores sont **relatifs** :
  1 = la commune au besoin le plus fort de métropole, pas un seuil absolu.
- **Secret statistique** : l'INSEE ne publie le taux de pauvreté que pour ~5 200 communes et le niveau de vie
  médian pour ~30 800. Pour les autres, on prend la valeur de l'intercommunalité (indiqué sur la fiche).
- **Communes prioritaires** : les 20 % de communes à l'IBM le plus élevé.
- **Classes des cartes** : 5 classes d'effectifs égaux (quintiles), calculées sur toute la métropole.
""".replace("%", " %").replace("  %", " %")
)

st.header("Limites")
st.markdown("\n".join(f"- {line}" for line in dashboard.limits(df)))
st.markdown(
    """
- **Repli intercommunal** : il gomme les écarts de pauvreté entre communes voisines.
- **Données manquantes** : 10 communes sans IBM (villages de la Meuse inhabités, îles sans
  intercommunalité, très petites communes) et 25 sans IED (dont une vingtaine dont les voix par
  candidat manquent dans la source).
- **Un indice n'est pas un diagnostic** : l'IBM aide à choisir où regarder ; la connaissance du terrain
  reste indispensable.
"""
)
st.caption("Code source et documentation complète : README du projet. Méthodologie sous licence CC BY 4.0 "
           "— voir la page À propos.")
