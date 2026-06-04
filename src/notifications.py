"""Envoi des notifications e-mail.

Une seule fonction, réutilisée par les deux DAGs : l'alerte de fraude (temps réel)
et le récapitulatif quotidien. Les identifiants SMTP proviennent du `.env` ; rien
n'est codé en dur. Le port 587 implique une connexion en clair promue en TLS via
STARTTLS avant authentification.
"""
import smtplib
from email.message import EmailMessage

from src import config

DELAI_SMTP_SECONDES = 30


def envoyer_email(sujet: str, corps: str, destinataire: str | None = None) -> None:
    """Envoie un e-mail texte via le serveur SMTP configuré.

    `destinataire` est facultatif : à défaut, l'e-mail part vers `ALERT_EMAIL_TO`.
    Les paramètres SMTP (hôte, port, identifiants) sont lus depuis l'environnement.
    """
    expediteur = config.exiger("SMTP_USER")
    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = expediteur
    message["To"] = destinataire or config.exiger("ALERT_EMAIL_TO")
    message.set_content(corps)

    with smtplib.SMTP(config.exiger("SMTP_HOST"), config.SMTP_PORT, timeout=DELAI_SMTP_SECONDES) as serveur:
        serveur.starttls()
        serveur.login(expediteur, config.exiger("SMTP_PASSWORD"))
        serveur.send_message(message)
