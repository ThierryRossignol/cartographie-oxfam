"""
Module de chargement des données.

Responsabilités :
- Télécharger les données depuis les différentes sources (API, fichiers, etc.).
- Gérer le cache local des données téléchargées.
- Charger les jeux de données bruts dans des DataFrames pandas.
- Vérifier l'intégrité des données téléchargées.

Sources de données prévues :
- API des résultats électoraux (data.gouv.fr)
- INSEE
- IGN
- Autres jeux de données publics

Ce module ne réalise aucun nettoyage ni transformation des données.
"""