"""
Tests du prétraitement INSEE, du recalage géographique et du téléchargement.

Aucun accès réseau : données fabriquées au format « long » de l'INSEE.
"""

import zipfile

import numpy as np
import pandas as pd
import pytest
import requests

from src import data_loader, indicators, preprocessing
from src.utils import min_max_normalize


def long(rows, dim):
    """Fabrique un tableau INSEE long : (GEO, modalité, valeur)."""
    return pd.DataFrame(rows, columns=["GEO", dim, "OBS_VALUE"])


# --- Recalage des codes communes ------------------------------------------


@pytest.fixture
def passage():
    return pd.DataFrame(
        {
            # 01001 inchangée ; 01002 + 01003 fusionnées dans 01002 ;
            # 01004 scindée en 01004 et 01099
            "CODGEO_INI": ["01001", "01002", "01003", "01004", "01004"],
            "CODGEO_COG": ["01001", "01002", "01002", "01004", "01099"],
        }
    )


def test_harmonize_merges_and_splits(passage):
    bv = pd.DataFrame(
        {
            "id_election": ["2017_pres_t1"] * 5,
            "code_departement": ["01"] * 4 + ["ZZ"],
            "code_commune": ["01001", "01002", "01003", "01004", "ZZ001"],
            "inscrits": [100, 100, 300, 200, 50],
            "abstentions": [10, 20, 60, 50, 40],
        }
    )
    out = preprocessing.harmonize_communes(bv, passage)
    assert list(out.columns) == list(bv.columns)
    assert sorted(out["code_commune"]) == ["01001", "01002", "01002", "01004", "01099", "ZZ001"]

    communes = preprocessing.aggregate_by_commune(out).set_index("code_commune")
    # Fusion : (20 + 60) / (100 + 300)
    assert communes.loc["01002", "taux_abstention"] == pytest.approx(20.0)
    # Scission : chaque nouvelle commune garde le taux de l'ancienne
    assert communes.loc["01004", "taux_abstention"] == pytest.approx(25.0)
    assert communes.loc["01099", "taux_abstention"] == pytest.approx(25.0)


# --- Variables socio-économiques ------------------------------------------


def test_youth_share_uses_total_row():
    rows = [("A", f"Y{a}", 1.0) for a in range(100)] + [("A", "Y_GE100", 0.0), ("A", "_T", 100.0)]
    y = preprocessing.youth_share(long(rows, "AGE"))
    # 7 âges (19 à 25 inclus) sur 100 habitants, sans compter la ligne _T
    assert y["A"] == pytest.approx(7.0)


def test_total_population():
    rows = [("A", "Y20", 10.0), ("A", "_T", 1234.4), ("B", "_T", 0.0)]
    pop = preprocessing.total_population(long(rows, "AGE"))
    assert pop.to_dict() == {"A": 1234, "B": 0}


def test_no_diploma_share():
    rows = [("A", "001T100_RP", 25.0), ("A", "300_RP", 75.0), ("A", "_T", 100.0), ("B", "001T100_RP", 0.0), ("B", "_T", 0.0)]
    sd = preprocessing.no_diploma_share(long(rows, "EDUC"))
    assert sd["A"] == pytest.approx(25.0)
    assert np.isnan(sd["B"])


def test_unemployment_rate():
    rows = [("A", "1", 90.0), ("A", "2", 10.0), ("A", "1T2", 100.0)]
    assert preprocessing.unemployment_rate(long(rows, "EMPSTA_ENQ"))["A"] == pytest.approx(10.0)


def test_income_indicators_fallback_to_epci():
    filosofi = pd.DataFrame(
        [
            ("COM", "01001", "PR_MD60", 20.0),
            ("COM", "01001", "MED_SL", 18000.0),
            ("COM", "01002", "MED_SL", 25000.0),  # pauvreté sous secret
            ("EPCI", "E1", "PR_MD60", 12.0),
            ("EPCI", "E1", "MED_SL", 22000.0),
        ],
        columns=["GEO_OBJECT", "GEO", "FILOSOFI_MEASURE", "OBS_VALUE"],
    )
    membership = pd.DataFrame({"CODGEO": ["01001", "01002", "01003", "01004"], "EPCI": ["E1", "E1", "E1", "ZZZZZZZZZ"]})
    out = preprocessing.income_indicators(filosofi, membership)

    assert out.loc["01001", ["P", "R"]].tolist() == [20.0, 18000.0]
    assert out.loc["01001", "P_source"] == "commune"
    assert out.loc["01002", "P"] == 12.0 and out.loc["01002", "P_source"] == "epci"
    assert out.loc["01002", "R"] == 25000.0 and out.loc["01002", "R_source"] == "commune"
    assert out.loc["01003", "R"] == 22000.0 and out.loc["01003", "R_source"] == "epci"
    # Commune sans EPCI (îles) : pas de repli possible
    assert np.isnan(out.loc["01004", "P"]) and pd.isna(out.loc["01004", "P_source"])


