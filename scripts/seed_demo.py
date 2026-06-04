"""Alimente la fenêtre « hier » avec un petit jeu de démonstration.

Sélectionne quelques transactions du CSV (majorité de normales, quelques fraudes
détectées), les fait passer dans le vrai pipeline (predire + construire_enregistrement),
répartit leur transaction_time sur la journée d'hier (UTC) et les insère dans Neon.
Sert uniquement à rendre le rapport quotidien démonstratif : les prédictions et le
label restent ceux du pipeline, seul l'horodatage est replacé dans la veille.

Usage : python -m scripts.seed_demo
"""
from datetime import datetime, timedelta, timezone

import pandas as pd

from src import config
from src.db import construire_enregistrement, inserer_transaction
from src.predictor import predire

NB_NORMALES = 45
NB_FRAUDES = 15


def selectionner(df: pd.DataFrame) -> pd.DataFrame:
    """Compose un échantillon de normales et de fraudes, sans présélection.

    Les fraudes ne sont pas filtrées sur la prédiction : c'est le pipeline qui
    tranche au moment de l'insertion, ce qui laisse apparaître de vrais ratés
    (rappel réel) et d'éventuels faux positifs dans le rapport.
    """
    normales = df[df["is_fraud"] == 0].head(NB_NORMALES)
    fraudes = df[df["is_fraud"] == 1].head(NB_FRAUDES)
    return pd.concat([normales, fraudes])


def horodatage_hier(rang: int, total: int) -> datetime:
    """Renvoie un instant naïf UTC de la journée d'hier, réparti selon le rang."""
    hier = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    heure = int(rang * 23 / max(total - 1, 1))
    minute = (rang * 17) % 60
    return datetime(hier.year, hier.month, hier.day, heure, minute)


def main() -> None:
    """Insère l'échantillon de démonstration daté de la veille."""
    echantillon = selectionner(pd.read_csv(config.exiger("CSV_PATH")))
    total = len(echantillon)

    for rang in range(total):
        df = echantillon.iloc[[rang]]
        probabilite, prediction = predire(df)
        label = int(df.iloc[0]["is_fraud"])
        enregistrement = construire_enregistrement(df, probabilite, prediction, label)
        enregistrement["transaction_time"] = horodatage_hier(rang, total)
        inserer_transaction(enregistrement)

    print(f"{total} transactions de démonstration insérées sur la journée d'hier (UTC).")


if __name__ == "__main__":
    main()
