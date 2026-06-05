"""DAG de démonstration à déclenchement manuel.

Sert à filmer la chaîne d'alerte de bout en bout sans attendre qu'une vraie fraude
tombe sur l'API. Sélectionne dans le CSV une transaction réellement frauduleuse que
le modèle prédit effectivement comme fraude (probabilité au-dessus du seuil), puis la
fait passer dans tout le pipeline : prédiction, écriture dans Neon et envoi de l'alerte.

La transaction injectée est datée de l'instant courant et reçoit un identifiant
unique, afin d'apparaître immédiatement comme une fraude fraîche sur le dashboard.
"""
import uuid
from datetime import datetime, timezone

import pandas as pd
import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

from src import config
from src.db import construire_enregistrement, inserer_transaction
from src.notifications import envoyer_email
from src.predictor import predire
from src.reporting import construire_corps_alerte


def selectionner_fraude_predite() -> tuple[pd.DataFrame, float, bool]:
    """Renvoie la première fraude du CSV que le modèle classe au-dessus du seuil.

    Parcourt les transactions réellement frauduleuses jusqu'à en trouver une que
    `predire` confirme, ce qui garantit le départ d'une alerte pendant la démo.
    """
    chemin_csv = config.exiger("CSV_PATH")
    fraudes = pd.read_csv(chemin_csv)
    fraudes = fraudes[fraudes["is_fraud"] == 1]

    for index in fraudes.index:
        df = fraudes.loc[[index]]
        probabilite, prediction = predire(df)
        if prediction:
            return df, probabilite, prediction

    raise RuntimeError(
        "Aucune fraude du CSV n'est prédite au-dessus du seuil ; vérifiez le modèle."
    )


def lancer_demo() -> None:
    """Injecte une fraude de démonstration datée de l'instant courant, puis alerte.

    La transaction reprend les caractéristiques d'une vraie fraude du CSV (marchand,
    montant, catégorie, probabilité du modèle), mais reçoit un identifiant propre et
    un `transaction_time` fixé à maintenant. Chaque déclenchement crée donc une ligne
    fraîche, visible aussitôt en tête du dashboard, sans collision avec le jeu de seed
    ni avec une exécution précédente.
    """
    df, probabilite, prediction = selectionner_fraude_predite()
    is_fraud_actual = int(df.iloc[0]["is_fraud"])
    enregistrement = construire_enregistrement(df, probabilite, prediction, is_fraud_actual)

    enregistrement["transaction_time"] = datetime.now(timezone.utc).replace(tzinfo=None)
    enregistrement["trans_num"] = f"demo-{uuid.uuid4().hex[:12]}"

    inserer_transaction(enregistrement)

    sujet, corps = construire_corps_alerte(enregistrement)
    envoyer_email(sujet, corps)


with DAG(
    dag_id="demo_alerte_fraude",
    description="Déclenchement manuel : envoie une alerte de fraude pour la démo.",
    schedule=None,
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["fraude", "demo"],
) as dag:
    PythonOperator(
        task_id="lancer_demo",
        python_callable=lancer_demo,
    )
