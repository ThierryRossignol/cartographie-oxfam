"""
Tests du module de cartographie (sans réseau, petites géométries fabriquées).
"""

import matplotlib

matplotlib.use("Agg")

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from src import mapping


@pytest.fixture
def communes():
    """10 communes carrées sur une ligne, dans 2 départements."""
    codes = [f"01{i:03d}" for i in range(5)] + [f"02{i:03d}" for i in range(5)]
    contours = gpd.GeoDataFrame(
        {"code": codes, "geometry": [box(i * 0.1, 45, i * 0.1 + 0.1, 45.1) for i in range(10)]},
        crs="EPSG:4326",
    )
    table = pd.DataFrame(
        {
            "LIBGEO": [f"C{i}" for i in range(10)],
            "DEP": ["01"] * 5 + ["02"] * 5,
            "IBM": np.linspace(0, 1, 10),
            "IED": [0.9, 0.1, 0.5, 0.3, 0.7, 0.2, 0.8, 0.4, np.nan, 0.6],
            "D": 0.5, "V": 0.5, "J": 0.5, "A2022": 20.0, "RN": 30.0,
        },
        index=pd.Index(codes, name="code_commune"),
    )
    return mapping.join_indicators(contours, table)


def test_quantile_classes_equal_counts_and_missing():
    values = pd.Series([0.0, 1, 2, 3, 4, 5, 6, 7, 8, 9, np.nan])
    classes = mapping.quantile_classes(values, k=5)
    assert classes.codes.iloc[:10].value_counts().tolist() == [2] * 5
    assert classes.codes.iloc[10] == -1
    assert classes.edges[0] == 0 and classes.edges[-1] == 9
    assert classes.labels()[0] == "0,00 – 1,80"


def test_class_colors_uses_palette_and_missing():
    classes = mapping.quantile_classes(pd.Series([1.0, 2, 3, 4, 5, np.nan]), k=5)
    colors = mapping.class_colors(classes, mapping.PALETTES["IBM"])
    assert colors.iloc[0] == mapping.PALETTES["IBM"][0]
    assert colors.iloc[4] == mapping.PALETTES["IBM"][4]
    assert colors.iloc[5] == mapping.MISSING_COLOR


def test_palettes_are_five_steps():
    for palette in mapping.PALETTES.values():
        assert len(palette) == 5 and len(set(palette)) == 5


def test_join_indicators_rejects_unknown_commune(communes):
    contours = gpd.GeoDataFrame({"code": ["01000"], "geometry": [box(0, 0, 1, 1)]}, crs="EPSG:4326")
    table = pd.DataFrame({"IBM": [0.5, 0.6]}, index=["01000", "99999"])
    with pytest.raises(ValueError, match="99999"):
        mapping.join_indicators(contours, table)


def test_department_outlines(communes):
    outlines = mapping.department_outlines(communes)
    assert outlines["DEP"].tolist() == ["01", "02"]
    assert [tuple(round(v, 6) for v in g.bounds) for g in outlines.geometry] == [(0, 45, 0.5, 45.1), (0.5, 45, 1.0, 45.1)]


def test_priority_categories(communes):
    cats = mapping.priority_categories(communes["IBM"], communes["IED"], top_share=0.2)
    # Les 2 communes à l'IBM le plus élevé sont prioritaires
    assert (cats.iloc[:8] == -1).all()
    assert cats.iloc[8] == -2          # prioritaire, IED manquant
    assert cats.iloc[9] in (0, 1, 2)


def test_row_major_legend_order():
    assert mapping._row_major(list("abcde"), ncol=3) == ["a", "d", "b", "e", "c"]


def test_static_maps_render(communes):
    outlines = mapping.department_outlines(communes)
    for fig in (mapping.choropleth(communes, "IBM", outlines), mapping.priority_map(communes, outlines)):
        assert fig.axes
        matplotlib.pyplot.close(fig)


def test_interactive_map_contains_toggle(communes):
    html = mapping.interactive_map(communes).get_root().render()
    assert "ibm-panel" in html and "only-priority" in html
    assert mapping.PALETTES["IED"][0] in html


def test_dashboard_layer_columns(communes):
    layer = mapping.dashboard_layer(communes)
    assert "geometry" in layer.columns and "IBM" in layer.columns and "D" in layer.columns
