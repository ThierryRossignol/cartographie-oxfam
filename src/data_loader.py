"""
Chargement des données publiques du projet Cartographie Oxfam.

Ce module contient les classes permettant de récupérer les données
depuis les différentes sources (data.gouv.fr, INSEE).

Principe « une seule source de vérité » : chaque fichier est téléchargé une
seule fois dans data/raw/, puis toutes les lectures se font sur cette copie
locale. Aucune analyse n'est réalisée ici : les fonctions renvoient les
données brutes, simplement filtrées.

Les adresses des fichiers sont dans config/sources.yaml.
"""

from __future__ import annotations

import gzip
import io
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pyarrow.parquet as pq
import requests

from src.utils import ROOT_DIR, load_config

RAW_DIR = ROOT_DIR / "data" / "raw"


# ----------------------------------------------------------------------------
# Téléchargement
# ----------------------------------------------------------------------------


def check_file(path: Path, suffix: str | None = None) -> None:
    """
    Vérifie qu'un fichier téléchargé est lisible (Parquet ou ZIP).

    Certains serveurs coupent les gros téléchargements sans erreur : sans ce
    contrôle, on garderait en cache un fichier tronqué. `suffix` permet de
    préciser le format quand le fichier porte une extension temporaire.
    """
    suffix = (suffix or path.suffix).lower()
    if suffix == ".parquet":
        try:
            pq.ParquetFile(path)
        except Exception as e:
            raise OSError(f"Fichier Parquet illisible ou incomplet : {path}") from e
    elif suffix == ".zip" and not zipfile.is_zipfile(path):
        raise OSError(f"Fichier ZIP illisible ou incomplet : {path}")
    elif suffix == ".gz":
        try:
            with gzip.open(path) as f:
                while f.read(1 << 20):
                    pass
        except (OSError, EOFError) as e:
            raise OSError(f"Fichier gzip illisible ou incomplet : {path}") from e


