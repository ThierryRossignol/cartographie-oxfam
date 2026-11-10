"""
Enchaînement des étapes du pipeline (téléchargement → prétraitement → export).

Ce module ne contient aucune logique propre : il appelle les autres modules
dans l'ordre. À lancer depuis la racine du projet :

    python -m src.pipeline            (ou : make data)   tout le pipeline
    python -m src.pipeline elections  (ou : make elections)

Fichiers produits :
    data/interim/abstention_communes.csv   abstention par commune (COG actuel)
    data/interim/socio_communes.csv        variables INSEE par commune
    data/processed/ibm_communes.csv        table fusionnée + indicateurs
"""

from __future__ import annotations

import sys

import pandas as pd

from src import export, indicators, preprocessing
from src.data_loader import ElectionLoader, InseeLoader
from src.utils import load_config

ABSTENTION_FILE = export.INTERIM_DIR / "abstention_communes.csv"
SOCIO_FILE = export.INTERIM_DIR / "socio_communes.csv"
IBM_FILE = export.PROCESSED_DIR / "ibm_communes.csv"


def _excluded_prefixes() -> list[str]:
    return load_config("perimetre")["exclure_codes_commune"]


def build_abstention(insee: InseeLoader | None = None) -> pd.DataFrame:
    """Taux d'abstention par commune, codes recalés sur le COG actuel."""
    insee = insee or InseeLoader()
    mapping = load_config("elections")["abstention"]

    bv = ElectionLoader().load(list(mapping.values()))
    bv = preprocessing.harmonize_communes(bv, insee.commune_passage())
    communes = preprocessing.aggregate_by_commune(bv)
    table = preprocessing.abstention_by_commune(communes, mapping)
    return preprocessing.filter_perimeter(table, _excluded_prefixes())


def build_socio(insee: InseeLoader | None = None) -> pd.DataFrame:
    """Variables socio-économiques INSEE par commune."""
    insee = insee or InseeLoader()
    table = preprocessing.socio_by_commune(
        population=insee.population_by_age(),
        diplomas=insee.diplomas(),
        employment=insee.employment(),
        filosofi=insee.filosofi(),
        membership=insee.commune_membership(),
    )
    return preprocessing.filter_perimeter(table, _excluded_prefixes())


def report_missing(table: pd.DataFrame, columns: list[str]) -> None:
    print(f"  {len(table)} communes ; valeurs manquantes :")
    print(table[columns].isna().sum().to_string().replace("\n", "\n    ").join(["    ", ""]))


def run_elections() -> None:
    table = build_abstention()
    report_missing(table, list(load_config("elections")["abstention"]))
    print(f"Écrit : {export.save_csv(table, ABSTENTION_FILE)}")


def run_all() -> None:
    insee = InseeLoader()

    print("1/3 Abstention")
    abstention = build_abstention(insee)
    report_missing(abstention, list(load_config("elections")["abstention"]))
    export.save_csv(abstention, ABSTENTION_FILE)

    print("2/3 Socio-économie (INSEE)")
    socio = build_socio(insee)
    report_missing(socio, ["P", "R", "C", "SD", "Y"])
    for var in ("P", "R"):
        print(f"  {var} : " + socio[f"{var}_source"].value_counts().to_string().replace("\n", ", "))
    export.save_csv(socio, SOCIO_FILE)

    print("3/3 Fusion et indicateurs")
    merged = preprocessing.merge_tables(abstention, socio)
    result = indicators.compute_all(merged)
    complete = result["IBM"].notna().sum()
    print(f"  IBM calculé pour {complete} communes sur {len(result)}")
    print(f"Écrit : {export.save_csv(result, IBM_FILE)}")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"elections": run_elections, "all": run_all}[step]()
