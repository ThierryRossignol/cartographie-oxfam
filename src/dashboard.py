"""
Logique du dashboard Streamlit (dossier app/).

Toute la préparation des données affichées est ici, sans dépendance à
Streamlit, pour pouvoir être testée. Les pages de app/ ne font que
l'affichage et la mise en cache.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src import mapping
from src.pipeline import IBM_FILE, read_results

INDICATORS = {
    "IBM": "Indice de Besoin de Mobilisation",
    "IED": "Indice d'Enjeu Extrême Droite",
}

COMPONENTS = {
    "D": "Déficit démocratique",
    "V": "Vulnérabilité socio-économique",
    "J": "Public prioritaire jeunes",
}

# Variables brutes : libellé, unité, nombre de décimales
VARIABLES = {
    "A2022": ("Abstention présidentielle 2022 (1er tour)", "%", 1),
    "A2017": ("Abstention présidentielle 2017 (1er tour)", "%", 1),
    "A2024": ("Abstention législatives 2024 (1er tour)", "%", 1),
    "P": ("Taux de pauvreté", "%", 1),
    "C": ("Taux de chômage (15-64 ans)", "%", 1),
    "R": ("Niveau de vie médian", "€", 0),
    "SD": ("Part des sans-diplôme", "%", 1),
    "Y": ("Part des 19-25 ans", "%", 1),
    "RN": ("Score RN présidentielle 2022", "%", 1),
    "delta_RN": ("Progression du RN depuis 2017", "pts", 1),
}

# Pour ces variables, une valeur faible traduit un besoin plus fort.
LOWER_IS_NEEDIER = {"R"}


ELECTION_TYPES = {
    "pres": "Présidentielle", "legi": "Législatives", "euro": "Européennes", "muni": "Municipales",
    "regi": "Régionales", "dpmt": "Départementales", "cant": "Cantonales",
}


def election_label(election_id: str) -> str:
    """« 2022_pres_t1 » → « Présidentielle 2022, 1er tour »."""
    year, kind, tour = election_id.split("_")
    n = tour.lstrip("t")
    return f"{ELECTION_TYPES.get(kind, kind)} {year}, {n}{'er' if n == '1' else 'e'} tour"


# ----------------------------------------------------------------------------
# Chargement et enrichissement
# ----------------------------------------------------------------------------


def results_available() -> bool:
    return IBM_FILE.exists()


def enrich(results: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute à la table des indicateurs ce dont le dashboard a besoin :
    nom du département complété, rang et classe (1 à 5) de l'IBM et de
    l'IED, drapeau « prioritaire », libellé de recherche.
    """
    df = results.copy()
    # Nom du département : complété pour les communes sans résultat électoral
    names = df.groupby("DEP")["libelle_departement"].agg(lambda s: s.dropna().iloc[0] if s.notna().any() else None)
    df["departement"] = df["DEP"].map(names).fillna(df["DEP"])

    for col in INDICATORS:
        df[f"rang_{col}"] = df[col].rank(ascending=False, method="min").astype("Int64")
        codes = mapping.quantile_classes(df[col]).codes
        df[f"classe_{col}"] = (codes + 1).where(codes >= 0).astype("Int64")

    df["prioritaire"] = mapping.is_priority(df["IBM"]).fillna(False)
    df["recherche"] = df["LIBGEO"] + " (" + df["DEP"] + ")"
    return df


def load() -> pd.DataFrame:
    """Table des indicateurs enrichie (data/processed/ibm_communes.csv)."""
    return enrich(read_results())


def department_options(df: pd.DataFrame) -> dict[str, str]:
    """{code : « 02 — Aisne »}, triés par code."""
    names = df.groupby("DEP")["departement"].first().sort_index()
    return {code: f"{code} — {name}" for code, name in names.items()}


# ----------------------------------------------------------------------------
# Filtres
# ----------------------------------------------------------------------------


@dataclass
class Filters:
    departments: list[str] | None = None   # None ou [] = toute la métropole
    min_population: int = 0
    only_priority: bool = False
    ied_classes: list[int] | None = None    # classes d'IED à garder (1 à 5)

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        mask = pd.Series(True, index=df.index)
        if self.departments:
            mask &= df["DEP"].isin(self.departments)
        if self.min_population:
            mask &= df["population"].fillna(0) >= self.min_population
        if self.only_priority:
            mask &= df["prioritaire"]
        if self.ied_classes:
            mask &= df["classe_IED"].isin(self.ied_classes)
        return df[mask]


def summary(df: pd.DataFrame, reference: pd.DataFrame) -> dict[str, float]:
    """Chiffres clés d'une sélection de communes, rapportés à `reference`."""
    population = df["population"].sum()
    priority = df[df["prioritaire"]]
    return {
        "communes": len(df),
        "population": int(population),
        "prioritaires": len(priority),
        "population_prioritaire": int(priority["population"].sum()),
        "part_population_prioritaire": float(priority["population"].sum() / population) if population else np.nan,
        "part_communes": len(df) / len(reference) if len(reference) else np.nan,
    }


