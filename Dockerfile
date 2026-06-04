FROM apache/airflow:2.9.3-python3.11

# Les DAGs s'appuient sur le code applicatif et rechargent le pipeline sérialisé.
# On installe les mêmes versions que l'entraînement local : scikit-learn et joblib
# doivent être strictement identiques, faute de quoi le .joblib ne se recharge pas.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
