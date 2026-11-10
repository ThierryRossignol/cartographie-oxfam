"""
Éléments communs aux pages du dashboard : chemins, chargement des données
(mis en cache), en-tête et petits composants d'affichage.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import dashboard, mapping  # noqa: E402

TITLE = "Observatoire de la mobilisation citoyenne"


def setup(page_title: str) -> None:
    """Rien à configurer : la page est déclarée dans app.py (st.navigation)."""


@st.cache_data(show_spinner="Chargement des indicateurs…")
def results() -> pd.DataFrame:
    return dashboard.load()


@st.cache_resource(show_spinner="Chargement des contours des communes…")
def communes_geo():
    """Contours (simplifiés pour le web) + indicateurs enrichis."""
    df = results()
    geo = mapping.join_indicators(dashboard.load_contours(), df)
    return mapping.lighten_geometries(geo)


def require_results() -> pd.DataFrame:
    """Arrête la page avec un message clair si `make data` n'a pas été lancé."""
    if not dashboard.results_available():
        st.error(
            "Les indicateurs n'ont pas encore été calculés. "
            "Lancer `make data` à la racine du projet, puis recharger la page."
        )
        st.stop()
    return results()


def number(value, decimals: int = 0) -> str:
    return dashboard.format_value(value, "", decimals)


def legend_html(items: list[tuple[str, str]], title: str = "") -> str:
    rows = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;margin:2px 0">'
        f'<span style="width:16px;height:12px;border-radius:2px;background:{color};'
        f'border:1px solid {mapping.LEGEND_EDGE};display:inline-block"></span>'
        f"<span>{label}</span></div>"
        for color, label in items
    )
    head = f'<div style="font-weight:600;margin-bottom:4px">{title}</div>' if title else ""
    return f'<div style="font-size:0.85rem;color:#0b0b0b">{head}{rows}</div>'


# Fond de carte « vide » (aplat couleur du fond), servi par l'application
# elle-même (app/static/, option server.enableStaticServing). Sans lui,
# Streamlit charge un fond CartoDB, service tiers soumis à conditions d'usage.
BLANK_MAP_STYLE = "/app/static/fond_vide.json"
MAP_PROVIDER = None


def fiche_url(code: str) -> str:
    """Adresse de la fiche d'une commune (partageable)."""
    return f"/fiche?commune={code}"


def source_note() -> None:
    """Crédits des données et de l'auteur, en bas de chaque page."""
    author = dashboard.about()["auteur"]["nom"]
    st.caption(
        "Données : Ministère de l'Intérieur (data.gouv.fr), INSEE (Filosofi 2021, recensement 2023), "
        "IGN / Etalab (contours 2025), sous Licence Ouverte 2.0. France métropolitaine. "
        f"Outil et méthodologie : {author} (code MIT, méthodologie CC BY 4.0). "
        "Limites, licences et contact : page [À propos](/a-propos)."
    )


def limits_box(df) -> None:
    """Encadré des limites, bien visible (accueil)."""
    st.warning(
        "**À savoir avant d'utiliser l'outil**\n\n" + "\n".join(f"- {line}" for line in dashboard.limits(df)),
        icon="⚠️",
    )
