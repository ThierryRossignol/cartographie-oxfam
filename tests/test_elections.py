"""
Tests du connecteur Élections et de l'agrégation par commune.

Aucun accès réseau : on fabrique un petit fichier Parquet local.
"""

import numpy as np
import pandas as pd
import pytest

from src import data_loader, preprocessing
from src.data_loader import ElectionLoader
from src.utils import load_config


def bureau(election, commune, bv, inscrits, abstentions, dep=None, libelle=None):
    votants = inscrits - abstentions
    return {
        "id_election": election,
        "code_departement": dep or commune[:2],
        "libelle_departement": "Dep",
        "code_commune": commune,
        "libelle_commune": libelle or f"Commune {commune}",
        "code_bv": bv,
        "inscrits": inscrits,
        "abstentions": abstentions,
        "votants": votants,
        "exprimes": votants,
    }


@pytest.fixture
def bv():
    return pd.DataFrame(
        [
            # Commune 01001 : 2 bureaux de tailles très différentes
            bureau("2022_pres_t1", "01001", "0001", 100, 50),
            bureau("2022_pres_t1", "01001", "0002", 900, 90),
            bureau("2017_pres_t1", "01001", "0001", 1000, 200, libelle="Ancien nom"),
            # Commune 01002 : absente en 2017 (commune nouvelle)
            bureau("2022_pres_t1", "01002", "0001", 200, 60),
            # Français de l'étranger : exclus
            bureau("2022_pres_t1", "ZZ001", "0001", 500, 400, dep="ZZ"),
            # Bureau sans inscrits
            bureau("2017_pres_t1", "01003", "0001", 0, 0),
        ]
    )


# --- Agrégation -----------------------------------------------------------


def test_aggregate_uses_sums_not_mean_of_rates(bv):
    communes = preprocessing.aggregate_by_commune(bv)
    row = communes.query("id_election == '2022_pres_t1' and code_commune == '01001'").iloc[0]
    assert row["inscrits"] == 1000
    assert row["abstentions"] == 140
    # (50 + 90) / 1000 = 14 %, et non la moyenne des taux (50 % + 10 %) / 2 = 30 %
    assert row["taux_abstention"] == pytest.approx(14.0)


def test_aggregate_excludes_abroad(bv):
    communes = preprocessing.aggregate_by_commune(bv)
    assert "ZZ001" not in communes["code_commune"].values
    with_abroad = preprocessing.aggregate_by_commune(bv, exclude_abroad=False)
    assert "ZZ001" in with_abroad["code_commune"].values


def test_aggregate_zero_inscrits_gives_nan(bv):
    communes = preprocessing.aggregate_by_commune(bv)
    assert np.isnan(communes.query("code_commune == '01003'")["taux_abstention"].iloc[0])


def test_abstention_table(bv):
    communes = preprocessing.aggregate_by_commune(bv)
    table = preprocessing.abstention_by_commune(
        communes, {"A2022": "2022_pres_t1", "A2017": "2017_pres_t1"}
    )
    assert list(table.columns) == ["libelle_commune", "code_departement", "A2022", "A2017"]
    assert table.loc["01001", "A2022"] == pytest.approx(14.0)
    assert table.loc["01001", "A2017"] == pytest.approx(20.0)
    # Libellé repris de l'élection la plus récente
    assert table.loc["01001", "libelle_commune"] == "Commune 01001"
    # Commune absente d'un scrutin → valeur manquante
    assert np.isnan(table.loc["01002", "A2017"])


def test_abstention_table_unknown_election(bv):
    communes = preprocessing.aggregate_by_commune(bv)
    with pytest.raises(ValueError, match="2024_legi_t1"):
        preprocessing.abstention_by_commune(communes, {"A2024": "2024_legi_t1"})


def test_filter_perimeter_column_and_index():
    df = pd.DataFrame({"code_commune": ["01001", "97101", "98801", "2A004"], "x": range(4)})
    kept = preprocessing.filter_perimeter(df, ["97", "98"])
    assert kept["code_commune"].tolist() == ["01001", "2A004"]
    by_index = preprocessing.filter_perimeter(df.set_index("code_commune"), ["97", "98"])
    assert by_index.index.tolist() == ["01001", "2A004"]


def test_elections_config_matches_weights():
    """Chaque scrutin d'abstention correspond à une variable de PC."""
    from src.utils import load_weights

    assert set(load_config("elections")["abstention"]) == set(load_weights()["PC"])


