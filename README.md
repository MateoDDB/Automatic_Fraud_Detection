# Automatic Fraud Detection

Système de détection de fraude en temps réel. Un modèle scikit-learn entraîné
hors-ligne est servi par un pipeline de données orchestré par Airflow : chaque
minute, une transaction est récupérée depuis une API, scorée, puis stockée dans
une base PostgreSQL (Neon). Toute fraude détectée déclenche une alerte e-mail,
et un récapitulatif de la veille est envoyé chaque matin.

Projet de certification Bloc 3 — conception et mise en œuvre de pipelines de
données pour l'IA. L'accent porte sur le pipeline, le modèle restant volontairement
simple.

## Architecture

Trois couches : source de données → orchestration Airflow → sorties métier.

- Phase hors-ligne (une fois, en local) : EDA et feature engineering sur le CSV,
  entraînement d'un `Pipeline` scikit-learn, sérialisé en un unique `.joblib`.
- Phase en ligne (orchestrée) : un DAG « temps réel » (chaque minute) interroge
  l'API, applique le même pipeline de préprocessing, prédit la probabilité de
  fraude, écrit dans Neon et alerte par e-mail si nécessaire. Un DAG « quotidien »
  (8h) agrège la veille et envoie un rapport.

Le schéma d'infrastructure est dans `architecture/`.

## Stack

- Python 3.11
- scikit-learn, pandas, numpy, joblib (modélisation)
- Apache Airflow 2.x via Docker Compose (orchestration)
- Neon PostgreSQL via psycopg2 (stockage applicatif)
- SMTP / smtplib (notifications)

## Prérequis

- Docker et Docker Compose
- Python 3.11 pour l'entraînement local
- Une base Neon PostgreSQL et un compte SMTP (mot de passe d'application)
- Le fichier `fraudTest.csv` en local (voir `data/README.md`)

## Installation et ordre de lancement

1. Récupérer `fraudTest.csv` et noter son chemin (voir `data/README.md`).
2. Copier `.env.template` vers `.env` et renseigner les variables (section
   ci-dessous). Le fichier `.env` n'est jamais versionné.
3. Créer un environnement et installer les dépendances d'entraînement :
   `pip install -r requirements.txt`.
4. Entraîner le modèle : `python -m src.train`. Produit
   `models/fraud_pipeline.joblib` et affiche les métriques.
5. Démarrer l'orchestration : `docker compose up`. Les deux DAGs apparaissent
   dans l'interface Airflow.

## Structure

```
.
├── architecture/   schéma d'infrastructure
├── notebooks/      EDA et feature engineering
├── src/            code applicatif (features, entraînement, API, base, modèle, e-mails)
├── dags/           DAGs Airflow (temps réel, rapport quotidien)
├── dashboard/      monitoring Streamlit (Lot 2)
├── tests/          tests unitaires (Lot 2)
├── models/         modèle sérialisé (généré, non versionné)
└── data/           CSV d'entraînement (local, non versionné)
```

## Variables d'environnement

Définies dans `.env` à partir de `.env.template` :

- `API_URL` — endpoint de l'API temps réel
- `CSV_PATH` — chemin local du CSV d'entraînement
- `DATABASE_URL` — connexion Neon PostgreSQL
- `FRAUD_THRESHOLD` — seuil de décision (défaut 0.4)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL_TO` — e-mail
- `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__WEBSERVER__SECRET_KEY` — secrets Airflow
