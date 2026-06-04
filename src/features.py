"""Feature engineering partagé entre l'entraînement (CSV) et le serving (API).

Le même code construit les features dans les deux contextes, ce qui élimine tout
écart de préprocessing (train/serve skew). Seules des variables calculables depuis
une transaction isolée sont produites : aucune feature comportementale par client,
qui serait toujours vide au serving puisque l'API renvoie des transactions au hasard.
"""
import numpy as np
import pandas as pd

# Features produites par construire_features, regroupées par type et dans un ordre
# stable. Réutilisées par le ColumnTransformer du pipeline d'entraînement.
COLONNES_CATEGORIELLES = ["category", "gender"]
COLONNES_NUMERIQUES = [
    "amt",
    "city_pop",
    "age",
    "hour",
    "day_of_week",
    "is_night",
    "is_weekend",
    "distance_km",
]


def calculer_distance_haversine(lat1, lon1, lat2, lon2):
    """Distance de Haversine en kilomètres entre deux points géographiques.

    Accepte indifféremment des scalaires ou des séries/tableaux numpy : le calcul
    est vectorisé, ce qui permet de l'appliquer à une colonne entière du CSV comme
    à une transaction unique.
    """
    rayon_terre_km = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = np.sin(d_lat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(d_lon / 2) ** 2
    return 2 * rayon_terre_km * np.arcsin(np.sqrt(a))


def _serie_horodatage(df: pd.DataFrame) -> pd.Series:
    """Renvoie l'horodatage de référence selon le contexte d'appel.

    À l'entraînement, le CSV fournit `trans_date_trans_time` ; au serving, l'API
    ne fournit que `current_time`. La sémantique temporelle (heure de la journée,
    jour de la semaine) est transférable entre les deux.
    """
    if "trans_date_trans_time" in df.columns:
        return pd.to_datetime(df["trans_date_trans_time"])
    if "current_time" in df.columns:
        return pd.to_datetime(df["current_time"])
    raise KeyError(
        "Aucune colonne d'horodatage trouvée (ni trans_date_trans_time ni current_time)."
    )


def construire_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les features de prédiction à partir d'un DataFrame brut.

    Fonctionne à l'identique sur le CSV d'entraînement et sur une transaction de
    l'API. Renvoie un DataFrame ne contenant que les colonnes de features (sans le
    label), dans l'ordre défini par COLONNES_CATEGORIELLES + COLONNES_NUMERIQUES.
    """
    horodatage = _serie_horodatage(df)
    dob = pd.to_datetime(df["dob"])

    features = pd.DataFrame(index=df.index)
    features["category"] = df["category"].astype(str)
    features["gender"] = df["gender"].astype(str)

    features["amt"] = pd.to_numeric(df["amt"])
    features["city_pop"] = pd.to_numeric(df["city_pop"])
    features["age"] = (horodatage - dob).dt.days / 365.25

    features["hour"] = horodatage.dt.hour
    features["day_of_week"] = horodatage.dt.dayofweek
    # Nuit : 22h–6h. Fenêtre où la fraude est sur-représentée dans les données.
    features["is_night"] = ((horodatage.dt.hour >= 22) | (horodatage.dt.hour < 6)).astype(int)
    features["is_weekend"] = (horodatage.dt.dayofweek >= 5).astype(int)

    features["distance_km"] = calculer_distance_haversine(
        df["lat"], df["long"], df["merch_lat"], df["merch_long"]
    )

    return features[COLONNES_CATEGORIELLES + COLONNES_NUMERIQUES]
