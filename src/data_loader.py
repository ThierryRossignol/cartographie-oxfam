"""
Chargement des données publiques du projet Cartographie Oxfam.

Ce module contient les classes permettant de récupérer les données
depuis les différentes sources (API, fichiers distants...).

Principe « une seule source de vérité » : chaque fichier est téléchargé une
seule fois dans data/raw/, puis toutes les lectures se font sur cette copie
locale. Aucune analyse n'est réalisée ici.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests

from src.utils import ROOT_DIR

RAW_DIR = ROOT_DIR / "data" / "raw"


def download_file(url: str, destination: Path, timeout: int = 60) -> Path:
    """
    Télécharge `url` vers `destination` en streaming.

    Le fichier est d'abord écrit en `.part` puis renommé : un téléchargement
    interrompu ne laisse jamais un fichier incomplet à la place du bon.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".part")

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)

    tmp.replace(destination)
    return destination


class ElectionLoader:
    """
    Résultats électoraux par bureau de vote, depuis le jeu de données
    « Données des élections agrégées » de data.gouv.fr (Ministère de
    l'Intérieur, tous scrutins depuis 1999).

    On utilise la version Parquet des « Résultats généraux » (~70 Mo) :
    inscrits, abstentions, votants, blancs, nuls et exprimés par bureau.

    Exemple :
        loader = ElectionLoader()
        df = loader.load(["2022_pres_t1", "2017_pres_t1"])
    """

    # Lien permanent data.gouv.fr vers la ressource (redirige vers le fichier).
    RESOURCE_URL = (
        "https://www.data.gouv.fr/api/1/datasets/r/ff16d511-10c0-405e-9b35-511723948fce"
    )
    FILENAME = "general_results.parquet"

    COLUMNS = [
        "id_election",
        "code_departement",
        "libelle_departement",
        "code_commune",
        "libelle_commune",
        "code_bv",
        "inscrits",
        "abstentions",
        "votants",
        "exprimes",
    ]

    def __init__(self, raw_dir: str | Path = RAW_DIR / "elections", url: str = RESOURCE_URL):
        self.raw_dir = Path(raw_dir)
        self.url = url

    @property
    def path(self) -> Path:
        """Chemin de la copie locale du fichier."""
        return self.raw_dir / self.FILENAME

    def download(self, force: bool = False) -> Path:
        """
        Télécharge le fichier s'il n'est pas déjà présent localement
        (ou systématiquement si `force=True`, pour récupérer une mise à jour).
        """
        if force or not self.path.exists():
            download_file(self.url, self.path)
        return self.path

    def available_elections(self) -> list[str]:
        """Liste des identifiants d'élection présents dans le fichier."""
        table = pq.read_table(self.download(), columns=["id_election"])
        return sorted(table.column("id_election").unique().to_pylist())

    def load(self, elections: list[str] | None = None, columns: list[str] | None = None) -> pd.DataFrame:
        """
        Charge les résultats par bureau de vote.

        - `elections` : identifiants à garder (ex. ["2022_pres_t1"]) ;
          `None` charge tout (~3 millions de lignes, à éviter).
        - `columns` : colonnes à lire (par défaut `COLUMNS`).

        Le fichier est téléchargé au premier appel. Une ValueError est levée
        si une élection demandée n'existe pas dans le fichier.
        """
        path = self.download()
        filters = [("id_election", "in", list(elections))] if elections else None
        df = pd.read_parquet(path, columns=columns or self.COLUMNS, filters=filters)

        if elections:
            missing = sorted(set(elections) - set(df["id_election"].unique()))
            if missing:
                raise ValueError(
                    f"Élection(s) introuvable(s) : {missing}. "
                    "Voir ElectionLoader().available_elections()."
                )
        return df
