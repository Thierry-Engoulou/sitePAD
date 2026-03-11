import streamlit as st
import pandas as pd
import requests
import os
import plotly.express as px

API_URL = "https://data-real-time-6.onrender.com/donnees"
CACHE_FILE = "data_cache.parquet"

st.title("🌦 Dashboard météo temps réel")

# -----------------------------
# ETAPE 1 : Charger les données
# -----------------------------

if st.button("📥 Charger les données depuis l'API"):

    with st.spinner("Téléchargement des données..."):

        try:
            r = requests.get(API_URL, timeout=120)

            if r.status_code != 200:
                st.error(f"Erreur API : {r.status_code}")
            else:

                data = r.json()

                df = pd.DataFrame(data)

                df["DateTime"] = pd.to_datetime(df["DateTime"])

                df.to_parquet(CACHE_FILE)

                st.success(f"✅ Données chargées : {len(df)} lignes")

        except Exception as e:
            st.error(f"Erreur connexion : {e}")


# -----------------------------
# ETAPE 2 : Visualiser
# -----------------------------

if st.button("📊 Visualiser les données"):

    if not os.path.exists(CACHE_FILE):
        st.warning("⚠️ Vous devez d'abord charger les données")
    else:

        df = pd.read_parquet(CACHE_FILE)

        df["DateTime"] = pd.to_datetime(df["DateTime"])

        st.success(f"Données disponibles : {len(df)} lignes")

        # filtre 7 jours
        last_date = df["DateTime"].max()
        start_date = last_date - pd.Timedelta(days=7)

        df7 = df[df["DateTime"] >= start_date]

        st.subheader("Température (7 derniers jours)")

        fig1 = px.line(
            df7,
            x="DateTime",
            y="AIR TEMPERATURE",
            title="Température"
        )

        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("Pression atmosphérique")

        fig2 = px.line(
            df7,
            x="DateTime",
            y="AIR PRESSURE",
            title="Pression"
        )

        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Hauteur de marée")

        fig3 = px.line(
            df7,
            x="DateTime",
            y="TIDE HEIGHT",
            title="Marée"
        )

        st.plotly_chart(fig3, use_container_width=True)

        # ------------------------
        # visualisation période
        # ------------------------

        st.subheader("Visualisation par période")

        start = st.date_input("Date début")
        end = st.date_input("Date fin")

        if st.button("Afficher période"):

            start = pd.to_datetime(start)
            end = pd.to_datetime(end)

            dfp = df[(df["DateTime"] >= start) & (df["DateTime"] <= end)]

            fig4 = px.line(
                dfp,
                x="DateTime",
                y="AIR TEMPERATURE",
                title="Température période"
            )

            st.plotly_chart(fig4, use_container_width=True)
