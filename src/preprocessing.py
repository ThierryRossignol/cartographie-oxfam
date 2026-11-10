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


def filter_perimeter(df: pd.DataFrame, excluded_prefixes: list[str]) -> pd.DataFrame:
    """
    Retire les communes dont le code INSEE commence par l'un des préfixes
    (voir config/perimetre.yaml). Le code est lu dans la colonne
    `code_commune`, ou à défaut dans l'index.
    """
    codes = df["code_commune"] if "code_commune" in df.columns else df.index.to_series()
    excluded = codes.astype(str).str.startswith(tuple(excluded_prefixes))
    return df[~excluded.to_numpy()]


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


# ----------------------------------------------------------------------------
# Géographie : recalage des codes communes
# ----------------------------------------------------------------------------


def harmonize_communes(df: pd.DataFrame, passage: pd.DataFrame, column: str = "code_commune") -> pd.DataFrame:
    """
    Remplace les codes communes historiques par les codes actuels.

    `passage` : table CODGEO_INI → CODGEO_COG (InseeLoader.commune_passage).
    - Communes fusionnées : plusieurs anciens codes → un code actuel. Les
      effectifs sont ensuite sommés par `aggregate_by_commune`.
    - Communes scindées : un ancien code → plusieurs codes actuels ; la
      ligne est dupliquée, chaque nouvelle commune hérite du taux de
      l'ancienne (inscrits et abstentions sont dupliqués ensemble).
    - Codes absents de la table (ex. ZZ001 pour l'étranger) : inchangés.
    """
    mapping = passage[["CODGEO_INI", "CODGEO_COG"]].drop_duplicates()
    out = df.merge(mapping, how="left", left_on=column, right_on="CODGEO_INI")
    out[column] = out["CODGEO_COG"].fillna(out[column])
    return out.drop(columns=["CODGEO_INI", "CODGEO_COG"])


# ----------------------------------------------------------------------------
# Variables socio-économiques (INSEE)
#
# Les fichiers INSEE sont au format « long » : GEO, dimensions, OBS_VALUE.
# Chaque fonction renvoie une Series indexée par code commune, en %.
# ----------------------------------------------------------------------------


def _share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """numérateur / dénominateur × 100, NaN si le dénominateur est nul."""
    return numerator / denominator.replace(0, np.nan) * 100


def youth_share(population: pd.DataFrame, age_min: int = 19, age_max: int = 25) -> pd.Series:
    """
    Y — part (%) de la population âgée de `age_min` à `age_max` ans inclus.

    `population` : InseeLoader.population_by_age (AGE = Y0…Y99, Y_GE100, _T).
    Le dénominateur est la ligne `_T` (total), et non la somme des âges.
    """
    wide = population.pivot_table(index="GEO", columns="AGE", values="OBS_VALUE", aggfunc="sum")
    ages = [f"Y{a}" for a in range(age_min, age_max + 1)]
    return _share(wide[ages].sum(axis=1), wide["_T"]).rename("Y")


def no_diploma_share(diplomas: pd.DataFrame) -> pd.Series:
    """
    SD — part (%) des 15 ans ou plus non scolarisés sans diplôme
    (aucun diplôme ou certificat d'études primaires).
    """
    wide = diplomas.pivot_table(index="GEO", columns="EDUC", values="OBS_VALUE", aggfunc="sum")
    return _share(wide["001T100_RP"], wide["_T"]).rename("SD")


def unemployment_rate(employment: pd.DataFrame) -> pd.Series:
    """
    C — taux de chômage (%) des 15-64 ans au sens du recensement :
    chômeurs / actifs.
    """
    wide = employment.pivot_table(index="GEO", columns="EMPSTA_ENQ", values="OBS_VALUE", aggfunc="sum")
    return _share(wide["2"], wide["1T2"]).rename("C")


def income_indicators(filosofi: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    """
    P (taux de pauvreté, %) et R (niveau de vie médian, €) par commune.

    Le secret statistique masque le taux de pauvreté des communes de moins
    de ~1 000 ménages (88 % des communes) et le niveau de vie médian des
    plus petites. Dans ce cas, on prend la valeur de l'intercommunalité
    (EPCI), toujours disponible. Les colonnes P_source / R_source indiquent
    l'origine de chaque valeur : "commune" ou "epci".

    `membership` : InseeLoader.commune_membership (CODGEO, EPCI).
    """
    wide = filosofi.pivot_table(
        index=["GEO_OBJECT", "GEO"], columns="FILOSOFI_MEASURE", values="OBS_VALUE"
    )
    commune = wide.loc["COM"] if "COM" in wide.index.get_level_values(0) else wide.iloc[:0]
    epci = wide.loc["EPCI"] if "EPCI" in wide.index.get_level_values(0) else wide.iloc[:0]

    out = membership[["CODGEO", "EPCI"]].set_index("CODGEO")
    for var, measure in [("P", "PR_MD60"), ("R", "MED_SL")]:
        own = out.index.map(commune[measure]) if measure in commune else np.nan
        fallback = out["EPCI"].map(epci[measure]) if measure in epci else np.nan
        own = pd.Series(own, index=out.index, dtype=float)
        out[var] = own.fillna(pd.Series(fallback, index=out.index, dtype=float))
        out[f"{var}_source"] = np.where(own.notna(), "commune", np.where(out[var].notna(), "epci", None))

    out.index.name = "code_commune"
    return out.drop(columns="EPCI")


def socio_by_commune(
    population: pd.DataFrame,
    diplomas: pd.DataFrame,
    employment: pd.DataFrame,
    filosofi: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    """
    Table socio-économique, une ligne par commune actuelle :
    libellé, département, EPCI, P, R, C, SD, Y (+ P_source, R_source).
    """
    base = membership.set_index("CODGEO")[["LIBGEO", "DEP", "EPCI"]]
    base.index.name = "code_commune"
    table = base.join(income_indicators(filosofi, membership))
    table = table.join(unemployment_rate(employment)).join(no_diploma_share(diplomas)).join(youth_share(population))
    return table.sort_index()


def merge_tables(abstention: pd.DataFrame, socio: pd.DataFrame) -> pd.DataFrame:
    """
    Fusionne abstention et socio-économie sur le code commune.

    On part de la table socio (communes actuelles) : une commune sans
    résultat électoral garde des valeurs manquantes d'abstention.
    """
    election_cols = [c for c in abstention.columns if c not in ("libelle_commune", "code_departement")]
    return socio.join(abstention[election_cols], how="left")
