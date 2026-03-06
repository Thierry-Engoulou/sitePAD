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
import math
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ✅ Configuration de la page
st.set_page_config(page_title="Météo Douala", layout="wide")

# ✅ Lecture automatique du paramètre email depuis l’URL
params = st.query_params
if "email" in params:
    st.session_state.user_email = params["email"]

# ✅ Connexion SQLite
conn = sqlite3.connect("demandes.db", check_same_thread=False)
cursor = conn.cursor()

# ✅ Table des demandes
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

# ✅ Fonction envoi email
def envoyer_email(destinataire, sujet, contenu_html):

    expediteur = "thierrygpt3@gmail.com"
    mot_de_passe = "teqbomlbqyyplwso"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = sujet
    msg["From"] = expediteur
    msg["To"] = destinataire

    part = MIMEText(contenu_html, "html")
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
            serveur.login(expediteur, mot_de_passe)
            serveur.sendmail(expediteur, destinataire, msg.as_string())
            print(f"Email envoyé à {destinataire}")

    except Exception as e:
        print(f"Erreur email : {e}")

st.title("📥 Téléchargement de données météo")

# ✅ Chargement sécurisé des données API
@st.cache_data(ttl=120)
def charger_donnees():

    API_URL = "https://data-real-time-2.onrender.com/donnees?limit=10000"

    try:
        response = requests.get(API_URL, timeout=30)

        if response.status_code != 200:
            st.error(f"Erreur API : {response.status_code}")
            return pd.DataFrame()

        data = response.json()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Erreur chargement API : {e}")
        return pd.DataFrame()


df = charger_donnees()

if df.empty:
    st.error("Aucune donnée disponible depuis l'API.")
    st.stop()

df["DateTime"] = pd.to_datetime(df["DateTime"])
df = df.sort_values("DateTime", ascending=False)

# ✅ Filtrage par date
st.sidebar.header("📅 Filtrer par date")

min_date = df["DateTime"].min().date()
max_date = df["DateTime"].max().date()

start_date, end_date = st.sidebar.date_input(
    "Plage de dates",
    [min_date, max_date]
)

df = df[
    (df["DateTime"].dt.date >= start_date) &
    (df["DateTime"].dt.date <= end_date)
]

# ✅ Formulaire utilisateur
st.subheader("📨 Demande de téléchargement")

if "user_email" not in st.session_state:
    st.session_state.user_email = ""

with st.form("form_demande"):

    nom = st.text_input("Votre nom")
    structure = st.text_input("Structure")
    email = st.text_input("Votre email", value=st.session_state.user_email)
    raison = st.text_area("Raison de la demande")

    submit = st.form_submit_button("Envoyer la demande")

if submit:

    if not nom or not structure or not email or not raison:

        st.error("Tous les champs sont requis.")

    else:

        demande_id = str(uuid.uuid4())

        st.session_state.user_email = email

        cursor.execute('''
        INSERT INTO demandes
        (id, nom, structure, email, raison, statut, token, timestamp)
        VALUES (?, ?, ?, ?, ?, 'en attente', NULL, NULL)
        ''', (demande_id, nom, structure, email, raison))

        conn.commit()

        st.success("✅ Demande envoyée. En attente de validation par l’administrateur.")

# ✅ Vérification automatique pour téléchargement

email_to_check = st.session_state.user_email

if email_to_check:

    cursor.execute(
        'SELECT * FROM demandes WHERE email = ? AND statut = "acceptée"',
        (email_to_check,)
    )

    row = cursor.fetchone()

    user_demande = None

    if row:

        _, _, _, _, _, _, _, timestamp = row

        if timestamp and time.time() - timestamp <= 300:

            user_demande = row

        else:

            cursor.execute(
                "UPDATE demandes SET statut = 'expirée' WHERE email = ?",
                (email_to_check,)
            )

            conn.commit()

    if user_demande:

        st.success("✅ Votre demande est acceptée. Vous avez 60 secondes pour télécharger.")

        export_cols = [
            "Station",
            "Latitude",
            "Longitude",
            "DateTime",
            "TIDE HEIGHT",
            "WIND SPEED",
            "WIND DIR",
            "AIR PRESSURE",
            "AIR TEMPERATURE",
            "DEWPOINT",
            "HUMIDITY"
        ]

        df_export = df[export_cols]

        csv = df_export.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="📥 Télécharger les données météo",
            data=csv,
            file_name="MeteoMarinePAD.csv",
            mime="text/csv"
        )

    else:

        cursor.execute(
            'SELECT * FROM demandes WHERE email = ? AND statut = "expirée"',
            (email_to_check,)
        )

        if cursor.fetchone():

            st.warning("⏱️ Le lien a expiré. Veuillez refaire une demande.")

# ✅ Interface administrateur

cursor.execute("SELECT COUNT(*) FROM demandes WHERE statut = 'en attente'")
nb_attente = cursor.fetchone()[0]

if nb_attente > 0:
    st.sidebar.warning(f"📬 {nb_attente} demande(s) en attente de validation.")

st.sidebar.header("🔐 Admin")

admin_password = st.sidebar.text_input("Mot de passe admin", type="password")

if admin_password == "SHy@2025":

    st.sidebar.success("Accès admin autorisé")

    st.sidebar.markdown("### 📩 Demandes en attente")

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
            horo = time.time()

            cursor.execute(
                "UPDATE demandes SET statut='acceptée', token=?, timestamp=? WHERE id=?",
                (token, horo, demande_id)
            )

            conn.commit()

            lien_app = f"https://sitepad-5.onrender.com/?email={email}"

            contenu_mail = f"""
            <html>
            <body>
            <p>Bonjour {nom},</p>
            <p>Votre demande de téléchargement de données météo a été <b>acceptée</b>.</p>
            <p>Vous avez 60 secondes pour télécharger via ce lien :</p>
            <p><a href="{lien_app}">Accéder à l'application</a></p>
            </body>
            </html>
            """

            envoyer_email(email, "Demande acceptée", contenu_mail)

            st.sidebar.success(f"Acceptée + email envoyé à {email}")

        if col2.button(f"❌ Refuser {demande_id}", key=f"ref_{demande_id}"):

            cursor.execute(
                "UPDATE demandes SET statut='refusée', timestamp=? WHERE id=?",
                (time.time(), demande_id)
            )

            conn.commit()

            st.sidebar.warning(f"Refusée pour {nom}")
