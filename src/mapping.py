"""
Module de cartographie.

Responsabilités :
- Générer les cartes choroplèthes.
- Associer les indicateurs aux limites administratives.
- Définir les palettes de couleurs.
- Gérer les couches cartographiques.
- Préparer les données destinées au dashboard.

Ce module est responsable uniquement de la représentation cartographique des
résultats. Les fichiers sont écrits par src/export.py.

Choix de représentation :
- Les indicateurs sont découpés en 5 classes d'effectifs égaux (quintiles) :
  « 20 % des communes les plus prioritaires », lecture directe pour
  préparer une campagne.
- Une palette par indicateur, du clair (faible) au foncé (fort), qui
  varie à la fois en clarté et en teinte pour que les classes voisines
  restent distinctes même sur de très petites communes :
  jaune → vert → bleu pour l'IBM, jaune → orange → rouge pour l'IED.
- Gris neutre pour les communes sans donnée, toujours légendé.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Palettes
# ----------------------------------------------------------------------------

# Rampes à 5 classes (clair → foncé), clarté et teinte croissantes.
# Vérifiées : écart de couleur entre classes voisines >= 15 (OKLab ×100)
# en vision normale et >= 8 en vision daltonienne simulée — l'ancienne
# rampe bleue à teinte unique plafonnait à 9,5 et se lisait mal.
# Les classes les plus claires sont peu contrastées avec le fond : les
# pastilles de légende ont donc un fin contour (LEGEND_EDGE).
PALETTES = {
    "IBM": ["#f0f388", "#7cd591", "#00a8a9", "#006bab", "#23367b"],  # jaune → vert → bleu
    "IED": ["#fff198", "#ffac34", "#e95c12", "#b32322", "#6e0b22"],  # jaune → orange → rouge
}
LEGEND_EDGE = "#c3c2b7"
MISSING_COLOR = "#d6d5d0"   # sans donnée
OTHER_COLOR = "#ebeae6"     # communes hors sélection
BORDER_COLOR = "#fcfcfb"    # limites de départements (couleur du fond)
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"

LABELS = {
    "IBM": "Indice de Besoin de Mobilisation",
    "IED": "Indice d'Enjeu Extrême Droite",
}

LAMBERT_93 = "EPSG:2154"

# Part des communes considérées comme prioritaires (IBM le plus élevé).
PRIORITY_SHARE = 0.2


def is_priority(ibm: pd.Series, top_share: float = PRIORITY_SHARE) -> pd.Series:
    """Vrai pour les `top_share` communes à l'IBM le plus élevé."""
    return ibm >= ibm.quantile(1 - top_share)


# ----------------------------------------------------------------------------
# Classes
# ----------------------------------------------------------------------------


@dataclass
class Classes:
    """Découpage d'un indicateur en classes."""

    codes: pd.Series        # 0 … k-1 par commune, -1 si valeur manquante
    edges: list[float]      # k + 1 bornes, de la valeur min à la valeur max

    @property
    def k(self) -> int:
        return len(self.edges) - 1

    def labels(self, decimals: int = 2) -> list[str]:
        """Libellés « 0,35 – 0,42 » de chaque classe (virgule décimale)."""
        fmt = lambda x: f"{x:.{decimals}f}".replace(".", ",")  # noqa: E731
        return [f"{fmt(lo)} – {fmt(hi)}" for lo, hi in zip(self.edges[:-1], self.edges[1:])]


def quantile_classes(values: pd.Series, k: int = 5) -> Classes:
    """
    Découpe `values` en `k` classes d'effectifs égaux (quantiles).

    Les communes sans valeur reçoivent le code -1. Les bornes sont
    calculées sur les seules valeurs présentes.
    """
    present = values.dropna()
    if present.empty:
        raise ValueError("Aucune valeur à classer.")
    edges = np.quantile(present, np.linspace(0, 1, k + 1))
    # Classe = nombre de bornes intérieures dépassées (bornes incluses à gauche)
    codes = np.searchsorted(edges[1:-1], values.to_numpy(), side="right")
    codes = pd.Series(codes, index=values.index).where(values.notna(), -1).astype(int)
    return Classes(codes=codes, edges=[float(e) for e in edges])


def class_colors(classes: Classes, palette: list[str]) -> pd.Series:
    """Couleur de chaque commune selon sa classe (gris si manquante)."""
    if classes.k != len(palette):
        raise ValueError(f"{classes.k} classes pour {len(palette)} couleurs")
    lookup = dict(enumerate(palette)) | {-1: MISSING_COLOR}
    return classes.codes.map(lookup)


# ----------------------------------------------------------------------------
# Couches
# ----------------------------------------------------------------------------


