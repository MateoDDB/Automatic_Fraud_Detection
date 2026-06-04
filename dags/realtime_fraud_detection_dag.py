"""DAG temps réel : score une transaction de l'API chaque minute.

Flux d'une exécution : récupérer une transaction, la scorer avec le modèle, écrire
le résultat dans Neon, puis envoyer une alerte e-mail si la transaction est prédite
frauduleuse. Le planning d'une exécution par minute épouse la cadence de l'API
(une transaction, rafraîchie à la minute) ; chaque exécution est indépendante
(catchup désactivé), donc un appel API en échec n'affecte que sa propre minute.
"""
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

from src.api_client import recuperer_transaction
from src.db import construire_enregistrement, inserer_transaction
from src.notifications import envoyer_email
from src.predictor import predire
from src.reporting import construire_corps_alerte


def traiter_transaction() -> None:
    """Récupère une transaction, la score, l'enregistre et alerte si fraude."""
    df, is_fraud_actual = recuperer_transaction()
    probabilite, prediction = predire(df)
    enregistrement = construire_enregistrement(df, probabilite, prediction, is_fraud_actual)
    inserer_transaction(enregistrement)

    if prediction:
        sujet, corps = construire_corps_alerte(enregistrement)
        envoyer_email(sujet, corps)


default_args = {
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
}

with DAG(
    dag_id="realtime_fraud_detection",
    description="Score chaque minute une transaction de l'API et alerte sur fraude.",
    schedule="* * * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["fraude", "temps-reel"],
) as dag:
    PythonOperator(
        task_id="traiter_transaction",
        python_callable=traiter_transaction,
    )
