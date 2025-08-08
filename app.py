import streamlit as st
import pandas as pd
import io
import csv
import re
from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl import load_workbook

def get_csv_delimiter(file):
    """
    Détermine le délimiteur d'un fichier CSV.
    """
    try:
        # L'utilisation de file.read() consomme le fichier, il faut donc le replacer au début
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0)
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ','

def check_data(df):
    """
    Vérifie les données du DataFrame pour détecter les anomalies en utilisant des opérations vectorisées.
    Retourne un DataFrame avec les lignes contenant des anomalies.
    """
    df_with_anomalies = df.copy()

    # Vérification des colonnes requises
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre', 'Mode de relève']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Colonnes requises manquantes : {', '.join(missing_columns)}")
        st.stop()

    df_with_anomalies['Anomalie'] = ''

    # Conversion des colonnes pour les analyses et remplacement des NaN par des chaînes vides
    # Ajout de 'Mode de relève' pour s'assurer qu'il est bien une chaîne
    df_with_anomalies['Numéro de compteur'] = df_with_anomalies['Numéro de compteur'].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Numéro de tête'] = df_with_anomalies['Numéro de tête'].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Marque'] = df_with_anomalies['Marque'].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Protocole Radio'] = df_with_anomalies['Protocole Radio'].astype(str).replace('nan', '', regex=False)
    df_with_anomalies['Mode de relève'] = df_with_anomalies['Mode de relève'].astype(str).replace('nan', '', regex=False)
    
    # Conversion des colonnes Latitude et Longitude en numérique pour éviter le TypeError
    df_with_anomalies['Latitude'] = pd.to_numeric(df_with_anomalies['Latitude'], errors='coerce')
    df_with_anomalies['Longitude'] = pd.to_numeric(df_with_anomalies['Longitude'], errors='coerce')

    # Marqueurs pour les conditions
    is_kamstrup = df_with_anomalies['Marque'].str.upper() == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].str.upper().isin(['SAPPEL (C)', 'SAPPEL (H)'])
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    df_with_anomalies['Diametre'] = pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce')

    # ------------------------------------------------------------------
    # ANOMALIES GÉNÉRALES (valeurs manquantes et incohérences de base)
    # ------------------------------------------------------------------
    
    # Colonnes manquantes
    # Nouvelle règle de contrôle : ne pas considérer comme une anomalie si le protocole radio est manquant
    # ET le mode de relève est "Manuelle".
    condition_protocole_manquant = (df_with_anomalies['Protocole Radio'].isin(['', 'nan'])) & (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[condition_protocole_manquant, 'Anomalie'] += 'Protocole Radio manquant / '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isin(['', 'nan']), 'Anomalie'] += 'Marque manquante / '
    df_with_anomalies.loc[df_with_anomalies['Numéro de compteur'].isin(['', 'nan']), 'Anomalie'] += 'Numéro de compteur manquant / '
    df_with_anomalies.loc[df_with_anomalies['Diametre'].isnull(), 'Anomalie'] += 'Diamètre manquant / '
    df_with_anomalies.loc[annee_fabrication_num.isnull(), 'Anomalie'] += 'Année de fabrication manquante / '
    
    # Numéro de tête manquant (sauf pour SAPPEL avec année < 22)
    # ET la nouvelle condition pour "Mode de relève" Manuelle
    condition_tete_manquante = (df_with_anomalies['Numéro de tête'].isin(['', 'nan'])) & \
                               (~is_sappel | (annee_fabrication_num >= 22)) & \
                               (df_with_anomalies['Mode de relève'].str.upper() != 'MANUELLE')
    df_with_anomalies.loc[condition_tete_manquante, 'Anomalie'] += 'Numéro de tête manquant / '

    # Coordonnées
    # La conversion en numérique ci-dessus résout le TypeError ici
    df_with_anomalies.loc[df_with_anomalies['Latitude'].isnull() | df_with_anomalies['Longitude'].isnull(), 'Anomalie'] += 'Coordonnées GPS non numériques / '
    coord_invalid = ((df_with_anomalies['Latitude'] == 0) | (~df_with_anomalies['Latitude'].between(-90, 90))) | \
                    ((df_with_anomalies['Longitude'] == 0) | (~df_with_anomalies['Longitude'].between(-180, 180)))
    df_with_anomalies.loc[coord_invalid, 'Anomalie'] += 'Coordonnées GPS invalides / '

    # ------------------------------------------------------------------
    # ANOMALIES SPÉCIFIQUES AUX MARQUES
    # ------------------------------------------------------------------
    
    # KAMSTRUP
    kamstrup_valid = is_kamstrup & (~df_with_anomalies['Numéro de tête'].isin(['', 'nan']))
    df_with_anomalies.loc[is_kamstrup & (df_with_anomalies['Numéro de compteur'].str.len() != 8), 'Anomalie'] += 'KAMSTRUP: Compteur ≠ 8 caractères / '
    df_with_anomalies.loc[kamstrup_valid & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête']), 'Anomalie'] += 'KAMSTRUP: Compteur ≠ Tête / '
    df_with_anomalies.loc[kamstrup_valid & (~df_with_anomalies['Numéro de compteur'].str.isdigit() | ~df_with_anomalies['Numéro de tête'].str.isdigit()), 'Anomalie'] += 'KAMSTRUP: Compteur ou Tête non numérique / '
    df_with_anomalies.loc[is_kamstrup & (~df_with_anomalies['Diametre'].between(15, 80)), 'Anomalie'] += 'KAMSTRUP: Diamètre hors plage / '
    df_with_anomalies.loc[is_kamstrup & (df_with_anomalies['Protocole Radio'].str.upper() != 'WMS'), 'Anomalie'] += 'KAMSTRUP: Protocole ≠ WMS / '

    # SAPPEL
    # Correction: Assurez-vous que la colonne est de type str avant d'appliquer .str.startswith()
    sappel_valid_tete_dme = is_sappel & (df_with_anomalies['Numéro de tête'].astype(str).str.upper().str.startswith('DME'))
    df_with_anomalies.loc[sappel_valid_tete_dme & (df_with_anomalies['Numéro de tête'].str.len() != 15), 'Anomalie'] += 'SAPPEL: Tête DME ≠ 15 caractères / '
    df_with_anomalies.loc[is_sappel & (~df_with_anomalies['Numéro de compteur'].str.match(r'^[A-Z]{1}\d{2}[A-Z]{2}\d{6}$')), 'Anomalie'] += 'SAPPEL: Compteur format incorrect / '
    df_with_anomalies.loc[is_sappel & (~df_with_anomalies['Numéro de compteur'].str.startswith(('C', 'H'))), 'Anomalie'] += 'SAPPEL: Compteur ne commence pas par C ou H / '
    df_with_anomalies.loc[(is_sappel) & (df_with_anomalies['Numéro de compteur'].str.startswith('C')) & (df_with_anomalies['Marque'].str.upper() != 'SAPPEL (C)'), 'Anomalie'] += 'SAPPEL: Incohérence Marque/Compteur (C) / '
    df_with_anomalies.loc[(is_sappel) & (df_with_anomalies['Numéro de compteur'].str.startswith('H')) & (df_with_anomalies['Marque'].str.upper() != 'SAPPEL (H)'), 'Anomalie'] += 'SAPPEL: Incohérence Marque/Compteur (H) / '
    df_with_anomalies.loc[is_sappel & (annee_fabrication_num > 22) & (~df_with_anomalies['Numéro de tête'].astype(str).str.upper().str.startswith('DME')), 'Anomalie'] += 'SAPPEL: Année >22 & Tête ≠ DME / '
    df_with_anomalies.loc[is_sappel & (annee_fabrication_num > 22) & (df_with_anomalies['Protocole Radio'].str.upper() != 'OMS'), 'Anomalie'] += 'SAPPEL: Année >22 & Protocole ≠ OMS / '

    # Règle de diamètre FP2E (pour SAPPEL)
    fp2e_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': 60, 'G': 65, 'H': 80, 'I': 100, 'J': 125, 'K': 150}

    def check_fp2e_vectorized(row):
        try:
            compteur = row['Numéro de compteur']
            annee_compteur = compteur[1:3]
            annee_fabrication = str(int(row['Année de fabrication'])) if pd.notna(row['Année de fabrication']) else ''
            if len(annee_fabrication) < 2 or annee_compteur != annee_fabrication[-2:]:
                return False
            
            lettre_diam = compteur[4].upper()
            return fp2e_map.get(lettre_diam, None) == row['Diametre']
        except:
            return False

    sappel_fp2e_condition = is_sappel & (df_with_anomalies['Numéro de compteur'].str.len() >= 5) & (df_with_anomalies['Diametre'].notnull())
    fp2e_anomalies = df_with_anomalies[sappel_fp2e_condition].apply(lambda row: not check_fp2e_vectorized(row), axis=1)
    df_with_anomalies.loc[sappel_fp2e_condition & fp2e_anomalies, 'Anomalie'] += 'SAPPEL: non conforme FP2E / '

    # Nettoyage de la colonne 'Anomalie'
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
    
    anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != ''].copy()
    anomalies_df.reset_index(inplace=True)
    anomalies_df.rename(columns={'index': 'Index original'}, inplace=True)
    
    # Comptage des anomalies pour le résumé
    anomaly_counter = anomalies_df['Anomalie'].str.split(' / ').explode().value_counts()
    
    return anomalies_df, anomaly_counter

