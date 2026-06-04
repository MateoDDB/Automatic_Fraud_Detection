"""Entraînement du pipeline de détection de fraude.

Charge le CSV local, assemble un Pipeline scikit-learn qui intègre le feature
engineering, l'encodage et le modèle, évalue les performances sur un jeu de test
stratifié, puis sérialise le pipeline complet dans models/fraud_pipeline.joblib.

Le pipeline sérialisé part des colonnes brutes (CSV ou API) et va jusqu'à la
prédiction : aucune transformation manuelle n'est dupliquée au serving.

Usage : python -m src.train
"""
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

from src import config
from src.features import COLONNES_CATEGORIELLES, COLONNES_NUMERIQUES, construire_features

CHEMIN_MODELE = Path("models/fraud_pipeline.joblib")

# Colonnes brutes lues dans le CSV : les variables nécessaires au feature
# engineering, l'horodatage d'entraînement et le label.
COLONNES_BRUTES = [
    "amt",
    "category",
    "gender",
    "city_pop",
    "dob",
    "lat",
    "long",
    "merch_lat",
    "merch_long",
]
COLONNE_HORODATAGE_CSV = "trans_date_trans_time"
COLONNE_LABEL = "is_fraud"

# Seuils de décision comparés : le seuil de production et une variante plus basse
# pour illustrer le compromis précision/rappel.
SEUILS_A_EVALUER = sorted({config.FRAUD_THRESHOLD, 0.3}, reverse=True)


def charger_donnees(chemin_csv: str) -> tuple[pd.DataFrame, pd.Series]:
    """Charge le CSV d'entraînement et renvoie le couple (X brut, y).

    Ne conserve que les colonnes utiles et écarte les lignes incomplètes. X garde
    les colonnes brutes (y compris l'horodatage), car le feature engineering est
    réalisé à l'intérieur du pipeline.
    """
    df = pd.read_csv(chemin_csv)
    colonnes_requises = COLONNES_BRUTES + [COLONNE_HORODATAGE_CSV, COLONNE_LABEL]
    df = df[colonnes_requises].dropna()
    X = df.drop(columns=[COLONNE_LABEL])
    y = df[COLONNE_LABEL].astype(int)
    return X, y


def construire_pipeline() -> Pipeline:
    """Assemble le pipeline complet : features -> encodage -> Random Forest.

    Le FunctionTransformer applique construire_features ; le ColumnTransformer
    encode les variables catégorielles (one-hot) et laisse passer les numériques.
    """
    encodeur = ColumnTransformer(
        transformers=[
            ("categoriel", OneHotEncoder(handle_unknown="ignore"), COLONNES_CATEGORIELLES),
            ("numerique", "passthrough", COLONNES_NUMERIQUES),
        ]
    )
    return Pipeline(
        steps=[
            ("features", FunctionTransformer(construire_features, validate=False)),
            ("encodage", encodeur),
            (
                "modele",
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ]
    )


def afficher_evaluation(y_test: pd.Series, probabilites, seuil: float) -> None:
    """Affiche précision, rappel, F1 et matrice de confusion pour un seuil donné."""
    predictions = (probabilites >= seuil).astype(int)
    precision = precision_score(y_test, predictions, zero_division=0)
    rappel = recall_score(y_test, predictions, zero_division=0)
    f1 = f1_score(y_test, predictions, zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y_test, predictions).ravel()

    print(f"\nSeuil = {seuil:.2f}")
    print(f"  Précision : {precision:.3f}")
    print(f"  Rappel    : {rappel:.3f}")
    print(f"  F1        : {f1:.3f}")
    print(f"  Confusion : TN={tn}  FP={fp}  FN={fn}  TP={tp}")


def main() -> None:
    """Entraîne, évalue et sérialise le pipeline de détection de fraude."""
    chemin_csv = config.exiger("CSV_PATH")
    print(f"Chargement du CSV : {chemin_csv}")
    X, y = charger_donnees(chemin_csv)
    print(f"{len(X)} transactions, {int(y.sum())} fraudes ({y.mean():.3%}).")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    pipeline = construire_pipeline()
    print("Entraînement du Random Forest en cours...")
    pipeline.fit(X_train, y_train)

    # Métriques indépendantes du seuil, à privilégier sur données déséquilibrées.
    probabilites = pipeline.predict_proba(X_test)[:, 1]
    print("\nMétriques globales (jeu de test)")
    print(f"  ROC-AUC : {roc_auc_score(y_test, probabilites):.3f}")
    print(f"  PR-AUC  : {average_precision_score(y_test, probabilites):.3f}")

    for seuil in SEUILS_A_EVALUER:
        afficher_evaluation(y_test, probabilites, seuil)

    CHEMIN_MODELE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, CHEMIN_MODELE)
    print(f"\nPipeline sérialisé dans {CHEMIN_MODELE}")


if __name__ == "__main__":
    main()
