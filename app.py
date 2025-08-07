import streamlit as st
import pandas as pd

st.set_page_config(page_title="Contrôle des compteurs", layout="wide")
st.title("🧪 Vérification des données compteurs")

uploaded_file = st.file_uploader("Chargez votre fichier Excel", type=["xlsx"])

def check_data(df):
    anomalies = []

    def add_anomaly(index, message):
        anomalies[index].append(message)

    for index, row in df.iterrows():
        anomalies.append([])

        # Données essentielles manquantes
        champs_vides = []
        for champ in ['Marque', 'Protocole Radio', 'Numéro de compteur', 'Latitude', 'Longitude']:
            if pd.isna(row[champ]) or row[champ] == "":
                champs_vides.append(champ)
        if champs_vides:
            add_anomaly(index, "Données manquantes : " + ", ".join(champs_vides))

        # GPS = 0 ou invalides
        if row['Latitude'] == 0 or row['Longitude'] == 0:
            add_anomaly(index, "Coordonnées GPS invalides")

        # FP2E pour SAPPEL / ITRON
        marque = str(row['Marque']).upper()
        numero = str(row['Numéro de compteur'])
        protocole = str(row['Protocole Radio']).upper()
        tete = str(row.get('Numéro de tête', ''))
        fp2e_erreur = False

        if marque in ['SAPPEL (C)', 'SAPPEL (H)', 'ITRON']:
            if not numero:
                fp2e_erreur = True
            else:
                if marque == 'SAPPEL (C)' and not numero.startswith('C'):
                    fp2e_erreur = True
                if marque == 'SAPPEL (H)' and not numero.startswith('H'):
                    fp2e_erreur = True
                if marque == 'ITRON' and not numero.startswith('H'):
                    fp2e_erreur = True
            # Année fabrication = 2e et 3e caractères
            try:
                annee = int(numero[1:3])
                if annee > 22:
                    if not tete.startswith("DME"):
                        fp2e_erreur = True
                    if protocole != "OMS":
                        fp2e_erreur = True
                    if len(numero) >= 5:
                        lettre_diametre = numero[4]
                        if lettre_diametre.upper() not in ['A', 'U', 'Y', 'Z', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K']:
                            fp2e_erreur = True
                    else:
                        fp2e_erreur = True
            except:
                fp2e_erreur = True

            if fp2e_erreur:
                add_anomaly(index, "Loi FP2E non respectée")

        # Marque KAMSTRUP
        if marque == 'KAMSTRUP':
            if any(c.isalpha() for c in numero) or any(c.isalpha() for c in tete):
                add_anomaly(index, "KAMSTRUP : Numéros non numériques")
            if numero != tete:
                add_anomaly(index, "KAMSTRUP : tête ≠ compteur")

    # Fusion avec le DataFrame original
    df_with_anomalies = df.copy()
    df_with_anomalies["Anomalie"] = [" / ".join(set(msgs)) for msgs in anomalies]
    df_with_anomalies = df_with_anomalies[df_with_anomalies['Anomalie'] != ""]

    return df_with_anomalies

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("Fichier chargé avec succès !")
    if st.button("Lancer les contrôles"):
        anomalies_df = check_data(df)

        if anomalies_df.empty:
            st.success("✅ Aucune anomalie détectée !")
        else:
            st.warning(f"🚨 {len(anomalies_df)} lignes avec anomalies détectées")
            st.dataframe(anomalies_df)

            # Téléchargement
            @st.cache_data
            def convert_df(df):
                return df.to_excel(index=False, engine='openpyxl')

            st.download_button(
                label="📥 Télécharger les anomalies en Excel",
                data=convert_df(anomalies_df),
                file_name="anomalies_detectées.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
