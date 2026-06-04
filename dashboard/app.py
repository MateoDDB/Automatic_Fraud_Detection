"""Dashboard de supervision de la détection de fraude.

Lit en direct la base applicative Neon (les écritures des DAGs) et affiche les
indicateurs clés, l'évolution du volume et des fraudes dans le temps, ainsi que les
dernières transactions. Se rafraîchit automatiquement pour suivre le pipeline pendant
qu'il tourne.
"""
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st

from src.db import lire_transactions

INTERVALLE_RAFRAICHISSEMENT_S = 20

st.set_page_config(page_title="Supervision détection de fraude", layout="wide")
st.title("Détection de fraude — supervision")


def charger_donnees() -> pd.DataFrame:
    """Charge les transactions depuis Neon et normalise les types pour l'affichage."""
    df = pd.DataFrame(lire_transactions())
    if df.empty:
        return df
    df["amt"] = df["amt"].astype(float)
    df["fraud_probability"] = df["fraud_probability"].astype(float)
    df["transaction_time"] = pd.to_datetime(df["transaction_time"])
    return df


@st.fragment(run_every=INTERVALLE_RAFRAICHISSEMENT_S)
def afficher() -> None:
    """Construit le tableau de bord ; rejoué périodiquement pour le suivi en direct."""
    df = charger_donnees()
    st.caption(
        f"Actualisé à {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC "
        f"· rafraîchissement toutes les {INTERVALLE_RAFRAICHISSEMENT_S} s"
    )

    if df.empty:
        st.info("Aucune transaction enregistrée pour le moment.")
        return

    nb = len(df)
    fraudes = int(df["predicted_fraud"].sum())
    montant_total = df["amt"].sum()
    montant_fraude = df.loc[df["predicted_fraud"], "amt"].sum()
    taux = fraudes / nb if nb else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Transactions", f"{nb}")
    c2.metric("Fraudes prédites", f"{fraudes}")
    c3.metric("Montant total", f"{montant_total:,.2f}")
    c4.metric("Montant des fraudes", f"{montant_fraude:,.2f}")
    c5.metric("Taux de fraude", f"{taux:.1%}")

    # Agrégation à la minute sur l'instant métier de la transaction.
    df["minute"] = df["transaction_time"].dt.floor("min")
    volume = df.groupby("minute").size().reset_index(name="transactions")
    fraudes_temps = df[df["predicted_fraud"]].groupby("minute").size().reset_index(name="fraudes")

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Volume de transactions dans le temps")
        st.plotly_chart(
            px.bar(volume, x="minute", y="transactions",
                   labels={"minute": "Heure (UTC)", "transactions": "Transactions"}),
            use_container_width=True,
        )
    with g2:
        st.subheader("Fraudes détectées dans le temps")
        if fraudes_temps.empty:
            st.write("Aucune fraude détectée sur la période.")
        else:
            st.plotly_chart(
                px.bar(fraudes_temps, x="minute", y="fraudes",
                       labels={"minute": "Heure (UTC)", "fraudes": "Fraudes"}),
                use_container_width=True,
            )

    st.subheader("Dernières transactions")
    colonnes = [
        "transaction_time", "trans_num", "merchant", "category", "amt",
        "fraud_probability", "predicted_fraud", "is_fraud_actual",
    ]
    derniers = df.sort_values("transaction_time", ascending=False).head(20)[colonnes]

    def surligner_fraude(ligne):
        couleur = "background-color: #fde2e2" if ligne["predicted_fraud"] else ""
        return [couleur] * len(ligne)

    st.dataframe(
        derniers.style.apply(surligner_fraude, axis=1),
        use_container_width=True,
        hide_index=True,
    )


afficher()