def afficher_resume_anomalies(anomaly_counter):
    """
    Affiche un résumé des anomalies.
    """
    if not anomaly_counter.empty:
        summary_df = pd.DataFrame(anomaly_counter).reset_index()
        summary_df.columns = ["Type d'anomalie", "Nombre de cas"]
        st.subheader("Récapitulatif des anomalies")
        st.dataframe(summary_df)

# --- Interface Streamlit ---
st.title("Contrôle des données de Radiorelève")
st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success("Fichier chargé avec succès !")

    try:
        file_extension = uploaded_file.name.split('.')[-1]
        
        # Définir le type de données pour les colonnes pour éviter la notation scientifique
        dtype_mapping = {
            'Numéro de branchement': str,
            'Abonnement': str
        }

        if file_extension == 'csv':
            delimiter = get_csv_delimiter(uploaded_file)
            # Lecture du fichier avec la conversion de type pour éviter la notation scientifique
            df = pd.read_csv(uploaded_file, sep=delimiter, dtype=dtype_mapping)
        elif file_extension == 'xlsx':
            # Lecture du fichier avec la conversion de type pour éviter la notation scientifique
            df = pd.read_excel(uploaded_file, dtype=dtype_mapping)
        else:
            st.error("Format de fichier non pris en charge. Veuillez utiliser un fichier .csv ou .xlsx.")
            st.stop()
    except Exception as e:
        st.error(f"Erreur de lecture du fichier : {e}")
        st.stop()

    st.subheader("Aperçu des 5 premières lignes")
    st.dataframe(df.head())

    if st.button("Lancer les contrôles"):
        st.write("Contrôles en cours...")
        anomalies_df, anomaly_counter = check_data(df)

        if not anomalies_df.empty:
            st.error("Anomalies détectées !")
            st.dataframe(anomalies_df)
            afficher_resume_anomalies(anomaly_counter)
            
            # Dictionnaire pour mapper les anomalies aux colonnes
            anomaly_columns_map = {
                "Protocole Radio manquant": ['Protocole Radio'],
                "Marque manquante": ['Marque'],
                "Numéro de compteur manquant": ['Numéro de compteur'],
                "Numéro de tête manquant": ['Numéro de tête'],
                "Coordonnées GPS non numériques": ['Latitude', 'Longitude'],
                "Coordonnées GPS invalides": ['Latitude', 'Longitude'],
                "Diamètre manquant": ['Diametre'],
                "Année de fabrication manquante": ['Année de fabrication'],
                
                # Anomalies spécifiques
                "KAMSTRUP: Compteur ≠ 8 caractères": ['Numéro de compteur'],
                "KAMSTRUP: Compteur ≠ Tête": ['Numéro de compteur', 'Numéro de tête'],
                "KAMSTRUP: Compteur ou Tête non numérique": ['Numéro de compteur', 'Numéro de tête'],
                "KAMSTRUP: Diamètre hors plage": ['Diametre'],
                "KAMSTRUP: Protocole ≠ WMS": ['Protocole Radio'],
                "SAPPEL: Tête DME ≠ 15 caractères": ['Numéro de tête'],
                "SAPPEL: Compteur format incorrect": ['Numéro de compteur'],
                "SAPPEL: Compteur ne commence pas par C ou H": ['Numéro de compteur'],
                "SAPPEL: Incohérence Marque/Compteur (C)": ['Marque', 'Numéro de compteur'],
                "SAPPEL: Incohérence Marque/Compteur (H)": ['Marque', 'Numéro de compteur'],
                "SAPPEL: Année >22 & Tête ≠ DME": ['Année de fabrication', 'Numéro de tête'],
                "SAPPEL: Année >22 & Protocole ≠ OMS": ['Année de fabrication', 'Protocole Radio'],
                "SAPPEL: non conforme FP2E": ['Numéro de compteur', 'Diametre', 'Année de fabrication'],
            }

            if file_extension == 'csv':
                csv_file = anomalies_df.to_csv(index=False, sep=delimiter).encode('utf-8')
                st.download_button("Télécharger les anomalies en CSV", csv_file, "anomalies_radioreleve.csv", "text/csv")
            elif file_extension == 'xlsx':
                excel_buffer = io.BytesIO()
                
                # Exporte uniquement le DataFrame des anomalies vers Excel
                anomalies_df.to_excel(excel_buffer, index=False, sheet_name='Anomalies', engine='openpyxl')
                excel_buffer.seek(0)
                
                wb = load_workbook(excel_buffer)
                ws = wb.active
                
                # J'ai changé la couleur ici pour un rouge plus clair
                red_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')

                # Utilisation d'un simple compteur 'i' pour correspondre aux lignes du fichier Excel de sortie
                for i, row in enumerate(anomalies_df.iterrows()):
                    anomalies = str(row[1]['Anomalie']).split(' / ')
                    for anomaly in anomalies:
                        anomaly_key = anomaly.strip()
                        if anomaly_key in anomaly_columns_map:
                            columns_to_highlight = anomaly_columns_map[anomaly_key]
                            for col_name in columns_to_highlight:
                                try:
                                    col_index = list(anomalies_df.columns).index(col_name) + 1
                                    # La ligne dans le fichier Excel est le compteur 'i' + 2 (pour l'en-tête)
                                    cell = ws.cell(row=i + 2, column=col_index)
                                    cell.fill = red_fill
                                except ValueError:
                                    pass
                                
                excel_buffer_styled = io.BytesIO()
                wb.save(excel_buffer_styled)
                excel_buffer_styled.seek(0)

                st.download_button("Télécharger les anomalies en Excel", excel_buffer_styled, "anomalies_radioreleve.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.success("Aucune anomalie détectée. Les données sont conformes.")
