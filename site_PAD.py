import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import folium
from streamlit_folium import st_folium
from datetime import datetime
import sqlite3
import uuid
import time

# Connexion à la base SQLite
conn = sqlite3.connect("demandes.db", check_same_thread=False)
cursor = conn.cursor()

# Création table des demandes
cursor.execute('''
CREATE TABLE IF NOT EXISTS demandes (
    id TEXT PRIMARY KEY,
    nom TEXT,
    structure TEXT,
    email TEXT,
    raison TEXT,
    statut TEXT,
    token TEXT,
    timestamp REAL
)
''')
conn.commit()

st.set_page_config(page_title="Météo Douala", layout="wide")
st.title("🌦️ Tableau de bord MeteoMarine – Port Autonome de Douala")

# Chargement données
API_URL = "https://data-real-time-2.onrender.com/donnees?limit=50000000000"
data = requests.get(API_URL).json()
df = pd.DataFrame(data)

df["DateTime"] = pd.to_datetime(df["DateTime"])
df = df.sort_values("DateTime", ascending=False)

# --- Filtre date ---
st.sidebar.header("📅 Filtrer par date")
min_date = df["DateTime"].min().date()
max_date = df["DateTime"].max().date()
start_date, end_date = st.sidebar.date_input("Plage de dates", [min_date, max_date])
df = df[(df["DateTime"].dt.date >= start_date) & (df["DateTime"].dt.date <= end_date)]

# --- Aperçu météo ---
st.subheader("📍 Aperçu MeteoMarinePAD – données en Direct")
for _, row in df.head(3).iterrows():
    date_heure = row["DateTime"].strftime("%Y-%m-%d %H:%M:%S")
    st.markdown(f"""
    #### 📍 Station {row['Station']}
    - 🕒 Observation : {date_heure}
    - 🌡️ Température : {row['AIR TEMPERATURE']}°C
    - 💧 Humidité : {row['HUMIDITY']}%
    - 💨 Vent : {row['WIND SPEED']} m/s
    - 🧭 Pression : {row['AIR PRESSURE']} hPa
    """)
    if "TIDE HEIGHT" in row:
        st.markdown(f"- 🌊 Marée : {row['TIDE HEIGHT']} m")
    if "SURGE" in row:
        st.markdown(f"- ⚠️ SURGE : {row['SURGE']} m")

# --- Carte interactive ---
st.subheader("🗺️ Carte interactive des stations météo")
m = folium.Map(location=[4.05, 9.68], zoom_start=10)
stations_grouped = df.groupby("Station").first().reset_index()

for _, row in stations_grouped.iterrows():
    popup_html = f"""
    <div style="width: 250px;">
        <h4>📍 {row['Station']}</h4>
        <p><b>Date :</b> {row['DateTime'].strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><b>Température :</b> {row['AIR TEMPERATURE']} °C</p>
        <p><b>Vent :</b> {row['WIND SPEED']} m/s</p>
        <p><b>Humidité :</b> {row['HUMIDITY']} %</p>
        <p><b>Pression :</b> {row['AIR PRESSURE']} hPa</p>
    </div>
    """
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=folium.Popup(popup_html, max_width=300),
        tooltip=row["Station"],
        icon=folium.Icon(color="blue", icon="cloud")
    ).add_to(m)

st_folium(m, width=900, height=500)

# --- Graphiques
st.subheader("📈 Graphique par station et paramètre")

station_selected = st.selectbox("Station", df["Station"].unique())
params = ["AIR TEMPERATURE", "HUMIDITY", "WIND SPEED", "AIR PRESSURE"]
if "TIDE HEIGHT" in df.columns:
    params.append("TIDE HEIGHT")
if "SURGE" in df.columns:
    params.append("SURGE")

param = st.selectbox("Paramètre", params)
df_station = df[df["Station"] == station_selected].copy()
df_station[param] = pd.to_numeric(df_station[param], errors='coerce')
df_station = df_station.dropna(subset=[param])
if param == "TIDE HEIGHT":
    df_station = df_station[df_station[param] >= 0.3]
fig = px.line(df_station, x="DateTime", y=param, title=f"{param} à {station_selected}")
st.plotly_chart(fig, use_container_width=True)

# === 📊 Comparaison entre stations ===
st.subheader("📊 Comparaison multistation")

# Copie pour conversion numérique
df_numeric = df.copy()
for p in params:
    df_numeric[p] = pd.to_numeric(df_numeric[p], errors='coerce')

for p in params:
    df_plot = df_numeric.dropna(subset=[p])
    df_plot = df_plot[(df_plot["DateTime"].dt.date >= start_date) & (df_plot["DateTime"].dt.date <= end_date)]

    fig = px.line(df_plot, x="DateTime", y=p, color="Station", title=f"Comparaison – {p}")
    if p == "TIDE HEIGHT":
        max_val = df_plot[p].max()
        if pd.notnull(max_val):
            fig.update_yaxes(range=[0, max_val + 0.5])
    st.plotly_chart(fig, use_container_width=True)

