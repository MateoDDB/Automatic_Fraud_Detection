"""Construction des contenus d'e-mails : alerte temps réel et rapport quotidien.

Centralise la mise en forme des notifications afin que les DAGs restent de simples
orchestrateurs et qu'aucun DAG n'ait besoin d'en importer un autre. N'utilise que la
bibliothèque standard, donc importable et testable hors d'Airflow.
"""
from datetime import datetime, timedelta, timezone


def construire_corps_alerte(enregistrement: dict) -> tuple[str, str]:
    """Construit le sujet et le corps de l'e-mail d'alerte d'une fraude."""
    sujet = f"Alerte fraude — transaction {enregistrement['trans_num']}"
    corps = (
        "Une transaction vient d'être classée comme frauduleuse.\n\n"
        f"Identifiant : {enregistrement['trans_num']}\n"
        f"Marchand    : {enregistrement['merchant']} ({enregistrement['category']})\n"
        f"Montant     : {enregistrement['amt']:.2f}\n"
        f"Probabilité : {enregistrement['fraud_probability']:.3f}\n"
        f"Horodatage  : {enregistrement['transaction_time']} UTC\n"
    )
    return sujet, corps


def agreger_veille(transactions: list[dict]) -> dict:
    """Calcule les indicateurs de la veille à partir des transactions enregistrées.

    Compare les prédictions à la vérité terrain (`is_fraud_actual`, label fuité par
    l'API) uniquement pour reporter précision et rappel réels.
    """
    nb = len(transactions)
    fraudes_predites = sum(1 for t in transactions if t["predicted_fraud"])
    montant_total = sum(float(t["amt"]) for t in transactions)
    montant_fraude = sum(float(t["amt"]) for t in transactions if t["predicted_fraud"])

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


def construire_corps_rapport(transactions: list[dict]) -> str:
    """Met en forme le corps texte de l'e-mail récapitulatif de la veille."""
    metriques = agreger_veille(transactions)
    hier = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

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
