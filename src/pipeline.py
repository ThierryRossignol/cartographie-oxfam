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
    data/outputs/carte_*.png               cartes France métropolitaine
    data/outputs/carte_interactive.html    carte interactive (IBM / IED)
    data/outputs/communes_indicateurs.geojson  couche pour le dashboard

    python -m src.pipeline cartes     (ou : make cartes)  cartes seules,
                                      à partir de data/processed/
    python -m src.pipeline publier    (ou : make publier) met à jour
                                      data/published/ pour le dashboard en ligne
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from src import export, indicators, mapping, preprocessing
from src.data_loader import ContoursLoader, ElectionLoader, InseeLoader
from src.utils import load_config

ABSTENTION_FILE = export.INTERIM_DIR / "abstention_communes.csv"
RN_FILE = export.INTERIM_DIR / "rn_communes.csv"
SOCIO_FILE = export.INTERIM_DIR / "socio_communes.csv"
IBM_FILE = export.PROCESSED_DIR / "ibm_communes.csv"

# Paquet versionné dans git, utilisé par le dashboard en ligne
# (Streamlit Community Cloud), qui ne peut pas relancer tout le pipeline.
PUBLISHED_DIR = export.ROOT_DIR / "data" / "published"
PUBLISHED_RESULTS = PUBLISHED_DIR / "ibm_communes.parquet"
PUBLISHED_CONTOURS = PUBLISHED_DIR / "communes-1000m.geojson.gz"
PUBLISHED_METADATA = PUBLISHED_DIR / "metadata.json"


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
    names = ied["candidats"]
    reference_names = ied.get("candidats_reference") or names
    candidates = loader.load_candidates([ied["scrutin"], ied["scrutin_reference"]])
    for election, wanted in [(ied["scrutin"], names), (ied["scrutin_reference"], reference_names)]:
        found = set(candidates.loc[candidates["id_election"] == election, "nom"])
        if missing := sorted(set(wanted) - found):
            raise ValueError(f"Candidat(s) introuvable(s) à {election} : {missing}")
    candidates = preprocessing.harmonize_communes(candidates, passage)
    far_right = preprocessing.far_right_by_commune(
        candidates, names, ied["scrutin"], ied["scrutin_reference"], reference_names
    )

    excluded = _excluded_prefixes()
    return (
        preprocessing.filter_perimeter(abstention, excluded),
        preprocessing.filter_perimeter(far_right, excluded),
    )


def build_socio(insee: InseeLoader | None = None) -> pd.DataFrame:
    """Variables socio-économiques INSEE par commune."""
    insee = insee or InseeLoader()
    membership = insee.commune_membership()
    passage_filo, membership_filo = insee.filosofi_geography()
    table = preprocessing.socio_by_commune(
        population=insee.population_by_age(),
        diplomas=insee.diplomas(),
        employment=insee.employment(),
        filosofi=insee.filosofi(),
        membership=membership,
        filosofi_geo=preprocessing.filosofi_geography(membership, passage_filo, membership_filo),
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


def results_path():
    """
    Table des indicateurs à utiliser : celle calculée localement
    (data/processed/) si elle existe, sinon le paquet publié
    (data/published/), ou None si aucune n'existe.
    """
    for path in (IBM_FILE, PUBLISHED_RESULTS):
        if path.exists():
            return path
    return None


def read_results(path=None) -> pd.DataFrame:
    """Relit la table des indicateurs en gardant les codes en texte."""
    path = path or results_path() or IBM_FILE
    if str(path).endswith(".parquet"):
        return pd.read_parquet(path)
    codes = {"code_commune": str, "DEP": str, "EPCI": str}
    return pd.read_csv(path, dtype=codes).set_index("code_commune")


def data_metadata() -> dict:
    """
    Dates des données : calcul de la table des indicateurs et
    téléchargement de chaque fichier source (date du fichier dans
    data/raw/). Affichées dans la page « À propos ».
    """
    from datetime import datetime

    def day(path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")

    raw = export.ROOT_DIR / "data" / "raw"
    files = sorted(p for p in raw.rglob("*") if p.is_file() and p.name != ".gitkeep")
    return {
        "calcul": day(IBM_FILE),
        "telechargements": {str(p.relative_to(raw)).replace("\\", "/"): day(p) for p in files},
    }


def run_publish() -> None:
    """
    Met à jour data/published/ (à versionner) à partir des résultats
    locaux : table des indicateurs (Parquet) et contours des communes.
    """
    import shutil

    if not IBM_FILE.exists():
        raise FileNotFoundError(f"{IBM_FILE} absent : lancer d'abord `make data`.")
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    read_results(IBM_FILE).to_parquet(PUBLISHED_RESULTS)
    shutil.copyfile(ContoursLoader().source_path("1000m"), PUBLISHED_CONTOURS)
    PUBLISHED_METADATA.write_text(json.dumps(data_metadata(), ensure_ascii=False, indent=2), encoding="utf-8")
    for path in (PUBLISHED_RESULTS, PUBLISHED_CONTOURS, PUBLISHED_METADATA):
        print(f"Écrit : {path} ({path.stat().st_size / 1e6:.1f} Mo)")


def run_maps() -> None:
    if not IBM_FILE.exists():
        raise FileNotFoundError(f"{IBM_FILE} absent : lancer d'abord `make data`.")
    results = read_results()
    communes = mapping.join_indicators(ContoursLoader().communes("1000m"), results)
    outlines = mapping.department_outlines(communes)
    out = export.OUTPUTS_DIR

    print(f"Écrit : {export.save_figure(mapping.choropleth(communes, 'IBM', outlines), out / 'carte_ibm.png')}")
    print(f"Écrit : {export.save_figure(mapping.choropleth(communes, 'IED', outlines), out / 'carte_ied.png')}")
    print(f"Écrit : {export.save_figure(mapping.priority_map(communes, outlines), out / 'carte_prioritaires.png')}")
    print(f"Écrit : {export.save_html_map(mapping.interactive_map(communes), out / 'carte_interactive.html')}")
    layer = mapping.dashboard_layer(communes)
    print(f"Écrit : {export.save_geojson(layer, out / 'communes_indicateurs.geojson')}")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    {"elections": run_elections, "all": run_all, "cartes": run_maps, "publier": run_publish}[step]()