# --- Carte météo Windy
st.subheader("🌐 Carte météo animée – Windy")
st.components.v1.html('''
<iframe width="100%" height="450" src="https://embed.windy.com/embed2.html?lat=4.05&lon=9.68&zoom=9&type=wind" frameborder="0"></iframe>
''', height=450)

# --- Demande utilisateur
st.subheader("💾 Demande de téléchargement des données météo")

with st.form("form_demande"):
    nom = st.text_input("Votre nom")
    structure = st.text_input("Structure")
    email = st.text_input("Votre email")
    raison = st.text_area("Raison de la demande")
    submit = st.form_submit_button("Envoyer la demande")

if submit:
    if not nom or not structure or not email or not raison:
        st.error("Tous les champs sont requis.")
    else:
        demande_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO demandes (id, nom, structure, email, raison, statut, token, timestamp)
            VALUES (?, ?, ?, ?, ?, 'en attente', NULL, NULL)
        ''', (demande_id, nom, structure, email, raison))
        conn.commit()
        st.success("✅ Demande envoyée. En attente de validation par l’administrateur.")

# --- Vérification des droits de téléchargement
cursor.execute('SELECT * FROM demandes WHERE email = ? AND statut = "acceptée"', (email,))
row = cursor.fetchone()
user_demande = None
if row:
    _, _, _, _, _, _, _, timestamp = row
    if timestamp and time.time() - timestamp <= 60:
        user_demande = row
    else:
        cursor.execute("UPDATE demandes SET statut = 'expirée' WHERE email = ?", (email,))
        conn.commit()

if user_demande:
    st.success("✅ Votre demande est acceptée. Vous avez 60 secondes pour télécharger.")

    export_cols = ["Station", "Latitude", "Longitude", "DateTime", "TIDE HEIGHT", "WIND SPEED", "WIND DIR",
                   "AIR PRESSURE", "AIR TEMPERATURE", "DEWPOINT", "HUMIDITY"]
    df_export = df[export_cols]
    csv = df_export.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Télécharger les données météo",
        data=csv,
        file_name="MeteoMarinePAD.csv",
        mime="text/csv"
    )
else:
    if email:
        cursor.execute('SELECT * FROM demandes WHERE email = ? AND statut = "expirée"', (email,))
        if cursor.fetchone():
            st.warning("⏱️ Le lien a expiré. Veuillez refaire une demande.")

# --- Interface admin
st.sidebar.header("🔐 Admin")
admin_password = st.sidebar.text_input("Mot de passe admin", type="password")

if admin_password == "LANGOUL":
    st.sidebar.success("Accès admin autorisé")
    st.sidebar.markdown("### 📥 Demandes en attente")

    cursor.execute("SELECT * FROM demandes WHERE statut = 'en attente'")
    demandes_attente = cursor.fetchall()

    for d in demandes_attente:
        demande_id, nom, structure, email, raison, _, _, _ = d
        st.sidebar.markdown(f"**{nom} ({email})**")
        st.sidebar.markdown(f"Structure : {structure}")
        st.sidebar.markdown(f"Raison : {raison}")
        col1, col2 = st.sidebar.columns(2)
        if col1.button(f"✅ Accepter {demande_id}", key=f"acc_{demande_id}"):
            token = str(uuid.uuid4())
            cursor.execute("UPDATE demandes SET statut='acceptée', token=?, timestamp=? WHERE id=?",
                           (token, time.time(), demande_id))
            conn.commit()
            st.sidebar.success(f"Acceptée pour {nom}")
        if col2.button(f"❌ Refuser {demande_id}", key=f"ref_{demande_id}"):
            cursor.execute("UPDATE demandes SET statut='refusée', timestamp=? WHERE id=?",
                           (time.time(), demande_id))
            conn.commit()
            st.sidebar.warning(f"Refusée pour {nom}")

    # Historique
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Historique des décisions")

    cursor.execute("SELECT * FROM demandes WHERE statut IN ('acceptée', 'refusée')")
    demandes_traitees = cursor.fetchall()
    for d in demandes_traitees:
        _, nom, structure, email, raison, statut, _, ts = d
        couleur = "🟢" if statut == "acceptée" else "🔴"
        heure = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "Inconnu"
        st.sidebar.markdown(f"""
        {couleur} **{nom}**  
        📧 {email}  
        🏢 {structure}  
        📌 {raison}  
        🕒 {heure}
        """)

    # Export CSV
    cursor.execute("SELECT nom, email, structure, raison, statut, timestamp FROM demandes")
    export_data = cursor.fetchall()
    df_export = pd.DataFrame(export_data, columns=["nom", "email", "structure", "raison", "statut", "timestamp"])
    df_export["Horodatage"] = df_export["timestamp"].apply(
        lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "")
    df_export = df_export.drop(columns=["timestamp"])
    st.sidebar.download_button(
        label="📤 Exporter l’historique",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name="historique_acces.csv",
        mime="text/csv"
    )

elif admin_password != "":
    st.sidebar.error("Mot de passe incorrect.")
