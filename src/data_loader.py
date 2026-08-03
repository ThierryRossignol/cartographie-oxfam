"""
Chargement des données publiques du projet Cartographie Oxfam.

Ce module contient les classes permettant de récupérer les données
depuis les différentes sources (API, CSV locaux...).
"""

from io import StringIO

import pandas as pd
import requests


class ElectionLoader:
    """
    Charge les données électorales depuis l'API Data.gouv.
    """

    API_URL = (
        "https://www.data.gouv.fr/api/resources/"
        "b8703c69-a18f-46ab-9e7f-3a8368dcb891/data/csv/"
    )

    def load(self) -> pd.DataFrame:
        """
        Télécharge les données électorales et les retourne sous forme
        d'un DataFrame Pandas.
        """

        response = requests.get(self.API_URL, timeout=60)

        response.raise_for_status()

        df = pd.read_csv(
            StringIO(response.text),
            sep=";",
            encoding="utf-8",
        )

        return df