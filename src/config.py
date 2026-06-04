"""Lecture centralisée des variables d'environnement du projet.

Les valeurs sont chargées une fois depuis le fichier `.env` à l'import du module.
Tous les autres modules passent par ici plutôt que de lire `os.environ` en direct.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Source temps réel et données locales
API_URL = os.getenv("API_URL")
CSV_PATH = os.getenv("CSV_PATH")

# Base applicative Neon
DATABASE_URL = os.getenv("DATABASE_URL")

# Seuil de décision du modèle (rappel privilégié, voir README)
FRAUD_THRESHOLD = float(os.getenv("FRAUD_THRESHOLD", "0.4"))

# Notifications e-mail
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")


def exiger(nom_variable: str) -> str:
    """Renvoie la variable d'environnement demandée ou lève une erreur si absente.

    Utilisé pour les variables sans valeur par défaut acceptable (chemin du CSV,
    URL de la base, identifiants), afin d'échouer tôt avec un message clair.
    """
    valeur = os.getenv(nom_variable)
    if not valeur:
        raise RuntimeError(
            f"Variable d'environnement requise manquante : {nom_variable}. "
            "Renseignez-la dans votre fichier .env (voir .env.template)."
        )
    return valeur
