"""
Fonctions utilitaires communes à l'ensemble du projet.

Responsabilités :
- Fonctions de normalisation.
- Fonctions mathématiques communes.
- Chargement de la configuration (dossier config/).

Ce module ne doit contenir aucune logique métier spécifique à l'IBM.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

import pandas as pd
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
WEIGHTS_PATH = CONFIG_DIR / "weights.yaml"


def load_config(name: str) -> dict:
    """Charge config/<name>.yaml."""
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_weights(path: str | Path = WEIGHTS_PATH) -> dict[str, dict[str, float]]:
    """
    Charge le fichier de pondérations et vérifie que chaque bloc somme à 1.
    """
    with open(path, encoding="utf-8") as f:
        weights = yaml.safe_load(f)

    for name, block in weights.items():
        check_weights(block, name=name)

    return weights


def check_weights(weights: Mapping[str, float], name: str = "pondérations") -> None:
    """
    Lève une ValueError si les poids ne sont pas positifs ou ne somment pas à 1.
    """
    if not weights:
        raise ValueError(f"{name} : aucune pondération définie.")

    negatives = [k for k, w in weights.items() if w < 0]
    if negatives:
        raise ValueError(f"{name} : poids négatifs pour {negatives}.")

    total = sum(weights.values())
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise ValueError(f"{name} : la somme des poids vaut {total}, au lieu de 1.")


def min_max_normalize(
    series: pd.Series,
    invert: bool = False,
    clip: tuple[float, float] | None = None,
) -> pd.Series:
    """
    Ramène une série sur l'intervalle [0, 1] (min-max).

    - `invert=True` inverse l'échelle (1 = valeur la plus basse), utile pour
      les variables où une valeur faible traduit un besoin plus fort
      (ex. revenu médian).
    - `clip=(0.01, 0.99)` écrête d'abord la série entre ces deux quantiles,
      pour que quelques valeurs extrêmes n'écrasent pas toutes les autres.
    - Les valeurs manquantes restent manquantes.
    - Une série constante est ramenée à 0 (aucune différence entre territoires).
    """
    series = pd.to_numeric(series, errors="raise").astype(float)
    if clip is not None:
        lo_q, hi_q = clip
        series = series.clip(series.quantile(lo_q), series.quantile(hi_q))

    lo, hi = series.min(), series.max()
    if pd.isna(lo) or lo == hi:
        normalized = series.where(series.isna(), 0.0)
    else:
        normalized = (series - lo) / (hi - lo)

    return 1.0 - normalized if invert else normalized


def weighted_sum(df: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    """
    Somme pondérée des colonnes de `df` nommées par les clés de `weights`.

    Si une des colonnes est manquante pour une ligne, le résultat est NaN :
    on préfère signaler l'absence de donnée plutôt que de produire un score
    calculé sur une base incomplète.
    """
    missing = [col for col in weights if col not in df.columns]
    if missing:
        raise KeyError(f"Colonnes manquantes : {missing}")

    total = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        total = total + w * df[col].astype(float)
    return total