def join_indicators(contours, table: pd.DataFrame, code_column: str = "code"):
    """
    Associe la table des indicateurs (indexée par code commune) aux contours.

    Ne garde que les communes présentes dans la table (le périmètre est
    décidé en amont, voir config/perimetre.yaml). Une commune de la table
    sans contour lève une erreur : c'est le signe d'un décalage de
    géographie (millésime du COG).
    """
    missing = sorted(set(table.index) - set(contours[code_column]))
    if missing:
        raise ValueError(f"{len(missing)} commune(s) sans contour, ex. {missing[:5]}")
    geo = contours[[code_column, "geometry"]].rename(columns={code_column: "code_commune"})
    return geo.merge(table, left_on="code_commune", right_index=True, how="inner")


def department_outlines(communes, department_column: str = "DEP"):
    """
    Limites des départements, reconstruites en fusionnant les communes.

    Les contours simplifiés contiennent quelques polygones invalides
    (auto-intersections) : ils sont réparés avant la fusion.
    """
    data = communes[[department_column, "geometry"]].copy()
    data["geometry"] = data.geometry.make_valid()
    return data.dissolve(by=department_column).reset_index()


def priority_categories(ibm: pd.Series, ied: pd.Series, top_share: float = PRIORITY_SHARE) -> pd.Series:
    """
    Croisement IBM × IED pour préparer les campagnes.

    Communes prioritaires = les `top_share` (20 %) d'IBM le plus élevé.
    Parmi elles, l'IED (en tiers calculés sur toute la métropole) indique
    le contexte : 0 = IED faible, 1 = moyen, 2 = élevé. Les autres
    communes valent -1 ; une commune prioritaire sans IED vaut -2.
    """
    tiers = quantile_classes(ied, k=3).codes
    out = pd.Series(-1, index=ibm.index)
    priority = is_priority(ibm, top_share)
    out[priority] = tiers[priority].where(tiers[priority] >= 0, -2)
    return out.astype(int)


# ----------------------------------------------------------------------------
# Cartes fixes (PNG)
# ----------------------------------------------------------------------------


def _base_figure(title: str, subtitle: str):
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(9, 10.2), dpi=100)
    fig.patch.set_facecolor(SURFACE)
    # La carte occupe le bas ; titre, sous-titre et légende sont au-dessus,
    # pour que la légende ne recouvre jamais le territoire.
    ax = fig.add_axes([0.02, 0.05, 0.96, 0.78])
    ax.set_facecolor(SURFACE)
    ax.set_axis_off()
    fig.text(0.04, 0.975, title, fontsize=17, fontweight="bold", color=TEXT_PRIMARY, va="top")
    fig.text(0.04, 0.938, subtitle, fontsize=11, color=TEXT_SECONDARY, va="top")
    return fig, ax