def ranking(df: pd.DataFrame, indicator: str = "IBM", limit: int | None = None) -> pd.DataFrame:
    """Classement des communes par indicateur décroissant (valeurs manquantes à la fin)."""
    out = df.sort_values(indicator, ascending=False, na_position="last")
    return out.head(limit) if limit else out


# ----------------------------------------------------------------------------
# Fiche commune
# ----------------------------------------------------------------------------


def commune_profile(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """
    Variables brutes d'une commune comparées à la médiane métropolitaine
    et au département, avec le centile de la commune (0 = plus faible,
    100 = plus élevé) : une ligne par variable.
    """
    row = df.loc[code]
    dep = df[df["DEP"] == row["DEP"]]
    records = []
    for var, (label, unit, _) in VARIABLES.items():
        if var not in df.columns:
            continue
        value = row[var]
        percentile = (df[var] < value).mean() * 100 if pd.notna(value) else np.nan
        records.append(
            {
                "variable": var,
                "libellé": label,
                "unité": unit,
                "commune": value,
                "département (médiane)": dep[var].median(),
                "France (médiane)": df[var].median(),
                "centile": percentile,
                "besoin plus fort si": "faible" if var in LOWER_IS_NEEDIER else "élevé",
            }
        )
    return pd.DataFrame(records).set_index("variable")


def format_value(value: float, unit: str, decimals: int) -> str:
    """Nombre à la française : « 12,3 % », « 21 450 € », « −2,1 pts »."""
    if pd.isna(value):
        return "—"
    text = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",").replace("-", "−")
    return f"{text} {unit}".strip()


def neighbours(df: pd.DataFrame, code: str, n: int = 10, indicator: str = "IBM") -> pd.DataFrame:
    """Les `n` communes du même département au rang d'IBM le plus proche."""
    row = df.loc[code]
    dep = df[(df["DEP"] == row["DEP"]) & df[indicator].notna()]
    distance = (dep[indicator] - row[indicator]).abs()
    return dep.loc[distance.sort_values().index[: n + 1]].sort_values(indicator, ascending=False)


# ----------------------------------------------------------------------------
# Carte (pydeck)
# ----------------------------------------------------------------------------


def hex_to_rgb(color: str) -> list[int]:
    color = color.lstrip("#")
    return [int(color[i : i + 2], 16) for i in (0, 2, 4)]


def map_features(communes, indicator: str, highlight: set[str] | None = None) -> dict:
    """
    GeoJSON prêt pour pydeck : couleur de remplissage selon la classe de
    l'indicateur (mêmes quintiles et couleurs que les cartes PNG), calculée
    sur toute la métropole pour que les couleurs ne changent pas quand on
    filtre. Les communes hors `highlight` (si fourni) sont en gris clair.

    `communes` : GeoDataFrame avec code_commune, LIBGEO, indicateurs,
    et la colonne `classe_<indicateur>` (voir `enrich`).
    """
    import json

    palette = [hex_to_rgb(c) for c in mapping.PALETTES[indicator]]
    missing = hex_to_rgb(mapping.MISSING_COLOR)
    other = hex_to_rgb(mapping.OTHER_COLOR)

    classes = communes[f"classe_{indicator}"]
    fill = [palette[int(c) - 1] if pd.notna(c) else missing for c in classes]
    if highlight is not None:
        fill = [f if code in highlight else other for f, code in zip(fill, communes["code_commune"])]

    data = communes[["code_commune", "LIBGEO", "departement", "population", "IBM", "IED", "D", "V", "J", "geometry"]].copy()
    data["fill"] = fill
    for col in ("IBM", "IED", "D", "V", "J"):
        data[col] = data[col].map(lambda v: "—" if pd.isna(v) else f"{v:.2f}".replace(".", ","))
    data["population"] = data["population"].map(lambda v: format_value(v, "hab.", 0))
    return json.loads(data.to_json())


def legend(indicator: str, df: pd.DataFrame) -> list[tuple[str, str]]:
    """[(couleur, « 0,53 – 1,00 · 20 % les plus élevés »), …], du plus élevé au plus faible."""
    classes = mapping.quantile_classes(df[indicator])
    labels = classes.labels()
    out = []
    for i in reversed(range(classes.k)):
        suffix = " · 20 % les plus élevés" if i == classes.k - 1 else (" · 20 % les plus faibles" if i == 0 else "")
        out.append((mapping.PALETTES[indicator][i], labels[i] + suffix))
    out.append((mapping.MISSING_COLOR, "Donnée manquante"))
    return out