# --- Loader ---------------------------------------------------------------


@pytest.fixture
def loader(tmp_path, bv):
    loader = ElectionLoader(raw_dir=tmp_path)
    bv.to_parquet(loader.path)
    return loader


def test_loader_filters_elections(loader):
    df = loader.load(["2017_pres_t1"])
    assert set(df["id_election"]) == {"2017_pres_t1"}
    assert list(df.columns) == ElectionLoader.COLUMNS


def test_loader_unknown_election(loader):
    with pytest.raises(ValueError, match="1900_pres_t1"):
        loader.load(["2022_pres_t1", "1900_pres_t1"])


def test_loader_available_elections(loader):
    assert loader.available_elections() == ["2017_pres_t1", "2022_pres_t1"]


def test_loader_uses_cache(loader, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("ne doit pas télécharger quand le fichier existe")

    monkeypatch.setattr(data_loader, "download_file", fail)
    loader.load(["2022_pres_t1"])


def test_loader_downloads_when_missing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(data_loader, "download_file", lambda url, dest: calls.append(dest) or dest)
    loader = ElectionLoader(raw_dir=tmp_path)
    assert loader.download() == loader.path
    assert calls == [loader.path]


# --- Extrême droite (IED) -------------------------------------------------


def votes(election, commune, voix_par_nom, dep=None):
    return [
        {"id_election": election, "code_departement": dep or commune[:2], "code_commune": commune,
         "code_bv": "0001", "nom": nom, "voix": v}
        for nom, v in voix_par_nom.items()
    ]


@pytest.fixture
def candidates():
    rows = (
        votes("2022_pres_t1", "01001", {"LE PEN": 30, "MACRON": 50, "ZEMMOUR": 20})
        + votes("2017_pres_t1", "01001", {"LE PEN": 20, "MACRON": 80})
        # Commune où la candidate n'a aucune voix
        + votes("2022_pres_t1", "01002", {"MACRON": 10})
        + votes("2017_pres_t1", "01002", {"MACRON": 10})
        # Commune absente en 2017
        + votes("2022_pres_t1", "01003", {"LE PEN": 5, "MACRON": 5})
        # Bureau sans voix (donnée manquante dans la source)
        + votes("2022_pres_t1", "01004", {"LE PEN": 0, "MACRON": 0})
        # Français de l'étranger : ignorés
        + votes("2022_pres_t1", "ZZ001", {"LE PEN": 1, "MACRON": 99}, dep="ZZ")
    )
    return pd.DataFrame(rows)


def test_vote_share_uses_sum_of_all_candidates(candidates):
    share = preprocessing.vote_share_by_commune(candidates, ["LE PEN"], "2022_pres_t1")
    assert share["01001"] == pytest.approx(30.0)
    assert share["01002"] == 0.0
    assert np.isnan(share["01004"])
    assert "ZZ001" not in share.index


def test_vote_share_sums_several_candidates(candidates):
    share = preprocessing.vote_share_by_commune(candidates, ["LE PEN", "ZEMMOUR"], "2022_pres_t1")
    assert share["01001"] == pytest.approx(50.0)


def test_far_right_by_commune(candidates):
    out = preprocessing.far_right_by_commune(candidates, ["LE PEN"], "2022_pres_t1", "2017_pres_t1")
    assert list(out.columns) == ["RN", "delta_RN"]
    assert out.loc["01001", "delta_RN"] == pytest.approx(10.0)
    assert out.loc["01002", "delta_RN"] == 0.0
    assert out.loc["01003", "RN"] == pytest.approx(50.0)
    assert np.isnan(out.loc["01003", "delta_RN"])


def test_vote_share_unknown_election(candidates):
    with pytest.raises(ValueError, match="1995_pres_t1"):
        preprocessing.vote_share_by_commune(candidates, ["LE PEN"], "1995_pres_t1")


def test_loader_candidates_filters(tmp_path, candidates):
    loader = ElectionLoader(raw_dir=tmp_path)
    candidates.assign(no_panneau=1, prenom="X").to_parquet(loader.candidates_path)
    df = loader.load_candidates(["2017_pres_t1"], names=["LE PEN"])
    assert set(df["id_election"]) == {"2017_pres_t1"} and set(df["nom"]) == {"LE PEN"}
    with pytest.raises(ValueError, match="DUPONT"):
        loader.load_candidates(["2017_pres_t1"], names=["DUPONT"])
