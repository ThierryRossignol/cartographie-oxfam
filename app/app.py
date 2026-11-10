"""
Point d'entrée principal de l'application Streamlit.

Responsabilités :
- Initialiser l'application.
- Configurer l'interface utilisateur.
- Charger les données nécessaires.
- Gérer la navigation entre les différentes pages.

Lancement, depuis la racine du projet :  make app
"""

import common  # noqa: F401  (chemins et cache)
import streamlit as st

st.set_page_config(page_title=common.TITLE, page_icon="🗺️", layout="wide")

navigation = st.navigation(
    [
        st.Page("accueil.py", title="Accueil", icon="🏠", default=True),
        st.Page("pages/1_carte.py", title="Carte", icon="🗺️", url_path="carte"),
        st.Page("pages/2_classement.py", title="Classement", icon="📋", url_path="classement"),
        st.Page("pages/3_fiche_territoire.py", title="Fiche territoire", icon="📍", url_path="fiche"),
        st.Page("pages/4_methodologie.py", title="Méthodologie", icon="📐", url_path="methodologie"),
        st.Page("pages/5_a_propos.py", title="À propos", icon="ℹ️", url_path="a-propos"),
    ]
)
navigation.run()
