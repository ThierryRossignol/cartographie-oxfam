# cartographie-oxfam
# IBM France – Indice de Besoin de Mobilisation

> Outil de cartographie et d'aide à la décision permettant d'identifier les territoires prioritaires pour les campagnes de mobilisation citoyenne d'Oxfam France.

---

# Présentation

Ce projet vise à développer un outil d'analyse territoriale permettant de prioriser les actions de communication et de mobilisation citoyenne à l'échelle nationale.

À partir de données publiques (élections, données socio-économiques, démographie…), l'outil calcule un **Indice de Besoin de Mobilisation (IBM)** pour chaque commune française.

L'objectif est d'aider Oxfam France à identifier les territoires où ses campagnes de mobilisation pourraient avoir le plus d'impact.

---

# Objectifs

L'outil doit permettre de :

- calculer un IBM pour chaque commune française ;
- produire des cartes interactives du territoire ;
- comparer les communes entre elles ;
- filtrer les résultats selon différents critères ;
- faciliter la préparation des campagnes de mobilisation.

À terme, l'outil pourra être utilisé pour différents scrutins (présidentielle, législatives, européennes, municipales, etc.).

---

# Fonctionnement général

Le projet suit un pipeline simple.

```text
Sources de données
        │
        ▼
Téléchargement
        │
        ▼
Prétraitement
        │
        ▼
Calcul des indicateurs
        │
        ▼
Calcul de l'IBM
        │
        ▼
Cartographie
        │
        ▼
Dashboard interactif
```

---

# Les principaux indicateurs

## IBM

L'Indice de Besoin de Mobilisation est l'indicateur principal.

Il est construit à partir de trois composantes :

- déficit démocratique ;
- vulnérabilité socio-économique ;
- public prioritaire jeunes.

---

## IED

L'Indice d'Enjeu Extrême Droite est un indicateur complémentaire.

Il ne participe pas au calcul de l'IBM mais peut être utilisé comme filtre dans les cartes afin d'adapter les stratégies de mobilisation selon les territoires.

---

# Sources de données

Toutes les données utilisées sont publiques et gratuites.

## Ministère de l'Intérieur

- résultats électoraux
- participation
- abstention

---

## INSEE

- population
- âge
- chômage
- pauvreté
- revenu médian
- diplôme

---

## data.gouv.fr

- jeux de données complémentaires
- référentiels

---

## IGN

- limites administratives
- fonds cartographiques

---

# Structure du projet

```text
cartographie-oxfam/
├── app/                  dashboard Streamlit
│   ├── app.py            point d'entrée et navigation
│   ├── accueil.py, pages/  les pages
│   ├── common.py         chargement des données, éléments communs
│   └── static/           fond de carte vide
├── config/               pondérations, scrutins, sources, périmètre, normalisation
├── data/
│   ├── raw/              fichiers téléchargés (non versionnés)
│   ├── interim/          tables intermédiaires
│   ├── processed/        table finale des indicateurs
│   └── outputs/          cartes et exports
├── notebooks/
├── src/
│   ├── data_loader.py    téléchargements (élections, INSEE, contours)
│   ├── preprocessing.py  nettoyage, recalage géographique, fusion
│   ├── indicators.py     PC, D, V, J, IBM, IED
│   ├── mapping.py        cartes
│   ├── dashboard.py      logique du dashboard
│   ├── export.py         écriture des fichiers
│   └── pipeline.py       enchaînement des étapes
├── tests/
├── Makefile
└── requirements.txt
```

---

# Architecture

Le projet est organisé autour de quatre grands modules.

## 1. Data Loader

Responsable du téléchargement des données.

Exemples :

- API des élections
- données INSEE
- données IGN

Aucune analyse n'est réalisée dans cette étape.

---

## 2. Prétraitement

Responsable de :

- nettoyer les données ;
- harmoniser les formats ;
- fusionner les bases ;
- calculer les premiers indicateurs.

---

## 3. Calcul des indicateurs

Responsable de :

- Participation Chronique Pondérée (PC)
- Vulnérabilité socio-économique (V)
- Public Prioritaire Jeunes (J)
- Indice de Besoin de Mobilisation (IBM)
- Indice d'Enjeu Extrême Droite (IED)

---

## 4. Cartographie

Responsable de :

- produire les cartes ;
- créer les exports ;
- alimenter le dashboard.

---

# Démarrage rapide

