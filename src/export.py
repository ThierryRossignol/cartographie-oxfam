"""
Module d'export.

Responsabilités :
- Exporter les résultats au format CSV.
- Exporter les résultats au format Excel.
- Exporter les couches cartographiques (GeoJSON).
- Générer les fichiers nécessaires aux rapports ou au dashboard.

Toutes les opérations d'écriture de fichiers sont centralisées dans ce module
(hors copies brutes de data/raw/, gérées par data_loader).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils import ROOT_DIR

INTERIM_DIR = ROOT_DIR / "data" / "interim"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUTS_DIR = ROOT_DIR / "data" / "outputs"


def save_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """
    Écrit `df` en CSV UTF-8 (index inclus) et renvoie le chemin.

    Relire avec `read_csv(path, dtype={"code_commune": str})` pour garder les
    zéros initiaux des codes INSEE (ex. 01001).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, encoding="utf-8")
    return path


def _prepare(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_figure(fig, path: str | Path, dpi: int = 200) -> Path:
    """Enregistre une figure matplotlib (PNG) et la ferme."""
    import matplotlib.pyplot as plt

    path = _prepare(path)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def save_html_map(fmap, path: str | Path) -> Path:
    """Enregistre une carte folium en page HTML autonome."""
    path = _prepare(path)
    fmap.save(str(path))
    return path


def save_geojson(gdf, path: str | Path) -> Path:
    """Enregistre un GeoDataFrame en GeoJSON (WGS84)."""
    path = _prepare(path)
    gdf.to_crs("EPSG:4326").to_file(path, driver="GeoJSON")
    return path
