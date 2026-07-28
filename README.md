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
ibm-france/

├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│
├── src/
│   ├── data_loader/
│   ├── preprocessing/
│   ├── indicators/
│   ├── mapping/
│   └── utils/
│
├── config/
│
├── docs/
│
├── tests/
│
├── README.md
│
├── requirements.txt
│
└── .gitignore
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

## Sprint 1

- Architecture du projet
- Documentation
- Configuration

---

## Sprint 2

- Connecteur Élections
- Téléchargement automatique
- Agrégation par commune

---

## Sprint 3

- Connecteurs INSEE

---

## Sprint 4

- Fusion des données

---

## Sprint 5

- Calcul de l'IBM

---

## Sprint 6

- Cartographie

---

## Sprint 7

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