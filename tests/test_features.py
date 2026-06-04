"""Tests du feature engineering (src/features.py).

Ne dépend ni d'Airflow, ni du modèle, ni du réseau : uniquement pandas et numpy.
"""
import pandas as pd

from src.features import (
    COLONNES_CATEGORIELLES,
    COLONNES_NUMERIQUES,
    calculer_distance_haversine,
    construire_features,
    serie_horodatage,
)


def transaction_exemple(current_time_ms: int) -> pd.DataFrame:
    """Construit une transaction d'exemple d'une ligne, au format de l'API."""
    return pd.DataFrame(
        [
            {
                "category": "grocery_pos",
                "gender": "F",
                "amt": 75.5,
                "city_pop": 50000,
                "dob": "1990-01-01",
                "lat": 40.0,
                "long": -75.0,
                "merch_lat": 41.0,
                "merch_long": -75.0,
                "current_time": current_time_ms,
            }
        ]
    )


def test_haversine_point_identique():
    """Deux points confondus donnent une distance nulle."""
    assert calculer_distance_haversine(45.0, 3.0, 45.0, 3.0) == 0.0


def test_haversine_distance_connue():
    """Un degré de longitude à l'équateur vaut environ 111,19 km."""
    distance = calculer_distance_haversine(0.0, 0.0, 0.0, 1.0)
    assert abs(distance - 111.19) < 0.5


def test_serie_horodatage_epoch_ms():
    """Un current_time en millisecondes est converti à la bonne date UTC."""
    instant = pd.Timestamp("2024-06-15 22:30:00")
    epoch_ms = instant.value // 1_000_000
    df = transaction_exemple(epoch_ms)
    assert serie_horodatage(df).iloc[0] == instant


def test_construire_features_colonnes_et_valeurs():
    """Renvoie les colonnes attendues et des valeurs temporelles/géo cohérentes."""
    instant = pd.Timestamp("2024-06-15 22:30:00")  # un samedi, 22h
    df = transaction_exemple(instant.value // 1_000_000)
    features = construire_features(df)

    assert list(features.columns) == COLONNES_CATEGORIELLES + COLONNES_NUMERIQUES
    assert not features.isna().any().any()

    ligne = features.iloc[0]
    assert ligne["category"] == "grocery_pos"
    assert ligne["hour"] == 22
    assert ligne["is_night"] == 1
    assert ligne["is_weekend"] == 1
    # Un degré de latitude d'écart vaut environ 111 km.
    assert abs(ligne["distance_km"] - 111.19) < 1.0
    assert 34 <= ligne["age"] <= 35
