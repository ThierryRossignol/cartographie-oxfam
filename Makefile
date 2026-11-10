# Commandes usuelles du projet Cartographie Oxfam
PYTHON ?= python3

.PHONY: help install test data elections app notebooks clean

help:  ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install:  ## Installe les dépendances
	$(PYTHON) -m pip install -r requirements.txt

test:  ## Lance les tests unitaires
	$(PYTHON) -m pytest -q

data:  ## Pipeline complet : téléchargements, fusion, calcul de l'IBM
	$(PYTHON) -m src.pipeline all

elections:  ## Abstention par commune uniquement
	$(PYTHON) -m src.pipeline elections

app:  ## Lance le dashboard Streamlit
	$(PYTHON) -m streamlit run app/app.py

notebooks:  ## Ouvre Jupyter Lab dans le dossier notebooks
	$(PYTHON) -m jupyter lab notebooks/

clean:  ## Supprime les caches Python
	find . -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
