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


def agreger(transactions: list[dict]) -> dict:
    """Calcule les indicateurs de la veille à partir des transactions enregistrées."""
    nb = len(transactions)
    fraudes_predites = sum(1 for t in transactions if t["predicted_fraud"])
    montant_total = sum(float(t["amt"]) for t in transactions)
    montant_fraude = sum(float(t["amt"]) for t in transactions if t["predicted_fraud"])

    # Comparaison aux labels fuités, uniquement à des fins de suivi des performances.
    vrais_positifs = sum(1 for t in transactions if t["predicted_fraud"] and t["is_fraud_actual"] == 1)
    faux_positifs = sum(1 for t in transactions if t["predicted_fraud"] and t["is_fraud_actual"] == 0)
    faux_negatifs = sum(1 for t in transactions if not t["predicted_fraud"] and t["is_fraud_actual"] == 1)
    precision = vrais_positifs / (vrais_positifs + faux_positifs) if (vrais_positifs + faux_positifs) else None
    rappel = vrais_positifs / (vrais_positifs + faux_negatifs) if (vrais_positifs + faux_negatifs) else None

    return {
        "nb": nb,
        "fraudes_predites": fraudes_predites,
        "montant_total": montant_total,
        "montant_fraude": montant_fraude,
        "precision": precision,
        "rappel": rappel,
    }


def formater_rapport(metriques: dict) -> str:
    """Met en forme le corps texte de l'e-mail récapitulatif."""
    hier = pendulum.now("UTC").subtract(days=1).format("YYYY-MM-DD")

    def pourcentage(valeur):
        return "n/a" if valeur is None else f"{valeur:.1%}"

    return (
        f"Récapitulatif des transactions du {hier} (UTC)\n\n"
        f"Transactions traitées : {metriques['nb']}\n"
        f"Fraudes prédites      : {metriques['fraudes_predites']}\n"
        f"Montant total         : {metriques['montant_total']:.2f}\n"
        f"Montant des fraudes   : {metriques['montant_fraude']:.2f}\n"
        f"Précision (vs vérité) : {pourcentage(metriques['precision'])}\n"
        f"Rappel (vs vérité)    : {pourcentage(metriques['rappel'])}\n"
    )


def envoyer_rapport() -> None:
    """Agrège la veille et envoie le récapitulatif par e-mail."""
    transactions = transactions_de_la_veille()
    corps = formater_rapport(agreger(transactions))
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