Prérequis : Python 3.11 ou plus récent, Git, une connexion internet (~600 Mo de données publiques
téléchargées au premier lancement, puis gardées dans `data/raw/`).

```bash
git clone https://github.com/ThierryRossignol/cartographie-oxfam.git
cd cartographie-oxfam
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS / Linux : source .venv/bin/activate)
python -m pip install -r requirements.txt
python -m src.pipeline all       # téléchargements + calcul de l'IBM et de l'IED (quelques minutes)
python -m src.pipeline cartes    # cartes PNG et carte interactive (facultatif)
python -m streamlit run app/app.py
```

Le dashboard s'ouvre dans le navigateur à l'adresse http://localhost:8501.
Sous macOS / Linux, les raccourcis `make install`, `make data`, `make cartes` et `make app` font la même chose.

---

# Utilisation

```bash
make install   # dépendances
make test      # tests unitaires
make data      # télécharge les données, fusionne, calcule l'IBM et l'IED (~1 min hors téléchargements)
make cartes    # produit les cartes à partir des résultats (~20 s)
make app       # lance le dashboard : http://localhost:8501
```

## Mise en ligne (Streamlit Community Cloud)

Le dashboard en ligne ne relance pas le pipeline : il lit `data/published/`
(résultats en Parquet et contours des communes, ~6,5 Mo, versionnés dans git).
Après un nouveau calcul (`make data`), mettre ce paquet à jour puis pousser :

```bash
python -m src.pipeline publier      # ou : make publier
git add data/published && git commit -m "Mise à jour des données publiées" && git push
```

Déploiement : sur https://share.streamlit.io, « Create app » → dépôt `ThierryRossignol/cartographie-oxfam`,
branche voulue, fichier principal `app/app.py`, Python 3.12 dans « Advanced settings ».
Les dépendances en ligne sont celles de `app/requirements.txt` (allégées).

## Le dashboard

