import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

st.set_page_config(page_title="Contrôle Compteurs FP2E", layout="wide")
st.title("\U0001F50D Contrôle de cohérence des compteurs (FP2E)")

# Fonction de détection des anomalies
def check_data(df):
    anomalies = []
    for _, row in df.iterrows():
        row_anomalies = []

        # Données manquantes
        missing_fields = []
        for field in ["Protocole Radio", "Marque", "Numéro de compteur"]:
            if pd.isna(row.get(field, None)) or str(row.get(field)).strip() == "":
                missing_fields.append(field)
        if missing_fields:
            row_anomalies.append("Données manquantes : " + ", ".join(missing_fields))

        # GPS invalides
        lat = row.get("Latitude", None)
        lon = row.get("Longitude", None)
        if (lat == 0 or lon == 0 or pd.isna(lat) or pd.isna(lon)):
            row_anomalies.append("Coordonnées GPS invalides")

        marque = str(row.get("Marque", "")).upper()
        num = str(row.get("Numéro de compteur", "")).strip()
        protocole = str(row.get("Protocole Radio", "")).strip().upper()
        tete = str(row.get("Numéro de tête", "")).strip()

        # Loi FP2E (SAPPEL ou ITRON)
        if marque in ["SAPPEL (C)", "SAPPEL (H)", "ITRON"] and len(num) >= 5:
            fp2e_issue = False
            if marque == "SAPPEL (C)" and not num.startswith("C"):
                fp2e_issue = True
            elif marque == "SAPPEL (H)" and not num.startswith("H"):
                fp2e_issue = True
            else:
                annee = num[1:3]
                code_diam = num[4]
                if not annee.isdigit() or code_diam.upper() not in "AUYZBCDEFGHIJK":
                    fp2e_issue = True

            if marque.startswith("SAPPEL") and annee.isdigit() and int(annee) > 22:
                if not tete.startswith("DME") or protocole != "OMS":
                    fp2e_issue = True

            if fp2e_issue:
                row_anomalies.append("Loi FP2E non respectée")

        # KAMSTRUP
        if marque == "KAMSTRUP":
            if any(c.isalpha() for c in num):
                row_anomalies.append("KAMSTRUP: Numéro compteur contient des lettres")
            if num != tete:
                row_anomalies.append("KAMSTRUP: Numéro compteur ≠ Numéro tête")

        anomalies.append(row_anomalies)

    df["Anomalie"] = [" / ".join(msgs) if msgs else "" for msgs in anomalies]
    return df, anomalies

# Fonction pour générer l'Excel avec mises en forme
def generate_excel_with_highlights(df, anomalies_list):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Anomalies')
    workbook = writer.book
    worksheet = writer.sheets['Anomalies']

    red_fill = PatternFill(start_color='FFFF0000', end_color='FFFF0000', fill_type='solid')

    for idx, anomaly_msgs in enumerate(anomalies_list):
        for msg in anomaly_msgs:
            # Coordonnées GPS invalides
            if "Coordonnées GPS invalides" in msg:
                for col in ["Latitude", "Longitude"]:
                    if col in df.columns:
                        col_idx = df.columns.get_loc(col) + 1
                        worksheet.cell(row=idx+2, column=col_idx).fill = red_fill
            # Données manquantes
            if "Données manquantes" in msg:
                champs = msg.replace("Données manquantes : ", "").split(", ")
                for field in champs:
                    if field in df.columns:
                        col_idx = df.columns.get_loc(field) + 1
                        worksheet.cell(row=idx+2, column=col_idx).fill = red_fill
            # Loi FP2E non respectée
            if "Loi FP2E non respectée" in msg:
                for field in ["Numéro de compteur", "Numéro de tête", "Protocole Radio"]:
                    if field in df.columns:
                        col_idx = df.columns.get_loc(field) + 1
                        worksheet.cell(row=idx+2, column=col_idx).fill = red_fill
            # KAMSTRUP
            if "KAMSTRUP" in msg:
                for field in ["Numéro de compteur", "Numéro de tête"]:
                    if field in df.columns:
                        col_idx = df.columns.get_loc(field) + 1
                        worksheet.cell(row=idx+2, column=col_idx).fill = red_fill

    writer.close()
    output.seek(0)
    return output

# Interface utilisateur
uploaded_file = st.file_uploader("Choisissez un fichier Excel avec les données à vérifier", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("Fichier chargé avec succès. Cliquez sur le bouton pour lancer le contrôle.")

    if st.button("Lancer les contrôles"):
        df_result, anomalies_list = check_data(df)
        anomalies_df = df_result[df_result["Anomalie"] != ""]

        if not anomalies_df.empty:
            st.warning(f"{len(anomalies_df)} ligne(s) présentent des anomalies.")
            st.dataframe(anomalies_df)

            output_file = generate_excel_with_highlights(df_result, anomalies_list)
            st.download_button("⬇ Télécharger le fichier avec anomalies", data=output_file,
                               file_name="anomalies_detectees.xlsx")
        else:
            st.success("Aucune anomalie détectée dans le fichier !")
