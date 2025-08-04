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

# ✅ Rafraîchissement automatique
st.query_params["refresh"] = str(time.time())

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
    expediteur = "engoulouthierry62@gmail.com"
    mot_de_passe = "tfzy bsaq rlyn tkox"  # Mot de passe d'application
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
            print(f"✅ Email envoyé à {destinataire}")
    except Exception as e:
        print(f"❌ Erreur email : {e}")

st.title("📅 Téléchargement de données météo")

# ✅ Chargement des données
API_URL = "https://data-real-time-2.onrender.com/donnees?limit=50000000000"
data = requests.get(API_URL).json()
df = pd.DataFrame(data)

if df.empty:
    st.error("Aucune donnée disponible depuis l'API.")
    st.stop()

df["DateTime"] = pd.to_datetime(df["DateTime"])
df = df.sort_values("DateTime", ascending=False)

# ✅ Filtrage par date
st.sidebar.header("🗕️ Filtrer par date")
min_date = df["DateTime"].min().date()
max_date = df["DateTime"].max().date()
start_date, end_date = st.sidebar.date_input("Plage de dates", [min_date, max_date])
df = df[(df["DateTime"].dt.date >= start_date) & (df["DateTime"].dt.date <= end_date)]

# ✅ Formulaire utilisateur
st.subheader("📀 Demande de téléchargement")
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
            INSERT INTO demandes (id, nom, structure, email, raison, statut, token, timestamp)
            VALUES (?, ?, ?, ?, ?, 'en attente', NULL, NULL)
        ''', (demande_id, nom, structure, email, raison))
        conn.commit()
        st.success("✅ Demande envoyée. En attente de validation par l’administrateur.")

# ✅ Vérification automatique pour téléchargement
email_to_check = st.session_state.user_email
if email_to_check:
    cursor.execute('SELECT * FROM demandes WHERE email = ? AND statut = "acceptée"', (email_to_check,))
    row = cursor.fetchone()
    user_demande = None
    if row:
        _, _, _, _, _, _, _, timestamp = row
        if timestamp and time.time() - timestamp <= 300:
            user_demande = row
        else:
            cursor.execute("UPDATE demandes SET statut = 'expirée' WHERE email = ?", (email_to_check,))
            conn.commit()

    if user_demande:
        st.success("✅ Votre demande est acceptée. Vous avez 60 secondes pour télécharger.")
        export_cols = ["Station", "Latitude", "Longitude", "DateTime", "TIDE HEIGHT", "WIND SPEED", "WIND DIR",
                       "AIR PRESSURE", "AIR TEMPERATURE", "DEWPOINT", "HUMIDITY"]
        df_export = df[export_cols]
        csv = df_export.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📅 Télécharger les données météo",
            data=csv,
            file_name="MeteoMarinePAD.csv",
            mime="text/csv"
        )
    else:
        cursor.execute('SELECT * FROM demandes WHERE email = ? AND statut = "expirée"', (email_to_check,))
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
    st.sidebar.markdown("### 📅 Demandes en attente")
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
            cursor.execute("UPDATE demandes SET statut='acceptée', token=?, timestamp=? WHERE id=?",
                           (token, horo, demande_id))
            conn.commit()

            # ✅ Envoi de l’email avec lien personnalisé
            lien_app = f"https://sitepad-5.onrender.com/?email={email}"
            contenu_mail = f"""
            <html><body>
            <p>Bonjour {nom},</p>
            <p>Votre demande de téléchargement de données météo a été <b>acceptée</b> ✅.</p>
            <p>Vous avez <b>60 secondes</b> pour télécharger les données via le lien suivant :</p>
            <p><a href="{lien_app}" style="padding:10px 15px;background-color:#0A84FF;color:white;text-decoration:none;border-radius:5px;">Accéder à l'application</a></p>
            <p>Merci et à bientôt.</p>
            </body></html>
            """
            envoyer_email(email, "Votre demande de téléchargement a été acceptée", contenu_mail)
            st.sidebar.success(f"Acceptée + email envoyé à {email}")
        if col2.button(f"❌ Refuser {demande_id}", key=f"ref_{demande_id}"):
            cursor.execute("UPDATE demandes SET statut='refusée', timestamp=? WHERE id=?", (time.time(), demande_id))
            conn.commit()
            st.sidebar.warning(f"Refusée pour {nom}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Historique des décisions")
    cursor.execute("SELECT * FROM demandes WHERE statut IN ('acceptée', 'refusée')")
    demandes_traitees = cursor.fetchall()
    for d in demandes_traitees:
        _, nom, structure, email, raison, statut, _, ts = d
        couleur = "🟢" if statut == "acceptée" else "🔴"
        heure = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts and pd.notna(ts) else "Inconnu"
        st.sidebar.markdown(f"""
        {couleur} **{nom}**  
        📧 {email}  
        🏢 {structure}  
        📌 {raison}  
        🕒 {heure}
        """)
    cursor.execute("SELECT nom, email, structure, raison, statut, timestamp FROM demandes")
    export_data = cursor.fetchall()
    df_export = pd.DataFrame(export_data, columns=["nom", "email", "structure", "raison", "statut", "timestamp"])
    df_export["Horodatage"] = df_export["timestamp"].apply(
        lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if pd.notna(ts) else "")
    df_export = df_export.drop(columns=["timestamp"])
    st.sidebar.download_button(
        label="📄 Exporter l’historique",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name="historique_acces.csv",
        mime="text/csv"
    )
elif admin_password != "":
    st.sidebar.error("Mot de passe incorrect.")
