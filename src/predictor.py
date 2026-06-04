"""Chargement du modèle et prédiction au serving.

Le pipeline sérialisé est chargé une seule fois, à la première prédiction, puis
mis en cache au niveau module : un worker Airflow qui enchaîne les exécutions ne
relit pas le `.joblib` à chaque minute.

Le pipeline part des colonnes brutes de la transaction et intègre tout le
préprocessing : `predire` lui passe directement le DataFrame issu de l'API.
"""
from pathlib import Path

import joblib
import pandas as pd

from src import config

CHEMIN_MODELE = Path("models/fraud_pipeline.joblib")

# Cache module : le pipeline n'est chargé qu'une fois par processus.
_pipeline = None


def _charger_pipeline():
    """Charge le pipeline depuis le `.joblib`, ou le renvoie depuis le cache."""
    global _pipeline
    if _pipeline is None:
        if not CHEMIN_MODELE.exists():
            raise FileNotFoundError(
                f"Modèle introuvable : {CHEMIN_MODELE}. Lancez d'abord `python -m src.train`."
            )
        _pipeline = joblib.load(CHEMIN_MODELE)
    return _pipeline


def predire(df_transaction: pd.DataFrame) -> tuple[float, bool]:
    """Prédit la probabilité de fraude d'une transaction et la décision associée.

    `df_transaction` est un DataFrame d'une ligne aux colonnes brutes de l'API. La
    décision booléenne applique le seuil `config.FRAUD_THRESHOLD`. Renvoie le couple
    (probabilité, prédiction booléenne).
    """
    pipeline = _charger_pipeline()
    probabilite = float(pipeline.predict_proba(df_transaction)[:, 1][0])
    prediction = probabilite >= config.FRAUD_THRESHOLD
    return probabilite, prediction
