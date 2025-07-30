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
from folium.features import DivIcon
from branca.element import MacroElement
from jinja2 import Template
from streamlit_folium import st_folium

import math

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

def wind_dir_to_text(deg):
    try:
        deg = float(deg)
    except:
        return "Inconnu"
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = int((deg + 22.5) // 45) % 8
    return directions[ix]

for _, row in df.head(3).iterrows():
    wind_deg = row.get("WIND DIR", "N/A")
    wind_dir_text = wind_dir_to_text(wind_deg)
    date_heure = row["DateTime"].strftime("%Y-%m-%d %H:%M:%S")

    st.markdown(fr"""
    #### 📍 Station {row['Station']}
    - 🕒 Observation : {date_heure}
    - 🌡️ Température : {row['AIR TEMPERATURE']}°C
    - 💧 Humidité : {row['HUMIDITY']}%
    - 💨 Vent : {row['WIND SPEED']} m/s
    - 🧭 Direction du vent : {wind_deg}° ({wind_dir_text})
    - ⚖️ Pression : {row['AIR PRESSURE']} hPa
    """)
    if "TIDE HEIGHT" in row:
        st.markdown(f"- 🌊 Marée : {row['TIDE HEIGHT']} m")
    if "SURGE" in row:
        st.markdown(f"- ⚠️ SURGE : {row['SURGE']} m")


st.subheader("🗺️ Carte interactive des stations météo avec flèches directionnelles dynamiques")

# ------- Fonctions utils --------
def wind_dir_to_text(deg):
    try:
        deg = float(deg)
    except:
        return "Inconnu"
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = int((deg + 22.5) // 45) % 8
    return directions[ix]

def get_wind_style(speed):
    try:
        speed = float(speed)
    except:
        return "blue", 18  # défaut
    if speed < 3:
        return "blue", 18  # vent faible
    elif 3 <= speed < 7:
        return "orange", 24  # modéré
    else:
        return "red", 30  # fort

def create_arrow_icon(rotation_deg, speed):
    color, size = get_wind_style(speed)
    return DivIcon(
        html=f'''
            <div style="transform: rotate({rotation_deg}deg);
                        font-size: {size}px;
                        color: {color};
                        text-align: center;">
                ↑
            </div>
        ''',
        icon_size=(size, size),
        icon_anchor=(size // 2, size // 2),
    )

# --- Carte ---
# --- Carte ---
m = folium.Map(location=[4.05, 9.68], zoom_start=10)

# Remplace 'df' par ton DataFrame réel avec les colonnes attendues
stations_grouped = df.groupby("Station").first().reset_index()

for _, row in stations_grouped.iterrows():
    wind_dir = row.get("WIND DIR", None)
    wind_speed = row.get("WIND SPEED", None)

    if pd.isna(wind_dir) or pd.isna(wind_speed):
        continue

    rotation_deg = float(wind_dir)
    direction_text = wind_dir_to_text(wind_dir)

    # Assure-toi que "DateTime" est bien de type datetime
    last_date = row["DateTime"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["DateTime"]) else "Date inconnue"

    popup_html = f"""
        <div style="width: 250px; font-size: 13px; background-color: #f8f9fa;
                border: 1px solid #ddd; border-radius: 8px; padding: 10px;">
        <h4 style="margin-top: 0; color: #007bff;">📍 {row['Station']}</h4>
        <p><b>📅 Date :</b> {last_date}</p>
        <p><b>🌡️ Température :</b> {row['AIR TEMPERATURE']} °C</p>
        <p><b>💨 Vent :</b>Vitesse: {row['WIND SPEED']} m/s et Dir: {wind_dir}° ({direction_text})</p>
        <p><b>💧 Humidité :</b> {row['HUMIDITY']} %</p>
        <p><b>🧭 Pression :</b> {row['AIR PRESSURE']} hPa</p>
        {f"<p><b>🌊 Marée :</b> {row['TIDE HEIGHT']} m</p>" if "TIDE HEIGHT" in row else ""}
        {f"<p><b>⚠️ SURGE :</b> {row['SURGE']} m</p>" if "SURGE" in row else ""}
        </div>
    """
    # Tu peux ensuite l'utiliser dans un Marker ou autre chose ici
    folium.Marker(
        location=[row["Latitude"], row["Longitude"]],
        popup=folium.Popup(popup_html, max_width=300),
        icon=create_arrow_icon(rotation_deg, wind_speed)
    ).add_to(m)

    folium.map.Marker(
        [row["Latitude"] + 0.01, row["Longitude"]],
        icon=DivIcon(
            icon_size=(150, 36),
            icon_anchor=(0, 0),
            html=f'<div style="font-size: 12pt; font-weight: bold; color: black;">{row["Station"]}</div>'
        )
    ).add_to(m)

# --- Légende avec MacroElement (compatible st_folium) ---
legend_template = """
{% macro html(this, kwargs) %}
<div style='
    position: absolute;
    bottom: 30px;
    left: 30px;
    width: 220px;
    background-color: white;
    border: 2px solid grey;
    z-index: 9999;
    font-size: 14px;
    padding: 10px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
'>
    <b>💨 Légende vitesse du vent</b><br>
    <span style='color:blue;'>⬆️ Faible (&lt; 3 m/s)</span><br>
    <span style='color:orange;'>⬆️ Modéré (3–7 m/s)</span><br>
    <span style='color:red;'>⬆️ Fort (&gt; 7 m/s)</span>
</div>
{% endmacro %}
"""

legend = MacroElement()
legend._template = Template(legend_template)
m.get_root().add_child(legend)

# --- Affichage Streamlit ---
st_folium(m, width=900, height=500)

# --- Graphiques
params = ["AIR TEMPERATURE", "HUMIDITY", "WIND SPEED", "AIR PRESSURE"]
if "TIDE HEIGHT" in df.columns:
    params.append("TIDE HEIGHT")
if "SURGE" in df.columns:
    params.append("SURGE")
st.subheader("📈 Graphique par station et paramètre")

tab1, tab2 = st.tabs(["🗓️ Derniers 30 jours", "📅 Période personnalisée"])

with tab1:
    df_last_30 = df[df["DateTime"] >= (df["DateTime"].max() - pd.Timedelta(days=30))]
    station_selected = st.selectbox("Station (30 jours)", df_last_30["Station"].unique(), key="station_30")
    param = st.selectbox("Paramètre (30 jours)", params, key="param_30")

    df_station = df_last_30[df_last_30["Station"] == station_selected].copy()
    df_station[param] = pd.to_numeric(df_station[param], errors='coerce')
    df_station = df_station.dropna(subset=[param])
    if param == "TIDE HEIGHT":
        df_station = df_station[df_station[param] >= 0.3]

    fig = px.line(df_station, x="DateTime", y=param, title=f"{param} à {station_selected} (30 derniers jours)")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    station_selected = st.selectbox("Station (perso)", df["Station"].unique(), key="station_custom")
    param = st.selectbox("Paramètre (perso)", params, key="param_custom")
    start_custom, end_custom = st.date_input("Sélectionnez une plage de dates", [min_date, max_date], key="range_custom")

    df_custom = df[
        (df["DateTime"].dt.date >= start_custom) & (df["DateTime"].dt.date <= end_custom)
    ]
    df_station = df_custom[df_custom["Station"] == station_selected].copy()
    df_station[param] = pd.to_numeric(df_station[param], errors='coerce')
    df_station = df_station.dropna(subset=[param])
    if param == "TIDE HEIGHT":
        df_station = df_station[df_station[param] >= 0.3]

    fig = px.line(df_station, x="DateTime", y=param, title=f"{param} à {station_selected} ({start_custom} → {end_custom})")
    st.plotly_chart(fig, use_container_width=True)

# === 📊 Comparaison entre stations ===
st.subheader("📊 Comparaison multistation")

# Préparation des données numériques
df_numeric = df.copy()
for p in params:
    df_numeric[p] = pd.to_numeric(df_numeric[p], errors='coerce')

tab1, tab2 = st.tabs(["🗓️ 30 derniers jours", "📅 Période personnalisée"])

# 🔹 Onglet : 30 derniers jours
with tab1:
    df_last_30 = df_numeric[df_numeric["DateTime"] >= (df_numeric["DateTime"].max() - pd.Timedelta(days=30))].copy()
    for p in params:
        df_plot = df_last_30.dropna(subset=[p])
        fig = px.line(df_plot, x="DateTime", y=p, color="Station", title=f"Comparaison – {p} (30 derniers jours)")
        if p == "TIDE HEIGHT":
            max_val = df_plot[p].max()
            if pd.notnull(max_val):
                fig.update_yaxes(range=[0, max_val + 0.5])
        st.plotly_chart(fig, use_container_width=True)

# 🔹 Onglet : Période personnalisée
with tab2:
    start_custom, end_custom = st.date_input("Période à comparer", [min_date, max_date], key="compare_range")

    df_custom = df_numeric[
        (df_numeric["DateTime"].dt.date >= start_custom) & (df_numeric["DateTime"].dt.date <= end_custom)
    ].copy()

    for p in params:
        df_plot = df_custom.dropna(subset=[p])
        fig = px.line(df_plot, x="DateTime", y=p, color="Station", title=f"Comparaison – {p} ({start_custom} → {end_custom})")
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

# --- Notification publique si des demandes sont en attente
cursor.execute("SELECT COUNT(*) FROM demandes WHERE statut = 'en attente'")
nb_attente = cursor.fetchone()[0]

if nb_attente > 0:
    st.sidebar.warning(f"📬 {nb_attente} demande(s) en attente de validation.")

# --- Interface admin
st.sidebar.header("🔐 Admin")
admin_password = st.sidebar.text_input("Mot de passe admin", type="password")

if admin_password == "SHy@2025":
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
