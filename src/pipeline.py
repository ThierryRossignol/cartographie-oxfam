"""
Enchaînement des étapes du pipeline (téléchargement → prétraitement → export).

Ce module ne contient aucune logique propre : il appelle les autres modules
dans l'ordre. À lancer depuis la racine du projet :

    python -m src.pipeline          (ou : make elections)
"""

from __future__ import annotations

from pathlib import Path

from src import export, preprocessing
from src.data_loader import ElectionLoader
from src.utils import load_config

ABSTENTION_FILE = export.INTERIM_DIR / "abstention_communes.csv"


def build_abstention(path: Path = ABSTENTION_FILE) -> Path:
    """Produit data/interim/abstention_communes.csv (une ligne par commune)."""
    mapping = load_config("elections")["abstention"]

    bv = ElectionLoader().load(list(mapping.values()))
    communes = preprocessing.aggregate_by_commune(bv)
    table = preprocessing.abstention_by_commune(communes, mapping)

    print(f"{len(table)} communes ; valeurs manquantes par scrutin :")
    print(table[list(mapping)].isna().sum().to_string())
    return export.save_csv(table, path)


if __name__ == "__main__":
    print(f"Écrit : {build_abstention()}")
