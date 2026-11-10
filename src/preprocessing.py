"""
Module de prétraitement des données.

Responsabilités :
- Nettoyer les jeux de données.
- Uniformiser les noms de colonnes.
- Convertir les types de données.
- Agréger les bureaux de vote par commune.
- Fusionner les différentes bases de données.
- Gérer les valeurs manquantes.
- Recalculer les indicateurs intermédiaires (participation, abstention, etc.).

Les données produites par ce module sont prêtes à être utilisées pour le calcul
des indicateurs.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

# Code département des « Français établis hors de France » : pas une commune.
ABROAD_DEPARTMENT = "ZZ"

COUNT_COLUMNS = ["inscrits", "abstentions", "votants", "exprimes"]


def aggregate_by_commune(bv: pd.DataFrame, exclude_abroad: bool = True) -> pd.DataFrame:
    """
    Agrège les résultats par bureau de vote au niveau commune.

    Les effectifs (inscrits, abstentions, votants, exprimés) sont sommés, puis
    le taux d'abstention est recalculé à partir des sommes :

        taux_abstention = abstentions / inscrits × 100

    (on ne fait surtout pas la moyenne des taux des bureaux, qui donnerait le
    même poids à un bureau de 50 inscrits et à un bureau de 1 500).

    Une ligne par (id_election, code_commune).
    """
    if exclude_abroad:
        bv = bv[bv["code_departement"] != ABROAD_DEPARTMENT]

    counts = [c for c in COUNT_COLUMNS if c in bv.columns]
    keys = ["id_election", "code_commune"]
    labels = [c for c in ("libelle_commune", "code_departement") if c in bv.columns]

    communes = bv.groupby(keys, as_index=False).agg(
        **{c: (c, "first") for c in labels},
        **{c: (c, "sum") for c in counts},
    )

    inscrits = communes["inscrits"].astype(float).replace(0, np.nan)
    communes["taux_abstention"] = communes["abstentions"] / inscrits * 100
    return communes


def abstention_by_commune(communes: pd.DataFrame, mapping: Mapping[str, str]) -> pd.DataFrame:
    """
    Construit la table des taux d'abstention, une ligne par commune.

    - `communes` : sortie de `aggregate_by_commune`.
    - `mapping` : nom de colonne → identifiant d'élection,
      ex. {"A2022": "2022_pres_t1", "A2017": "2017_pres_t1"}.

    Résultat indexé par `code_commune`, avec `libelle_commune`,
    `code_departement` (pris dans l'élection la plus récente) et une colonne
    de taux (en %) par entrée de `mapping`. Une commune absente d'un scrutin
    (ex. commune créée ou fusionnée entre-temps) a une valeur manquante.
    """
    missing = sorted(set(mapping.values()) - set(communes["id_election"]))
    if missing:
        raise ValueError(f"Élection(s) absente(s) des données : {missing}")

    wanted = communes[communes["id_election"].isin(mapping.values())]
    rates = wanted.pivot(index="code_commune", columns="id_election", values="taux_abstention")
    rates = pd.DataFrame({col: rates[election] for col, election in mapping.items()})

    # Libellés : l'élection la plus récente (les identifiants commencent par l'année).
    label_cols = [c for c in ("libelle_commune", "code_departement") if c in communes.columns]
    labels = (
        wanted.sort_values("id_election")
        .groupby("code_commune")[label_cols]
        .last()
    )

    table = labels.join(rates, how="right")
    table.index.name = "code_commune"
    return table.sort_index()
