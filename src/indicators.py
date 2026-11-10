"""
Module de calcul des indicateurs.

Responsabilités :
- Calcul de la Participation Chronique Pondérée (PC).
- Calcul du Déficit Démocratique (D).
- Calcul de la Vulnérabilité socio-économique (V).
- Calcul du Public Prioritaire Jeunes (J).
- Calcul de l'Indice de Besoin de Mobilisation (IBM).
- Calcul de l'Indice d'Enjeu Extrême Droite (IED).

Toutes les fonctions de ce module prennent des données prétraitées en entrée
(une ligne par commune) et produisent les différents indicateurs utilisés
dans l'application.

Colonnes attendues en entrée (mêmes noms que dans config/weights.yaml) :

    A2022, A2017, A2024   taux d'abstention (en % ou entre 0 et 1)
    P                     taux de pauvreté
    C                     taux de chômage
    R                     revenu médian (en euros)
    SD                    part de la population sans diplôme
    Y                     part des 19-25 ans dans la population
    RN                    score du RN à la présidentielle 2022
    delta_RN              progression du RN entre 2017 et 2022

Toutes les composantes (D, V, J) et les indices (IBM, IED) sont compris
entre 0 et 1 : 1 = besoin (ou enjeu) le plus fort parmi les communes
étudiées. Les scores sont donc relatifs à l'ensemble des communes passées
en entrée : la normalisation min-max doit être faite sur tout le territoire
étudié, pas commune par commune.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from src.utils import check_weights, load_weights, min_max_normalize, weighted_sum

Weights = Mapping[str, float]

# Variables pour lesquelles une valeur élevée traduit un besoin plus faible.
INVERTED_VARIABLES = {"R"}


def _normalize_columns(df: pd.DataFrame, columns) -> pd.DataFrame:
    """Normalise chaque colonne sur [0, 1], en inversant celles qui doivent l'être."""
    return pd.DataFrame(
        {col: min_max_normalize(df[col], invert=col in INVERTED_VARIABLES) for col in columns},
        index=df.index,
    )


def compute_pc(df: pd.DataFrame, weights: Weights) -> pd.Series:
    """
    Participation Chronique Pondérée : moyenne pondérée des taux d'abstention.

    PC = 0,60 A2022 + 0,25 A2017 + 0,15 A2024

    PC reste dans l'unité des taux d'entrée (pas de normalisation), ce qui
    permet de la lire directement comme une abstention moyenne.
    """
    check_weights(weights, "PC")
    return weighted_sum(df, weights).rename("PC")


def compute_d(pc: pd.Series) -> pd.Series:
    """Déficit Démocratique : PC normalisée sur [0, 1]."""
    return min_max_normalize(pc).rename("D")


def compute_v(df: pd.DataFrame, weights: Weights) -> pd.Series:
    """
    Vulnérabilité socio-économique.

    V = 0,35 P + 0,25 C + 0,25 R + 0,15 SD

    Chaque variable est normalisée sur [0, 1] ; le revenu médian R est
    inversé (un revenu faible correspond à une vulnérabilité forte).
    """
    check_weights(weights, "V")
    return weighted_sum(_normalize_columns(df, weights), weights).rename("V")


def compute_j(df: pd.DataFrame, weights: Weights) -> pd.Series:
    """Public Prioritaire Jeunes : J = Y normalisée."""
    check_weights(weights, "J")
    return weighted_sum(_normalize_columns(df, weights), weights).rename("J")


def compute_ibm(components: pd.DataFrame, weights: Weights) -> pd.Series:
    """
    Indice de Besoin de Mobilisation.

    IBM = 0,45 D + 0,40 V + 0,15 J

    `components` doit contenir les colonnes D, V et J (déjà sur [0, 1]).
    """
    check_weights(weights, "IBM")
    return weighted_sum(components, weights).rename("IBM")


def compute_ied(df: pd.DataFrame, weights: Weights) -> pd.Series:
    """
    Indice d'Enjeu Extrême Droite (indépendant de l'IBM).

    IED = 0,70 RN + 0,30 ΔRN, chaque variable normalisée sur [0, 1].
    """
    check_weights(weights, "IED")
    return weighted_sum(_normalize_columns(df, weights), weights).rename("IED")


def compute_all(df: pd.DataFrame, weights: Mapping[str, Weights] | None = None) -> pd.DataFrame:
    """
    Calcule l'ensemble des indicateurs et les ajoute à une copie de `df`.

    Colonnes ajoutées : PC, D, V, J, IBM, IED.
    Si `weights` n'est pas fourni, les poids sont lus dans config/weights.yaml.
    """
    if weights is None:
        weights = load_weights()

    out = df.copy()
    out["PC"] = compute_pc(out, weights["PC"])
    out["D"] = compute_d(out["PC"])
    out["V"] = compute_v(out, weights["V"])
    out["J"] = compute_j(out, weights["J"])
    out["IBM"] = compute_ibm(out[["D", "V", "J"]], weights["IBM"])
    out["IED"] = compute_ied(out, weights["IED"])
    return out
