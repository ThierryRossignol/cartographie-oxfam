"""
Tests du dashboard : logique (src/dashboard.py) sur données fabriquées, puis
exécution de chaque page Streamlit (AppTest) sur les vraies données si
`make data` a été lancé.
"""

import numpy as np
import pandas as pd
import pytest

from src import dashboard


@pytest.fixture
def results():
    n = 10
    return pd.DataFrame(
        {
            "LIBGEO": [f"Commune {i}" for i in range(n)],
            "DEP": ["01"] * 5 + ["02"] * 5,
            "libelle_departement": ["Ain"] * 5 + ["Aisne"] * 4 + [None],
            "population": [100, 200, 300, 400, 500, 1000, 2000, 3000, 4000, 5000],
            "IBM": np.linspace(0.1, 1.0, n),
            "IED": [0.9, 0.1, 0.5, 0.3, 0.7, 0.2, 0.8, 0.4, np.nan, 0.6],
            "D": 0.5, "V": 0.5, "J": 0.5,
            "A2022": np.linspace(10, 30, n), "A2017": 15.0, "A2024": 25.0,
            "P": 14.0, "C": 8.0, "R": np.linspace(30000, 15000, n), "SD": 18.0, "Y": 5.0,
            "RN": 30.0, "delta_RN": 2.0,
        },
        index=pd.Index([f"0{1 + i // 5}{i:03d}" for i in range(n)], name="code_commune"),
    )


@pytest.fixture
def df(results):
    return dashboard.enrich(results)


def test_enrich_ranks_classes_and_names(df):
    assert df.loc["02009", "rang_IBM"] == 1           # IBM le plus élevé
    assert df["classe_IBM"].tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert pd.isna(df.loc["02008", "classe_IED"])     # IED manquant
    assert df.loc["02009", "departement"] == "Aisne"  # nom complété
    assert df["prioritaire"].sum() == 2               # 20 % de 10
    assert df.loc["01000", "recherche"] == "Commune 0 (01)"


def test_department_options(df):
    assert dashboard.department_options(df) == {"01": "01 — Ain", "02": "02 — Aisne"}


def test_filters_combine(df):
    assert len(dashboard.Filters(departments=["01"]).apply(df)) == 5
    assert len(dashboard.Filters(min_population=2000).apply(df)) == 4
    assert len(dashboard.Filters(only_priority=True).apply(df)) == 2
    kept = dashboard.Filters(departments=["02"], ied_classes=[5]).apply(df)
    assert kept.index.tolist() == ["02006"]          # IED 0,8 → classe 5
    assert len(dashboard.Filters().apply(df)) == 10


def test_summary(df):
    stats = dashboard.summary(df[df["DEP"] == "02"], df)
    assert stats["communes"] == 5
    assert stats["population"] == 15000
    assert stats["prioritaires"] == 2
    assert stats["part_population_prioritaire"] == pytest.approx(9000 / 15000)


def test_ranking_puts_missing_last(df):
    ranked = dashboard.ranking(df, "IED")
    assert ranked.index[0] == "01000" and ranked.index[-1] == "02008"
    assert len(dashboard.ranking(df, "IBM", limit=3)) == 3


def test_commune_profile(df):
    profile = dashboard.commune_profile(df, "02009")
    assert profile.loc["A2022", "commune"] == 30.0
    assert profile.loc["A2022", "centile"] == 90.0    # 9 communes sur 10 en dessous
    assert profile.loc["R", "besoin plus fort si"] == "faible"
    assert profile.loc["A2022", "département (médiane)"] == pytest.approx(df[df.DEP == "02"]["A2022"].median())


def test_format_value():
    assert dashboard.format_value(12.345, "%", 1) == "12,3 %"
    assert dashboard.format_value(21450, "€", 0) == "21 450 €"
    assert dashboard.format_value(-2.06, "pts", 1) == "−2,1 pts"
    assert dashboard.format_value(np.nan, "%", 1) == "—"


def test_election_label():
    assert dashboard.election_label("2022_pres_t1") == "Présidentielle 2022, 1er tour"
    assert dashboard.election_label("2024_legi_t2") == "Législatives 2024, 2e tour"


def test_neighbours(df):
    near = dashboard.neighbours(df, "01002", n=2)
    assert "01002" in near.index and len(near) == 3
    assert set(near["DEP"]) == {"01"}


def test_legend_and_colors(df):
    items = dashboard.legend("IBM", df)
    assert len(items) == 6 and items[0][1].endswith("20 % les plus élevés")
    assert dashboard.hex_to_rgb("#0d366b") == [13, 54, 107]


def test_map_features(df):
    import geopandas as gpd
    from shapely.geometry import box

    geo = gpd.GeoDataFrame(
        df.reset_index().assign(geometry=[box(i, 0, i + 1, 1) for i in range(len(df))]), crs="EPSG:4326"
    )
    data = dashboard.map_features(geo, "IED", highlight={"02009"})
    props = [f["properties"] for f in data["features"]]
    # IED 0,6 : 4e quintile des 9 valeurs présentes (bornes 0,42 – 0,58 – 0,74)
    assert props[-1]["fill"] == dashboard.hex_to_rgb(dashboard.mapping.PALETTES["IED"][3])
    assert props[0]["fill"] == dashboard.hex_to_rgb(dashboard.mapping.OTHER_COLOR)        # hors sélection
    assert props[0]["IBM"] == "0,10"


# --- Pages Streamlit (sur les vraies données) ---------------------------------

needs_data = pytest.mark.skipif(not dashboard.results_available(), reason="lancer `make data` d'abord")
PAGES = "app/pages"


def run_page(path, **query):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(path, default_timeout=300)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@needs_data
def test_page_accueil():
    at = run_page("app/accueil.py")
    assert at.title[0].value == "Observatoire de la mobilisation citoyenne"
    assert len(at.metric) == 4


@needs_data
def test_page_classement():
    at = run_page(f"{PAGES}/2_classement.py")
    assert at.title[0].value == "Classement des communes"
    at.toggle[0].set_value(True).run()
    assert not at.exception


@needs_data
def test_page_fiche_from_url():
    at = run_page(f"{PAGES}/3_fiche_territoire.py", commune="62498")
    assert at.title[0].value == "Lens"
    assert at.metric[0].label == "IBM"


@needs_data
def test_page_fiche_without_commune():
    at = run_page(f"{PAGES}/3_fiche_territoire.py")
    assert at.info[0].value.startswith("Choisir une commune")


@needs_data
def test_page_methodologie():
    at = run_page(f"{PAGES}/4_methodologie.py")
    assert any("IBM = 0,45 × D" in c.value for c in at.code)


@needs_data
def test_page_carte():
    pytest.importorskip("pydeck")
    at = run_page(f"{PAGES}/1_carte.py")
    at.radio[0].set_value("IED").run()
    assert not at.exception