def test_income_indicators_with_newer_geography():
    """Filosofi en géographie N+1 : commune fusionnée et EPCI renommé."""
    filosofi = pd.DataFrame(
        [
            ("COM", "01001", "PR_MD60", 20.0),     # 01001 fusionnée dans 01001 (inchangé)
            ("COM", "01001", "MED_SL", 18000.0),
            ("EPCI", "E2", "PR_MD60", 15.0),       # EPCI de la nouvelle géographie
            ("EPCI", "E2", "MED_SL", 21000.0),
        ],
        columns=["GEO_OBJECT", "GEO", "FILOSOFI_MEASURE", "OBS_VALUE"],
    )
    membership = pd.DataFrame({"CODGEO": ["01001", "01002", "01003"], "EPCI": ["E1", "E1", "E1"]})
    passage = pd.DataFrame({"CODGEO_INI": ["01001", "01002", "01003"], "CODGEO_COG": ["01001", "01001", "01003"]})
    membership_new = pd.DataFrame({"CODGEO": ["01001", "01003"], "EPCI": ["E2", "E2"]})

    geo = preprocessing.filosofi_geography(membership, passage, membership_new)
    assert geo.loc["01002", "code_filo"] == "01001"
    assert geo.loc["01003", "epci_filo"] == "E2"

    out = preprocessing.income_indicators(filosofi, membership, geo)
    # 01002 a fusionné dans 01001 : elle prend la valeur de la commune nouvelle
    assert out.loc["01002", "P"] == 20.0 and out.loc["01002", "P_source"] == "commune"
    # 01003 sans valeur propre : repli sur son EPCI dans la nouvelle géographie
    assert out.loc["01003", "P"] == 15.0 and out.loc["01003", "P_source"] == "epci"


def test_merge_tables_keeps_current_communes():
    socio = pd.DataFrame({"LIBGEO": ["A", "B"], "P": [10.0, 20.0]}, index=pd.Index(["01001", "01002"], name="code_commune"))
    abst = pd.DataFrame(
        {"libelle_commune": ["A", "X"], "code_departement": ["01", "01"], "A2022": [20.0, 30.0]},
        index=pd.Index(["01001", "01999"], name="code_commune"),
    )
    merged = preprocessing.merge_tables(socio, abst)
    assert merged.index.tolist() == ["01001", "01002"]
    assert list(merged.columns) == ["LIBGEO", "P", "A2022"]
    assert np.isnan(merged.loc["01002", "A2022"])


# --- Normalisation écrêtée ------------------------------------------------


def test_min_max_clip_limits_outliers():
    s = pd.Series(list(range(1, 100)) + [10_000])
    plain = min_max_normalize(s)
    clipped = min_max_normalize(s, clip=(0.0, 0.98))
    # Sans écrêtage, la valeur aberrante écrase tout : la médiane vaut ~0,005
    assert plain.median() < 0.01
    assert clipped.median() == pytest.approx(0.5, abs=0.02)
    assert clipped.max() == 1.0


def test_compute_all_without_ied_columns():
    df = pd.DataFrame(
        {"A2022": [20.0, 30.0], "A2017": [20.0, 30.0], "A2024": [30.0, 40.0], "P": [10.0, 20.0],
         "C": [5.0, 10.0], "R": [25000.0, 18000.0], "SD": [10.0, 20.0], "Y": [5.0, 8.0]}
    )
    out = indicators.compute_all(df)
    assert "IBM" in out.columns and "IED" not in out.columns


# --- Téléchargement -------------------------------------------------------


class FakeResponse:
    def __init__(self, content: bytes, length: int | None = None):
        self.content = content
        self.headers = {"Content-Length": str(length)} if length else {}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_download_rejects_truncated_parquet_then_retries(tmp_path, monkeypatch):
    good = tmp_path / "ok.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(good)
    responses = [FakeResponse(good.read_bytes()[:20]), FakeResponse(good.read_bytes())]
    monkeypatch.setattr(requests, "get", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(data_loader.time, "sleep", lambda s: None)

    dest = data_loader.download_file("http://x/f.parquet", tmp_path / "f.parquet")
    assert pd.read_parquet(dest)["a"].tolist() == [1, 2]
    assert not (tmp_path / "f.parquet.part").exists()


def test_download_checks_content_length(tmp_path, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(b"abc", length=10))
    monkeypatch.setattr(data_loader.time, "sleep", lambda s: None)
    with pytest.raises(OSError, match="incomplet"):
        data_loader.download_file("http://x/f.csv", tmp_path / "f.csv", retries=2)
    assert not (tmp_path / "f.csv").exists()


def test_read_insee_xlsx(tmp_path):
    header = [["Titre"], ["Sous-titre"], ["Mise en ligne"], ["Source"], ["Libellés longs", "x"]]
    sheet = pd.DataFrame(header + [["CODGEO", "EPCI"], ["01001", "200069193"]])
    xlsx = tmp_path / "t.xlsx"
    sheet.to_excel(xlsx, sheet_name="COM", header=False, index=False)
    zpath = tmp_path / "t.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(xlsx, "t.xlsx")

    df = data_loader.read_insee_xlsx(zpath, "COM")
    assert df.to_dict("records") == [{"CODGEO": "01001", "EPCI": "200069193"}]


def test_read_insee_long_filters_year_and_dims(tmp_path):
    path = tmp_path / "d.parquet"
    pd.DataFrame(
        {
            "GEO": ["01001", "01001", "01001", "01"],
            "GEO_OBJECT": ["COM", "COM", "COM", "DEP"],
            "SEX": ["_T", "F", "_T", "_T"],
            "TIME_PERIOD": pd.to_datetime(["2023-01-01", "2023-01-01", "2017-01-01", "2023-01-01"]).date,
            "OBS_VALUE": [1.0, 2.0, 3.0, 4.0],
        }
    ).to_parquet(path)
    df = data_loader.read_insee_long(path, year=2023, GEO_OBJECT="COM", SEX="_T")
    assert df["OBS_VALUE"].tolist() == [1.0]
