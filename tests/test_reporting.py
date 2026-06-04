"""Tests de l'agrégation et de la mise en forme du rapport (src/reporting.py).

Ne dépend d'aucune ressource externe : les transactions sont synthétiques.
"""
from src.reporting import agreger_veille, construire_corps_rapport


def transactions_synthetiques() -> list[dict]:
    """Quatre transactions : un vrai positif, un faux positif, un faux négatif, un vrai négatif."""
    return [
        {"amt": 100.0, "predicted_fraud": True, "is_fraud_actual": 1},
        {"amt": 50.0, "predicted_fraud": True, "is_fraud_actual": 0},
        {"amt": 30.0, "predicted_fraud": False, "is_fraud_actual": 1},
        {"amt": 20.0, "predicted_fraud": False, "is_fraud_actual": 0},
    ]


def test_agreger_veille_comptes_montants_et_taux():
    """Vérifie comptes, montants et précision/rappel sur un cas connu."""
    metriques = agreger_veille(transactions_synthetiques())
    assert metriques["nb"] == 4
    assert metriques["fraudes_predites"] == 2
    assert metriques["montant_total"] == 200.0
    assert metriques["montant_fraude"] == 150.0
    assert metriques["precision"] == 0.5
    assert metriques["rappel"] == 0.5


def test_agreger_veille_liste_vide():
    """Sur une liste vide, precision et rappel valent None (pas de division par zéro)."""
    metriques = agreger_veille([])
    assert metriques["nb"] == 0
    assert metriques["fraudes_predites"] == 0
    assert metriques["montant_total"] == 0
    assert metriques["montant_fraude"] == 0
    assert metriques["precision"] is None
    assert metriques["rappel"] is None


def test_construire_corps_rapport_liste_vide():
    """Le corps du rapport gère la liste vide et affiche n/a sans erreur."""
    corps = construire_corps_rapport([])
    assert "Transactions traitées : 0" in corps
    assert "n/a" in corps
