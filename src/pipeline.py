"""
Enchaînement des étapes du pipeline (téléchargement → prétraitement → export).

Ce module ne contient aucune logique propre : il appelle les autres modules
dans l'ordre. À lancer depuis la racine du projet :

    python -m src.pipeline            (ou : make data)   tout le pipeline
    python -m src.pipeline elections  (ou : make elections)

Fichiers produits :
    data/interim/abstention_communes.csv   abstention par commune (COG actuel)
    data/interim/rn_communes.csv           score et progression du RN par commune
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
RN_FILE = export.INTERIM_DIR / "rn_communes.csv"
SOCIO_FILE = export.INTERIM_DIR / "socio_communes.csv"
IBM_FILE = export.PROCESSED_DIR / "ibm_communes.csv"


def _excluded_prefixes() -> list[str]:
    return load_config("perimetre")["exclure_codes_commune"]


def build_elections(insee: InseeLoader | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Tables électorales par commune, codes recalés sur le COG actuel :
    - abstention (A2022, A2017, A2024) ;
    - extrême droite (RN, delta_RN) pour l'IED.
    """
    insee = insee or InseeLoader()
    config = load_config("elections")
    mapping, ied = config["abstention"], config["ied"]
    elections = sorted(set(mapping.values()) | {ied["scrutin"], ied["scrutin_reference"]})

    loader = ElectionLoader()
    passage = insee.commune_passage()

    bv = preprocessing.harmonize_communes(loader.load(elections), passage)
    communes = preprocessing.aggregate_by_commune(bv)
    abstention = preprocessing.abstention_by_commune(communes, mapping)

    # Tous les candidats : leurs voix servent à recalculer les exprimés.
    candidates = loader.load_candidates([ied["scrutin"], ied["scrutin_reference"]])
    missing = sorted(set(ied["candidats"]) - set(candidates["nom"]))
    if missing:
        raise ValueError(f"Candidat(s) introuvable(s) : {missing}")
    candidates = preprocessing.harmonize_communes(candidates, passage)
    far_right = preprocessing.far_right_by_commune(
        candidates, ied["candidats"], ied["scrutin"], ied["scrutin_reference"]
    )

    excluded = _excluded_prefixes()
    return (
        preprocessing.filter_perimeter(abstention, excluded),
        preprocessing.filter_perimeter(far_right, excluded),
    )


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


def run_elections() -> tuple[pd.DataFrame, pd.DataFrame]:
    abstention, far_right = build_elections()
    report_missing(abstention, list(load_config("elections")["abstention"]))
    report_missing(far_right, ["RN", "delta_RN"])
    print(f"Écrit : {export.save_csv(abstention, ABSTENTION_FILE)}")
    print(f"Écrit : {export.save_csv(far_right, RN_FILE)}")
    return abstention, far_right


def run_all() -> None:
    insee = InseeLoader()

    print("1/3 Élections (abstention, extrême droite)")
    abstention, far_right = run_elections()

    print("2/3 Socio-économie (INSEE)")
    socio = build_socio(insee)
    report_missing(socio, ["P", "R", "C", "SD", "Y"])
    for var in ("P", "R"):
        print(f"  {var} : " + socio[f"{var}_source"].value_counts().to_string().replace("\n", ", "))
    export.save_csv(socio, SOCIO_FILE)

    print("3/3 Fusion et indicateurs")
    merged = preprocessing.merge_tables(socio, abstention, far_right)
    result = indicators.compute_all(merged)
    for col in ("IBM", "IED"):
        print(f"  {col} calculé pour {result[col].notna().sum()} communes sur {len(result)}")
    print(f"Écrit : {export.save_csv(result, IBM_FILE)}")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"elections": run_elections, "all": run_all}[step]()
