"""Client de l'API temps réel des transactions.

Récupère une transaction sur l'endpoint configuré, gère le rate limit (HTTP 429)
avec quelques tentatives, et sépare le label `is_fraud` (que l'API laisse fuiter)
du reste des champs. Ce label n'est jamais utilisé comme feature : il est conservé
uniquement comme vérité terrain pour mesurer précision et rappel.
"""
import json
import time
from io import StringIO

import pandas as pd
import requests

from src import config

# L'API est limitée à 5 appels/minute ; en cas de 429 on patiente brièvement.
NOMBRE_TENTATIVES = 3
DELAI_RETRY_SECONDES = 5
DELAI_REQUETE_SECONDES = 30


def _parser_reponse(texte: str) -> pd.DataFrame:
    """Décode la réponse de l'API en DataFrame d'une ligne.

    L'API renvoie le résultat de `to_json(orient="split")` ré-encodé une seconde
    fois en chaîne JSON : on désérialise donc deux fois. `convert_dates=False` laisse
    `current_time` (epoch ms) et `dob` (texte) bruts, leur conversion étant gérée
    de façon centralisée dans features.construire_features.
    """
    charge = json.loads(texte)
    if isinstance(charge, str):
        return pd.read_json(StringIO(charge), orient="split", convert_dates=False)
    # Cas défensif : payload déjà au format split (dict) plutôt qu'une chaîne.
    return pd.DataFrame(charge["data"], columns=charge["columns"], index=charge["index"])


def _separer_label(df: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    """Extrait `is_fraud` du DataFrame et le renvoie à part comme vérité terrain.

    Renvoie le DataFrame débarrassé du label et la valeur du label (ou None si
    l'API ne l'a pas fait fuiter sur cet appel).
    """
    if "is_fraud" not in df.columns:
        return df, None
    is_fraud_actual = int(df["is_fraud"].iloc[0])
    return df.drop(columns=["is_fraud"]), is_fraud_actual


def recuperer_transaction() -> tuple[pd.DataFrame, int | None]:
    """Récupère une transaction depuis l'API et renvoie (df_une_ligne, is_fraud_actual).

    Le DataFrame contient les champs bruts de la transaction (dont `current_time`),
    sans le label. En cas de HTTP 429, on réessaie après une courte attente en
    respectant l'en-tête `Retry-After` s'il est présent.
    """
    url = config.exiger("API_URL")
    for _ in range(NOMBRE_TENTATIVES):
        reponse = requests.get(url, timeout=DELAI_REQUETE_SECONDES)
        if reponse.status_code == 429:
            attente = int(reponse.headers.get("Retry-After", DELAI_RETRY_SECONDES))
            time.sleep(attente)
            continue
        reponse.raise_for_status()
        return _separer_label(_parser_reponse(reponse.text))
    raise RuntimeError(
        f"API temps réel indisponible (HTTP 429) après {NOMBRE_TENTATIVES} tentatives."
    )


if __name__ == "__main__":
    # Vérification manuelle : python -m src.api_client
    transaction, label = recuperer_transaction()
    print(transaction.to_string(index=False))
    print(f"is_fraud_actual = {label}")
