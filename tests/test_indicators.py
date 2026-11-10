"""
Tests unitaires des indicateurs.

Objectifs :
- Vérifier le calcul des différents indicateurs.
- Contrôler les pondérations.
- Tester les cas limites.
- Garantir la stabilité des calculs au fil des évolutions du projet.
"""

import numpy as np
import pandas as pd
import pytest

from src import indicators
from src.utils import check_weights, load_weights, min_max_normalize, weighted_sum


@pytest.fixture
def weights():
    return load_weights()


@pytest.fixture
def communes():
    """Trois communes fictives : A peu de besoin, C le plus de besoin."""
    return pd.DataFrame(
        {
            "A2022": [20.0, 30.0, 40.0],
            "A2017": [20.0, 30.0, 40.0],
            "A2024": [40.0, 50.0, 60.0],
            "P": [5.0, 15.0, 25.0],
            "C": [4.0, 8.0, 12.0],
            "R": [30000.0, 22000.0, 18000.0],
            "SD": [10.0, 20.0, 30.0],
            "Y": [5.0, 7.0, 9.0],
            "RN": [15.0, 25.0, 45.0],
            "delta_RN": [-2.0, 3.0, 8.0],
        },
        index=pd.Index(["A", "B", "C"], name="commune"),
    )


# --- Configuration --------------------------------------------------------


def test_config_weights_sum_to_one(weights):
    assert set(weights) == {"IBM", "PC", "V", "J", "IED"}
    for block in weights.values():
        assert sum(block.values()) == pytest.approx(1.0)


def test_check_weights_rejects_bad_sum():
    with pytest.raises(ValueError, match="somme"):
        check_weights({"a": 0.5, "b": 0.6})


def test_check_weights_rejects_negative():
    with pytest.raises(ValueError, match="négatifs"):
        check_weights({"a": 1.5, "b": -0.5})


# --- Utilitaires ----------------------------------------------------------


def test_min_max_normalize_bounds():
    s = min_max_normalize(pd.Series([10, 20, 30]))
    assert s.tolist() == [0.0, 0.5, 1.0]


def test_min_max_normalize_inverted():
    s = min_max_normalize(pd.Series([10, 20, 30]), invert=True)
    assert s.tolist() == [1.0, 0.5, 0.0]


def test_min_max_normalize_constant_series():
    assert min_max_normalize(pd.Series([5, 5, 5])).tolist() == [0.0, 0.0, 0.0]


def test_min_max_normalize_keeps_nan():
    s = min_max_normalize(pd.Series([0, np.nan, 10]))
    assert s.iloc[0] == 0.0 and np.isnan(s.iloc[1]) and s.iloc[2] == 1.0


def test_weighted_sum_missing_column():
    with pytest.raises(KeyError, match="x"):
        weighted_sum(pd.DataFrame({"a": [1]}), {"a": 0.5, "x": 0.5})


# --- Indicateurs ----------------------------------------------------------


def test_pc_is_weighted_abstention(communes, weights):
    pc = indicators.compute_pc(communes, weights["PC"])
    # Commune A : 0,60*20 + 0,25*20 + 0,15*40 = 23
    assert pc["A"] == pytest.approx(23.0)
    assert pc["C"] == pytest.approx(0.60 * 40 + 0.25 * 40 + 0.15 * 60)


def test_v_inverts_income(communes, weights):
    v = indicators.compute_v(communes, weights["V"])
    # A est la moins vulnérable sur tous les critères, C la plus vulnérable.
    assert v["A"] == pytest.approx(0.0)
    assert v["C"] == pytest.approx(1.0)
    # B : P 0,5 ; C 0,5 ; R inversé (30000-22000)/12000 = 2/3 ; SD 0,5
    expected_b = 0.35 * 0.5 + 0.25 * 0.5 + 0.25 * (2 / 3) + 0.15 * 0.5
    assert v["B"] == pytest.approx(expected_b)


def test_compute_all_adds_columns_in_range(communes, weights):
    out = indicators.compute_all(communes, weights)
    for col in ["PC", "D", "V", "J", "IBM", "IED"]:
        assert col in out.columns
    for col in ["D", "V", "J", "IBM", "IED"]:
        assert out[col].between(0, 1).all(), col
    # L'entrée n'est pas modifiée.
    assert "IBM" not in communes.columns


def test_ibm_ranking(communes, weights):
    ibm = indicators.compute_all(communes, weights)["IBM"]
    assert ibm["A"] == pytest.approx(0.0)
    assert ibm["C"] == pytest.approx(1.0)
    assert ibm["A"] < ibm["B"] < ibm["C"]


def test_ibm_formula(weights):
    comps = pd.DataFrame({"D": [1.0, 0.0], "V": [0.0, 1.0], "J": [0.0, 0.0]})
    ibm = indicators.compute_ibm(comps, weights["IBM"])
    assert ibm.tolist() == pytest.approx([0.45, 0.40])


def test_ied_independent_of_ibm(communes, weights):
    """Changer les variables RN ne modifie pas l'IBM."""
    other = communes.assign(RN=communes["RN"][::-1].values)
    base = indicators.compute_all(communes, weights)
    changed = indicators.compute_all(other, weights)
    pd.testing.assert_series_equal(base["IBM"], changed["IBM"])
    assert not base["IED"].equals(changed["IED"])


def test_missing_value_propagates(communes, weights):
    communes.loc["B", "P"] = np.nan
    out = indicators.compute_all(communes, weights)
    assert np.isnan(out.loc["B", "V"])
    assert np.isnan(out.loc["B", "IBM"])
    assert not np.isnan(out.loc["A", "IBM"])


def test_compute_all_loads_default_weights(communes):
    out = indicators.compute_all(communes)
    assert "IBM" in out.columns