def download_file(url: str, destination: Path, timeout: int = 120, retries: int = 4) -> Path:
    """
    Télécharge `url` vers `destination` en streaming, avec contrôle et reprises.

    Le fichier est d'abord écrit en `.part`, vérifié, puis renommé : un
    téléchargement interrompu ne laisse jamais un fichier incomplet à la
    place du bon. En cas d'échec, nouvel essai après 1, 2, 4… secondes.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".part")

    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout) as response:
                response.raise_for_status()
                expected = int(response.headers.get("Content-Length", 0))
                received = 0
                with open(tmp, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        received += len(chunk)
            if expected and received != expected:
                raise OSError(f"Téléchargement incomplet ({received}/{expected} octets)")
            check_file(tmp, destination.suffix)
            tmp.replace(destination)
            return destination
        except (requests.RequestException, OSError):
            tmp.unlink(missing_ok=True)
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)

    raise AssertionError("inatteignable")


class CachedSource:
    """Un fichier distant, téléchargé une fois dans `raw_dir`."""

    def __init__(self, url: str, raw_dir: str | Path):
        self.url = url
        self.raw_dir = Path(raw_dir)

    @property
    def path(self) -> Path:
        """Chemin de la copie locale (nom de fichier repris de l'URL)."""
        return self.raw_dir / Path(urlparse(self.url).path).name

    def download(self, force: bool = False) -> Path:
        """
        Télécharge le fichier s'il n'est pas déjà présent localement
        (ou systématiquement si `force=True`, pour récupérer une mise à jour).
        """
        if force or not self.path.exists():
            download_file(self.url, self.path)
        return self.path


# ----------------------------------------------------------------------------
# Élections
# ----------------------------------------------------------------------------


class ElectionLoader(CachedSource):
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

    FILENAME = "general_results.parquet"
    CANDIDATES_FILENAME = "candidats_results.parquet"

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

    CANDIDATE_COLUMNS = [
        "id_election",
        "code_departement",
        "code_commune",
        "code_bv",
        "no_panneau",
        "nom",
        "prenom",
        "voix",
    ]

    def __init__(
        self,
        raw_dir: str | Path = RAW_DIR / "elections",
        url: str | None = None,
        candidates_url: str | None = None,
    ):
        sources = load_config("sources")["elections"]
        super().__init__(url or sources["resultats_generaux"], raw_dir)
        self.candidates_url = candidates_url or sources["resultats_candidats"]

    @property
    def candidates_path(self) -> Path:
        """Chemin de la copie locale des résultats par candidat."""
        return self.raw_dir / self.CANDIDATES_FILENAME

    @property
    def path(self) -> Path:
        # Le lien data.gouv.fr ne contient pas le nom du fichier.
        return self.raw_dir / self.FILENAME

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

    def load_candidates(self, elections: list[str], names: list[str] | None = None) -> pd.DataFrame:
        """
        Voix par candidat et par bureau de vote.

        - `elections` : identifiants d'élection à garder.
        - `names` : noms de candidats à garder (ex. ["LE PEN"]), en
          majuscules comme dans le fichier ; `None` garde tout le monde.

        Le fichier (~160 Mo) est téléchargé au premier appel.
        """
        path = self.candidates_path
        if not path.exists():
            download_file(self.candidates_url, path)

        filters = [("id_election", "in", list(elections))]
        if names:
            filters.append(("nom", "in", list(names)))
        df = pd.read_parquet(path, columns=self.CANDIDATE_COLUMNS, filters=filters)

        missing_elections = sorted(set(elections) - set(df["id_election"]))
        missing_names = sorted(set(names or []) - set(df["nom"]))
        if missing_elections or missing_names:
            raise ValueError(
                "Introuvable dans les résultats par candidat "
                f"(élections : {missing_elections or '-'} ; candidats : {missing_names or '-'})"
            )
        return df


# ----------------------------------------------------------------------------
# INSEE
# ----------------------------------------------------------------------------


def read_insee_long(path: Path, year: int | None = None, **dims: str | list[str]) -> pd.DataFrame:
    """
    Lit un fichier INSEE au format « long » (une ligne par mesure : GEO,
    GEO_OBJECT, dimensions…, TIME_PERIOD, OBS_VALUE).

    - `year` : ne garde que ce millésime (TIME_PERIOD est une date ou une
      chaîne selon les fichiers, on compare donc l'année).
    - `dims` : filtres sur les dimensions, ex. GEO_OBJECT=["COM", "EPCI"],
      SEX="_T". Appliqués à la lecture pour limiter la mémoire.
    """
    filters = [
        (col, "in", list(v) if isinstance(v, (list, tuple, set)) else [v])
        for col, v in dims.items()
    ]
    df = pd.read_parquet(path, filters=filters or None)
    if year is not None:
        df = df[df["TIME_PERIOD"].astype(str).str[:4] == str(year)]
    return df.reset_index(drop=True)


def read_insee_xlsx(zip_path: Path, sheet: str) -> pd.DataFrame:
    """
    Lit une feuille d'un fichier Excel INSEE contenu dans un ZIP.

    Ces fichiers ont 5 lignes d'en-tête (titre, source…) puis les noms
    courts des colonnes (CODGEO, LIBGEO…). Toutes les colonnes sont lues
    comme du texte pour garder les zéros initiaux des codes.
    """
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        data = io.BytesIO(z.read(name))
    return pd.read_excel(data, sheet_name=sheet, skiprows=5, dtype=str, engine="calamine")


class InseeLoader:
    """
    Fichiers INSEE utilisés par le projet (adresses dans config/sources.yaml).

    Chaque méthode télécharge le fichier si besoin puis renvoie les données
    brutes au niveau commune (et EPCI quand c'est utile), sans calcul.
    """

    def __init__(self, raw_dir: str | Path = RAW_DIR / "insee", urls: dict[str, str] | None = None):
        self.raw_dir = Path(raw_dir)
        self.urls = urls or load_config("sources")["insee"]

    def source(self, key: str) -> CachedSource:
        return CachedSource(self.urls[key], self.raw_dir)

    def download_all(self, force: bool = False) -> list[Path]:
        return [self.source(k).download(force) for k in self.urls]

    def filosofi(self, measures: list[str] = ("PR_MD60", "MED_SL")) -> pd.DataFrame:
        """
        Filosofi (revenus et pauvreté), communes et EPCI.

        Mesures utiles : PR_MD60 = taux de pauvreté (%), MED_SL = niveau de
        vie médian (€). Valeur manquante = donnée soumise au secret
        statistique (trop peu de ménages).
        """
        path = self.source("filosofi").download()
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith("_data.csv"))
            with z.open(name) as f:
                df = pd.read_csv(
                    f,
                    sep=";",
                    dtype={"GEO": str},
                    usecols=["GEO", "GEO_OBJECT", "FILOSOFI_MEASURE", "TIME_PERIOD", "OBS_VALUE"],
                )
        keep = df["GEO_OBJECT"].isin(["COM", "EPCI"]) & df["FILOSOFI_MEASURE"].isin(measures)
        return df[keep].reset_index(drop=True)

    def population_by_age(self, year: int = 2023) -> pd.DataFrame:
        """Population par année d'âge (AGE = Y0…Y99, Y_GE100, _T), communes."""
        return read_insee_long(
            self.source("population_age").download(), year=year, GEO_OBJECT="COM", SEX="_T"
        )

    def diplomas(self, year: int = 2023) -> pd.DataFrame:
        """
        Population non scolarisée de 15 ans ou plus par diplôme le plus élevé
        (EDUC : 001T100_RP = aucun diplôme ou CEP, …, _T = total), communes.
        """
        return read_insee_long(
            self.source("diplomes").download(), year=year, GEO_OBJECT="COM", SEX="_T", AGE="Y_GE15"
        )

    def employment(self, year: int = 2023) -> pd.DataFrame:
        """
        Population de 15-64 ans par statut d'emploi (EMPSTA_ENQ : 1 = actif
        occupé, 2 = chômeur, 1T2 = actifs…), communes.
        """
        return read_insee_long(
            self.source("emploi").download(),
            year=year,
            GEO_OBJECT="COM",
            SEX="_T",
            AGE="Y15T64",
            EDUC="_T",
            EMPSTA_ENQ=["1", "2", "1T2"],
        )

    def commune_passage(self, cog_year: int | None = None) -> pd.DataFrame:
        """
        Table de passage : CODGEO_INI (tout code ayant existé depuis 2003)
        → CODGEO_<année> (code actuel). Une commune scindée a plusieurs lignes.
        """
        cog_year = cog_year or load_config("sources")["cog_annee"]
        df = read_insee_xlsx(self.source("table_passage").download(), "Table de passage")
        return df.rename(columns={f"CODGEO_{cog_year}": "CODGEO_COG"})[["CODGEO_INI", "CODGEO_COG"]]

    def commune_membership(self) -> pd.DataFrame:
        """Communes actuelles : CODGEO, LIBGEO, DEP, REG, EPCI…"""
        return read_insee_xlsx(self.source("appartenance").download(), "COM")


# ----------------------------------------------------------------------------
# IGN — contours des communes
# ----------------------------------------------------------------------------


class ContoursLoader:
    """
    Contours des communes (adresses dans config/sources.yaml, section `ign`).

    Exemple :
        communes = ContoursLoader().communes()          # GeoDataFrame, WGS84
    """

    def __init__(self, raw_dir: str | Path = RAW_DIR / "ign", urls: dict[str, str] | None = None):
        self.raw_dir = Path(raw_dir)
        self.urls = urls or load_config("sources")["ign"]

    def communes(self, resolution: str = "1000m"):
        """
        Contours des communes : colonnes code, nom, departement, region,
        epci, geometry (WGS84). `resolution` : "1000m" ou "100m".
        """
        import geopandas as gpd  # import local : dépendance lourde

        path = CachedSource(self.urls[f"communes_{resolution}"], self.raw_dir).download()
        # Décompression en Python plutôt que via le préfixe GDAL /vsigzip/,
        # peu fiable avec les chemins Windows (C:\...).
        with gzip.open(path, "rb") as f:
            return gpd.read_file(io.BytesIO(f.read()))
