"""DAG quotidien : récapitulatif des transactions de la veille.

Chaque matin à 8h, agrège les transactions du jour calendaire UTC précédent
(volume, fraudes prédites, montants) et compare les prédictions à la vérité terrain
(`is_fraud_actual`, le label que l'API laisse fuiter) pour reporter précision et
rappel réels, puis envoie le tout par e-mail.
"""
import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

from src.db import transactions_de_la_veille
from src.notifications import envoyer_email
from src.reporting import construire_corps_rapport


def envoyer_rapport() -> None:
    """Agrège la veille et envoie le récapitulatif par e-mail."""
    transactions = transactions_de_la_veille()
    corps = construire_corps_rapport(transactions)
    envoyer_email("Rapport quotidien de détection de fraude", corps)


with DAG(
    dag_id="daily_fraud_report",
    description="Envoie chaque matin le récapitulatif des fraudes de la veille.",
    schedule="0 8 * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["fraude", "rapport"],
) as dag:
    PythonOperator(
        task_id="envoyer_rapport",
        python_callable=envoyer_rapport,
    )
