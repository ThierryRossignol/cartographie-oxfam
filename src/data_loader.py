"""
Chargement des données publiques utilisées par le projet IBM France.

Ce module centralise les fonctions permettant de récupérer les données
depuis les différentes sources (API ou fichiers locaux).

Pour le moment, seule l'API des élections est prévue.
"""


class ElectionLoader:
    """
    Charge les données électorales depuis l'API nationale.
    """

    def __init__(self):
        """
        Initialise le chargeur de données électorales.
        """
        self.api_url = (
            "https://www.data.gouv.fr/api/resources/"
            "b8703c69-a18f-46ab-9e7f-3a8368dcb891/data/csv/"
        )

    def load(self):
        """
        Charge les données électorales.

        Cette méthode sera implémentée dans la prochaine étape.
        """
        raise NotImplementedError("Méthode non encore implémentée.")