"""Accès à la base applicative Neon (PostgreSQL).

Centralise la connexion, la création du schéma, l'insertion idempotente des
transactions scorées et la requête du rapport quotidien. Toutes les requêtes sont
paramétrées (aucune concaténation de valeurs dans le SQL).

La colonne `current_time` reprend le nom du champ renvoyé par l'API. C'est aussi
un mot-clé SQL : elle est donc systématiquement entre guillemets dans les requêtes.
"""
import psycopg2
from psycopg2.extras import RealDictCursor

from src import config

# Ordre de référence des colonnes insérées par le DAG temps réel.
COLONNES_TRANSACTION = [
    "trans_num",
    "cc_num",
    "merchant",
    "category",
    "amt",
    "gender",
    "city_pop",
    "lat",
    "long",
    "merch_lat",
    "merch_long",
    "job",
    "dob",
    "current_time",
    "fraud_probability",
    "predicted_fraud",
    "is_fraud_actual",
]

REQUETE_CREATION_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    trans_num          TEXT PRIMARY KEY,
    cc_num             BIGINT,
    merchant           TEXT,
    category           TEXT,
    amt                NUMERIC,
    gender             TEXT,
    city_pop           INTEGER,
    lat                DOUBLE PRECISION,
    long               DOUBLE PRECISION,
    merch_lat          DOUBLE PRECISION,
    merch_long         DOUBLE PRECISION,
    job                TEXT,
    dob                DATE,
    "current_time"     TIMESTAMP,
    fraud_probability  DOUBLE PRECISION,
    predicted_fraud    BOOLEAN,
    is_fraud_actual    SMALLINT,
    created_at         TIMESTAMP DEFAULT now()
);
"""

# Insertion idempotente : un même trans_num ne crée jamais de doublon, ce qui rend
# le DAG temps réel rejouable sans risque.
REQUETE_UPSERT = """
INSERT INTO transactions (
    trans_num, cc_num, merchant, category, amt, gender, city_pop,
    lat, long, merch_lat, merch_long, job, dob, "current_time",
    fraud_probability, predicted_fraud, is_fraud_actual
) VALUES (
    %(trans_num)s, %(cc_num)s, %(merchant)s, %(category)s, %(amt)s, %(gender)s, %(city_pop)s,
    %(lat)s, %(long)s, %(merch_lat)s, %(merch_long)s, %(job)s, %(dob)s, %(current_time)s,
    %(fraud_probability)s, %(predicted_fraud)s, %(is_fraud_actual)s
)
ON CONFLICT (trans_num) DO NOTHING;
"""

# Transactions dont l'instant d'appel API tombe la veille (jour calendaire précédent).
REQUETE_VEILLE = """
SELECT trans_num, merchant, category, amt, "current_time",
       fraud_probability, predicted_fraud, is_fraud_actual
FROM transactions
WHERE "current_time"::date = (CURRENT_DATE - INTERVAL '1 day')::date
ORDER BY "current_time";
"""


def obtenir_connexion():
    """Ouvre une connexion psycopg2 vers la base Neon à partir de DATABASE_URL."""
    return psycopg2.connect(config.exiger("DATABASE_URL"))


def initialiser_base() -> None:
    """Crée la table `transactions` si elle n'existe pas encore."""
    with obtenir_connexion() as conn:
        with conn.cursor() as cur:
            cur.execute(REQUETE_CREATION_TABLE)


def inserer_transaction(transaction: dict) -> None:
    """Insère une transaction scorée, sans rien faire si `trans_num` existe déjà.

    `transaction` doit contenir les clés de COLONNES_TRANSACTION. L'idempotence est
    assurée par la clause ON CONFLICT sur la clé primaire.
    """
    with obtenir_connexion() as conn:
        with conn.cursor() as cur:
            cur.execute(REQUETE_UPSERT, transaction)


def transactions_de_la_veille() -> list[dict]:
    """Renvoie les transactions de la veille sous forme de liste de dictionnaires.

    Utilisée par le DAG quotidien pour agréger le récapitulatif et comparer les
    prédictions à la vérité terrain (`is_fraud_actual`).
    """
    with obtenir_connexion() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(REQUETE_VEILLE)
            return cur.fetchall()


if __name__ == "__main__":
    # Initialisation manuelle du schéma : python -m src.db
    initialiser_base()
    print("Table `transactions` prête.")