| Page | Contenu |
|---|---|
| Accueil | Chiffres clés, plus grandes communes prioritaires |
| Carte | IBM ou IED commune par commune, filtre par département et « communes prioritaires », fiche au survol |
| Classement | Tri, filtres (département, taille, classe d'IED), recherche, export CSV pour Excel, comparaison de communes |
| Fiche territoire | Une commune en détail : composantes, données comparées au département et à la métropole, vote, voisines |
| Méthodologie | Formules (lues dans `config/`), sources, choix et limites |

Une fiche se partage par son adresse : `http://localhost:8501/fiche?commune=62498` (code INSEE).
Le dashboard n'appelle aucun service externe (pas de fond de carte tiers).

Fichiers produits :

| Fichier | Contenu |
|---|---|
| `data/interim/abstention_communes.csv` | Taux d'abstention A2022, A2017, A2024 par commune |
| `data/interim/rn_communes.csv` | Score du RN 2022 et progression depuis 2017 par commune |
| `data/interim/socio_communes.csv` | P, R, C, SD, Y par commune (source INSEE) |
| `data/processed/ibm_communes.csv` | Table fusionnée + PC, D, V, J, IBM, IED |
| `data/outputs/carte_ibm.png`, `carte_ied.png` | Cartes de France en quintiles |
| `data/outputs/carte_prioritaires.png` | Les 20 % de communes à l'IBM le plus élevé, selon leur IED |
| `data/outputs/carte_interactive.html` | Carte à ouvrir dans un navigateur : bascule IBM / IED, filtre « prioritaires », fiche au survol |
| `data/outputs/communes_indicateurs.geojson` | Contours + indicateurs, pour le dashboard |

Relire avec `pd.read_csv(..., dtype={"code_commune": str})` pour garder les zéros des codes INSEE.

Réglages (dossier `config/`) :

- `weights.yaml` : pondérations des indicateurs ;
- `elections.yaml` : scrutins utilisés pour l'abstention ;
- `sources.yaml` : adresses des fichiers téléchargés (millésimes, contours) ;
- `perimetre.yaml` : territoires exclus ;
- `normalisation.yaml` : écrêtage des valeurs extrêmes.

---

# Choix méthodologiques

| Variable | Source | Définition |
|---|---|---|
| A2022, A2017, A2024 | Ministère de l'Intérieur via data.gouv.fr | Abstentions / inscrits, 1er tour (présidentielles 2022 et 2017, législatives 2024) |
| P | INSEE Filosofi 2021 | Taux de pauvreté au seuil de 60 % |
| R | INSEE Filosofi 2021 | Niveau de vie médian (inversé : faible revenu = besoin fort) |
| C | INSEE Recensement 2023 | Chômeurs / actifs de 15-64 ans (au sens du recensement) |
| SD | INSEE Recensement 2023 | Part des 15 ans ou plus non scolarisés sans diplôme ou avec le seul CEP |
| Y | INSEE Recensement 2023 | Part des 19-25 ans dans la population |
| RN | Ministère de l'Intérieur via data.gouv.fr | Score de Marine Le Pen, 1er tour de la présidentielle 2022, en % des exprimés |
| delta_RN | Ministère de l'Intérieur via data.gouv.fr | Score 2022 − score 2017 (1er tour), en points |

- **Géographie** : toutes les données sont ramenées aux communes au 1er janvier 2025 grâce à la table de passage de l'INSEE (communes fusionnées regroupées, communes scindées héritant du taux de l'ancienne commune). Paris, Lyon et Marseille sont traitées comme une seule commune.
- **Périmètre** : France métropolitaine. Les outre-mer sont exclus : leur abstention (45 à 85 % en médiane, contre 20 % en métropole) écraserait l'échelle.
- **Secret statistique** : le taux de pauvreté n'est publié que pour ~4 300 communes (les plus grandes) et le niveau de vie médian pour ~31 000. Pour les autres, on utilise la valeur de l'intercommunalité (colonnes `P_source` et `R_source`).
- **Normalisation** : chaque variable est écrêtée entre le 1er et le 99e centile, puis ramenée entre 0 et 1. Les scores sont relatifs : 1 = commune au plus fort besoin de la métropole.
- **IED** : le candidat retenu est réglable dans `config/elections.yaml` (`ied.candidats`). Les exprimés sont recalculés comme la somme des voix de tous les candidats, la colonne de la source étant parfois erronée.
- **Communes sans IED** (25) : en plus des communes sans IBM, une vingtaine de communes dont les voix par candidat valent 0 dans le fichier agrégé de data.gouv.fr pour 2017 ou 2022 (donnée manquante à la source).
- **Cartes** : chaque indicateur est découpé en 5 classes d'effectifs égaux (quintiles), lues comme « les 20 % de communes les plus… ». Une teinte par indicateur (bleu pour l'IBM, orange pour l'IED), du clair au foncé ; gris pour les données manquantes. Contours IGN ADMIN EXPRESS simplifiés par Etalab (géographie 2025).
- **Communes sans IBM** (10) : villages de la Meuse inhabités depuis 1916, îles sans intercommunalité, très petites communes.

---

# Philosophie du projet

Le projet suit quelques principes simples.

## Les données avant le code

Les données constituent le cœur du projet.

Le développement logiciel vient ensuite.

---

## Une seule source de vérité

Chaque donnée est téléchargée une seule fois puis stockée localement.

Tous les calculs utilisent ensuite cette copie locale.

---

## Un code modulaire

Chaque module possède une responsabilité unique.

Exemple :

- téléchargement
- nettoyage
- calcul
- cartographie

ne doivent jamais être mélangés.

---

## Reproductibilité

Le projet doit pouvoir être recréé automatiquement sur une nouvelle machine.

L'objectif est qu'un utilisateur puisse lancer quelques commandes et obtenir exactement les mêmes résultats.

---

# Feuille de route

## Sprint 1 ✅

- Architecture du projet
- Documentation
- Configuration

---

## Sprint 2 ✅

- Connecteur Élections
- Téléchargement automatique
- Agrégation par commune

---

## Sprint 3 ✅

- Connecteurs INSEE

---

## Sprint 4 ✅

- Fusion des données

---

## Sprint 5 ✅

- Calcul de l'IBM et de l'IED

---

## Sprint 6 ✅

- Cartographie

---

## Sprint 7 ✅

- Dashboard interactif

---

# Technologies

Le projet est développé principalement en Python.

Bibliothèques envisagées :

- pandas
- geopandas
- numpy
- matplotlib
- plotly
- folium
- streamlit
- requests
- scikit-learn
- jupyter

---

# Licence

À définir.

---

# Auteur

Projet initié dans le cadre des activités de mobilisation citoyenne d'Oxfam France.

Ce dépôt constitue un prototype technique destiné à explorer l'utilisation de la data science et de la cartographie pour soutenir les campagnes de mobilisation et d'engagement citoyen.