"""Dashboard de supervision de la détection de fraude.

Lit en direct la base applicative Neon (les écritures des DAGs) et affiche les
indicateurs clés, l'activité par heure et les dernières transactions. Se rafraîchit
automatiquement pour suivre le pipeline pendant qu'il tourne.

Le stockage reste en UTC ; la conversion vers l'heure de Paris est faite uniquement
pour l'affichage (horodatages, axes, tableau).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from src.db import lire_transactions

INTERVALLE_RAFRAICHISSEMENT_S = 20
FUSEAU_AFFICHAGE = ZoneInfo("Europe/Paris")

# Palette : un seul accent (bleu), gris neutres pour le secondaire, rouge réservé
# exclusivement à la fraude.
ACCENT = "#2563EB"
ROUGE = "#DC2626"
ROUGE_FOND = "#FEE2E2"
GRIS_BLEU = "#94A3B8"
GRIS = "#64748B"
TEXTE = "#0F172A"
GRILLE = "#E2E8F0"

st.set_page_config(page_title="Supervision détection de fraude", layout="wide")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Détection de fraude : supervision")


def charger_donnees() -> pd.DataFrame:
    """Charge les transactions depuis Neon et normalise les types pour l'affichage."""
    df = pd.DataFrame(lire_transactions())
    if df.empty:
        return df
    df["amt"] = df["amt"].astype(float)
    df["fraud_probability"] = df["fraud_probability"].astype(float)
    df["transaction_time"] = pd.to_datetime(df["transaction_time"])
    # Conversion UTC -> Europe/Paris pour l'affichage uniquement (puis naïf pour
    # éviter toute ambiguïté de fuseau dans les graphes et le tableau).
    df["heure_locale"] = (
        df["transaction_time"].dt.tz_localize("UTC").dt.tz_convert(FUSEAU_AFFICHAGE).dt.tz_localize(None)
    )
    return df


def carte_kpi(colonne, libelle: str, valeur: str, rouge: bool = False) -> None:
    """Affiche un KPI dans une carte bordée ; les KPIs de fraude sont en rouge."""
    couleur = ROUGE if rouge else TEXTE
    with colonne.container(border=True):
        st.markdown(
            f"<div style='font-size:0.8rem;color:{GRIS};margin-bottom:0.2rem'>{libelle}</div>"
            f"<div style='font-size:1.7rem;font-weight:700;line-height:1.1;color:{couleur}'>{valeur}</div>",
            unsafe_allow_html=True,
        )


def graphe_activite(df: pd.DataFrame):
    """Barres empilées du nombre de transactions par heure, fraudes en rouge."""
    df = df.assign(
        heure=df["heure_locale"].dt.floor("h"),
        statut=df["predicted_fraud"].map({True: "Fraude prédite", False: "Normale"}),
    )
    par_heure = df.groupby(["heure", "statut"]).size().reset_index(name="transactions")
    fig = px.bar(
        par_heure,
        x="heure",
        y="transactions",
        color="statut",
        barmode="stack",
        template="plotly_white",
        category_orders={"statut": ["Normale", "Fraude prédite"]},
        color_discrete_map={"Normale": GRIS_BLEU, "Fraude prédite": ROUGE},
        labels={"heure": "Heure (Europe/Paris)", "transactions": "Transactions", "statut": "Statut"},
    )
    fig.update_xaxes(tickformat="%d/%m %Hh", showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRILLE)
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=360, legend_title_text="")
    return fig


def graphe_fraudes_categorie(df: pd.DataFrame):
    """Barres horizontales du nombre de fraudes prédites par catégorie."""
    fraudes = (
        df[df["predicted_fraud"]].groupby("category").size().reset_index(name="fraudes").sort_values("fraudes")
    )
    fig = px.bar(
        fraudes,
        x="fraudes",
        y="category",
        orientation="h",
        template="plotly_white",
        color_discrete_sequence=[ROUGE],
        labels={"fraudes": "Fraudes prédites", "category": "Catégorie"},
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRILLE)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=360)
    return fig


def tableau_transactions(df: pd.DataFrame):
    """Prépare le tableau stylé des 20 dernières transactions."""
    recent = df.sort_values("heure_locale", ascending=False).head(20).copy()
    recent["statut"] = recent["predicted_fraud"].map({True: "Fraude", False: "Normal"})
    recent["trans_court"] = recent["trans_num"].str[:8]
    recent["proba_pct"] = (recent["fraud_probability"] * 100).round(0)
    tableau = recent[["statut", "heure_locale", "trans_court", "merchant", "category", "amt", "proba_pct"]]

    def styliser(ligne):
        fraude = ligne["statut"] == "Fraude"
        fond = f"background-color:{ROUGE_FOND};color:{TEXTE}" if fraude else ""
        styles = [fond] * len(ligne)
        index_statut = list(ligne.index).index("statut")
        accent = f"color:{ROUGE};font-weight:600" if fraude else f"color:{GRIS}"
        styles[index_statut] = f"{fond};{accent}" if fond else accent
        return styles

    return tableau.style.apply(styliser, axis=1)


@st.fragment(run_every=INTERVALLE_RAFRAICHISSEMENT_S)
def afficher() -> None:
    """Construit le tableau de bord ; rejoué périodiquement pour le suivi en direct."""
    df = charger_donnees()
    maintenant = datetime.now(FUSEAU_AFFICHAGE)
    st.caption(
        f"Actualisé à {maintenant:%d/%m/%Y %H:%M:%S} (heure de Paris) "
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
    carte_kpi(c1, "Transactions", f"{nb:,}".replace(",", " "))
    carte_kpi(c2, "Fraudes prédites", f"{fraudes:,}".replace(",", " "), rouge=True)
    carte_kpi(c3, "Montant total", f"{montant_total:,.2f}".replace(",", " "))
    carte_kpi(c4, "Montant des fraudes", f"{montant_fraude:,.2f}".replace(",", " "), rouge=True)
    carte_kpi(c5, "Taux de fraude", f"{taux:.1%}", rouge=True)

    st.divider()

    st.subheader("Activité par heure")
    st.plotly_chart(graphe_activite(df), use_container_width=True)

    st.subheader("Fraudes prédites par catégorie")
    if int(df["predicted_fraud"].sum()) == 0:
        st.write("Aucune fraude détectée sur la période.")
    else:
        st.plotly_chart(graphe_fraudes_categorie(df), use_container_width=True)

    st.divider()

    st.subheader("Dernières transactions")
    st.dataframe(
        tableau_transactions(df),
        use_container_width=True,
        hide_index=True,
        column_config={
            "statut": st.column_config.TextColumn("Statut"),
            "heure_locale": st.column_config.DatetimeColumn("Horodatage", format="DD/MM/YYYY HH:mm"),
            "trans_court": st.column_config.TextColumn("Transaction"),
            "merchant": st.column_config.TextColumn("Marchand"),
            "category": st.column_config.TextColumn("Catégorie"),
            "amt": st.column_config.NumberColumn("Montant", format="%.2f"),
            "proba_pct": st.column_config.ProgressColumn(
                "Probabilité de fraude", min_value=0, max_value=100, format="%d%%"
            ),
        },
    )


afficher()