def _row_major(handles: list, ncol: int) -> list:
    """
    Matplotlib remplit la légende colonne par colonne ; on réordonne pour
    qu'elle se lise ligne par ligne (du plus élevé au plus faible).
    """
    nrow = -(-len(handles) // ncol)
    grid = [handles[r * ncol:(r + 1) * ncol] for r in range(nrow)]
    return [row[c] for c in range(ncol) for row in grid if c < len(row)]


def _finish(fig, ax, handles, legend_title: str, source: str, ncol: int = 3):
    ax.set_aspect("equal")
    fig.legend(
        handles=_row_major(handles, ncol),
        title=legend_title,
        loc="upper left",
        bbox_to_anchor=(0.03, 0.91),
        ncol=ncol,
        frameon=False,
        fontsize=10,
        title_fontsize=10,
        labelcolor=TEXT_PRIMARY,
        alignment="left",
        columnspacing=1.6,
        handlelength=1.6,
    )
    fig.text(0.04, 0.02, source, fontsize=8, color=TEXT_SECONDARY)
    return fig


def _thousands(n: int) -> str:
    """12345 → « 12 345 » (espace insécable fine, à la française)."""
    return f"{n:,}".replace(",", "\u202f")


def _swatch(color: str, label: str):
    from matplotlib.patches import Patch

    return Patch(facecolor=color, edgecolor=LEGEND_EDGE, linewidth=0.6, label=label)


SOURCE_NOTE = (
    "Sources : Ministère de l'Intérieur (data.gouv.fr), INSEE (Filosofi 2021, recensement 2023), "
    "IGN / Etalab (contours 2025). France métropolitaine."
)


def choropleth(communes, column: str, outlines=None, k: int = 5):
    """
    Carte d'un indicateur en quintiles (figure matplotlib, Lambert-93).

    `communes` : GeoDataFrame issu de `join_indicators`.
    """
    palette = PALETTES[column]
    classes = quantile_classes(communes[column], k=k)
    data = communes.to_crs(LAMBERT_93).assign(_color=class_colors(classes, palette).to_numpy())

    n_missing = int((classes.codes < 0).sum())
    fig, ax = _base_figure(
        f"{LABELS[column]} ({column})",
        f"{_thousands(len(data))} communes en 5 classes d'effectifs égaux — plus foncé = plus élevé",
    )
    data.plot(ax=ax, color=data["_color"], linewidth=0)
    if outlines is not None:
        outlines.to_crs(LAMBERT_93).boundary.plot(ax=ax, color=BORDER_COLOR, linewidth=0.5)

    names = ["20 % les plus faibles", "", "", "", "20 % les plus élevés"] if k == 5 else [""] * k
    handles = [
        _swatch(color, f"{label}   {name}".rstrip())
        for color, label, name in zip(palette[::-1], classes.labels()[::-1], names[::-1])
    ]
    if n_missing:
        handles.append(_swatch(MISSING_COLOR, f"Donnée manquante ({n_missing})"))
    return _finish(fig, ax, handles, column, SOURCE_NOTE)


def priority_map(communes, outlines=None, top_share: float = PRIORITY_SHARE):
    """
    Carte des communes prioritaires (IBM dans les 20 % les plus élevés),
    colorées selon leur IED (tiers). Les autres communes sont en gris clair.
    """
    cats = priority_categories(communes["IBM"], communes["IED"], top_share)
    # Tiers d'IED : on saute le jaune le plus clair, trop proche du gris
    # des communes non prioritaires.
    ied_colors = [PALETTES["IED"][1], PALETTES["IED"][2], PALETTES["IED"][4]]
    lookup = {-1: OTHER_COLOR, -2: MISSING_COLOR, 0: ied_colors[0], 1: ied_colors[1], 2: ied_colors[2]}
    data = communes.to_crs(LAMBERT_93).assign(_color=cats.map(lookup).to_numpy())

    n_priority = int((cats != -1).sum())
    fig, ax = _base_figure(
        "Communes prioritaires et enjeu extrême droite",
        f"Les {_thousands(n_priority)} communes à l'IBM le plus élevé (20 %), selon leur IED",
    )
    data.plot(ax=ax, color=data["_color"], linewidth=0)
    if outlines is not None:
        outlines.to_crs(LAMBERT_93).boundary.plot(ax=ax, color=BORDER_COLOR, linewidth=0.5)

    counts = cats.value_counts()
    handles = [
        _swatch(ied_colors[2], f"IED élevé — {_thousands(counts.get(2, 0))}"),
        _swatch(ied_colors[1], f"IED moyen — {_thousands(counts.get(1, 0))}"),
        _swatch(ied_colors[0], f"IED faible — {_thousands(counts.get(0, 0))}"),
        _swatch(OTHER_COLOR, "Communes non prioritaires"),
    ]
    if counts.get(-2, 0):
        handles.append(_swatch(MISSING_COLOR, f"IED manquant — {counts.get(-2)}"))
    return _finish(fig, ax, handles, "Communes prioritaires, par tiers d'IED (calculés sur toute la métropole)", SOURCE_NOTE)


# ----------------------------------------------------------------------------
# Carte interactive (HTML)
# ----------------------------------------------------------------------------

TOOLTIP_FIELDS = {
    "LIBGEO": "Commune",
    "DEP": "Département",
    "IBM": "IBM",
    "IBM_classe": "Classe IBM",
    "IED": "IED",
    "IED_classe": "Classe IED",
    "D": "Déficit démocratique (D)",
    "V": "Vulnérabilité (V)",
    "J": "Jeunes (J)",
    "A2022": "Abstention 2022 (%)",
    "RN": "Score RN 2022 (%)",
}

_TOGGLE_JS = """
<div id="ibm-panel" style="position:absolute;top:12px;right:12px;z-index:1000;background:#fcfcfb;
  padding:10px 12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25);font:13px system-ui,sans-serif;color:#0b0b0b">
  <div style="font-weight:600;margin-bottom:6px">Indicateur</div>
  <label><input type="radio" name="ind" value="IBM" checked> IBM — besoin de mobilisation</label><br>
  <label><input type="radio" name="ind" value="IED"> IED — enjeu extrême droite</label>
  <div style="margin-top:8px"><label><input type="checkbox" id="only-priority">
    Seulement les 20 % d'IBM le plus élevé</label></div>
  <div id="ibm-legend" style="margin-top:8px"></div>
</div>
<script>
document.addEventListener("DOMContentLoaded", function () {
  var layer = {layer};
  var legends = {legends};
  var missing = "{missing}", other = "{other}";
  function style(f) {
    var ind = document.querySelector('input[name=ind]:checked').value;
    var only = document.getElementById('only-priority').checked;
    var p = f.properties;
    var color = p["c_" + ind] || missing;
    if (only && !p.prioritaire) color = other;
    // Liseré de la couleur de la commune : il bouche les jointures des
    // contours simplifiés sans délaver les couleurs (un liseré blanc le ferait).
    return {fillColor: color, fillOpacity: 1, stroke: true, color: color, weight: 1.2, opacity: 1};
  }
  function legend() {
    var ind = document.querySelector('input[name=ind]:checked').value;
    var rows = legends[ind].map(function (r) {
      return '<div><span style="display:inline-block;width:14px;height:10px;margin-right:6px;border:1px solid {edge};background:'
        + r[0] + '"></span>' + r[1] + '</div>';
    });
    document.getElementById('ibm-legend').innerHTML = rows.join('');
  }
  // resetStyle (fin du survol) réutilise options.style : on le remplace aussi.
  function update() { layer.options.style = style; layer.setStyle(style); legend(); }
  document.querySelectorAll('#ibm-panel input').forEach(function (i) { i.addEventListener('change', update); });
  update();
});
</script>
"""


def interactive_map(communes, precision: float = 0.001):
    """
    Carte interactive (folium) : bascule IBM / IED, filtre « communes
    prioritaires », info-bulle par commune.

    Les géométries sont arrondies à `precision` degré (~100 m) pour alléger
    le fichier HTML ; c'est cohérent avec les contours, déjà simplifiés
    à 1 000 m. Pas de fond de carte : les communes couvrent tout le
    territoire en aplat, et les fonds gratuits exigent désormais une clé.
    """
    import folium

    data = lighten_geometries(communes, precision)

    legends = {}
    for col in ("IBM", "IED"):
        classes = quantile_classes(data[col])
        data[f"c_{col}"] = class_colors(classes, PALETTES[col]).replace(MISSING_COLOR, None)
        data[f"{col}_classe"] = (classes.codes + 1).map(
            lambda c: "—" if c == 0 else f"{c} / 5"
        )
        legends[col] = [[c, lab] for c, lab in zip(PALETTES[col][::-1], classes.labels()[::-1])]
        legends[col].append([MISSING_COLOR, "Donnée manquante"])
    data["prioritaire"] = is_priority(data["IBM"])

    fields = [f for f in TOOLTIP_FIELDS if f in data.columns]
    keep = ["code_commune", *fields, "c_IBM", "c_IED", "prioritaire", "geometry"]
    data = data[keep].copy()
    for col in ("IBM", "IED", "D", "V", "J"):
        if col in data:
            data[col] = data[col].round(2)
    for col in ("A2022", "RN"):
        if col in data:
            data[col] = data[col].round(1)

    fmap = folium.Map(location=[46.6, 2.4], zoom_start=6, tiles=None, prefer_canvas=True)
    fmap.get_root().header.add_child(
        folium.Element(f"<style>.leaflet-container {{ background: {SURFACE} !important; }}</style>")
    )
    layer = folium.GeoJson(
        data,
        name="Communes",
        style_function=lambda f: {"fillOpacity": 1, "stroke": False},
        highlight_function=lambda f: {"stroke": True, "weight": 2, "color": TEXT_PRIMARY},
        tooltip=folium.GeoJsonTooltip(
            fields=fields, aliases=[TOOLTIP_FIELDS[f] for f in fields], localize=True, sticky=True
        ),
        smooth_factor=1.5,
    ).add_to(fmap)

    import json

    js = (
        _TOGGLE_JS.replace("{layer}", layer.get_name())
        .replace("{legends}", json.dumps(legends, ensure_ascii=False))
        .replace("{missing}", MISSING_COLOR)
        .replace("{other}", OTHER_COLOR)
        .replace("{edge}", LEGEND_EDGE)
    )
    fmap.get_root().html.add_child(folium.Element(js))
    return fmap


def lighten_geometries(communes, precision: float = 0.001):
    """
    Arrondit les coordonnées à `precision` degré (~100 m) pour l'affichage
    web. Arrondi point par point : la topologie n'est pas recalculée, ce qui
    évite les erreurs sur les contours déjà simplifiés.
    """
    import shapely

    data = communes.copy()
    data["geometry"] = shapely.set_precision(data.geometry.values, precision, mode="pointwise")
    return data[~data.geometry.is_empty]


def dashboard_layer(communes):
    """Couche GeoJSON légère pour le dashboard : géométrie + indicateurs."""
    cols = ["code_commune", "LIBGEO", "DEP", "EPCI", "PC", "D", "V", "J", "IBM", "RN", "delta_RN", "IED"]
    return communes[[c for c in cols if c in communes.columns] + ["geometry"]]
