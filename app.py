import streamlit as st
import pandas as pd
import io
import csv

@st.cache_data
def get_csv_delimiter(file):
    """Détecte le délimiteur d'un fichier CSV."""
    try:
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0)
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ','

def check_data(df):
    """
    Effectue tous les contrôles sur le DataFrame et retourne un DataFrame avec les anomalies.
    """
    df_with_anomalies = df.copy()
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre']
    
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Votre fichier ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_columns)}")
        st.stop()
    
    anomalies_list = []
    
    # Dictionnaire de correspondance des diamètres pour la loi FP2E
    diameter_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': 60, 'H': 80, 'I': 100, 'J': 125, 'K': 150}

    # Nettoyage des données pour les comparaisons
    for col in required_columns:
        if pd.api.types.is_string_dtype(df_with_anomalies[col]):
            df_with_anomalies[col] = df_with_anomalies[col].str.strip()
    
    for index, row in df_with_anomalies.iterrows():
        anomalies_row = []
        
        # Conditions de base
        if pd.isnull(row['Protocole Radio']):
            anomalies_row.append('Protocole Radio vide')
        if pd.isnull(row['Marque']):
            anomalies_row.append('Marque vide')
        if pd.isnull(row['Latitude']):
            anomalies_row.append('Latitude vide')
        elif row['Latitude'] == 0:
            anomalies_row.append('Latitude = 0')
        elif not (-90 <= row['Latitude'] <= 90):
            anomalies_row.append('Latitude invalide')
        if pd.isnull(row['Longitude']):
            anomalies_row.append('Longitude vide')
        elif row['Longitude'] == 0:
            anomalies_row.append('Longitude = 0')
        elif not (-180 <= row['Longitude'] <= 180):
            anomalies_row.append('Longitude invalide')
        
        # Règle spéciale pour Numéro de tête vide (Sappel avec année < 22)
        is_sappel = row['Marque'] in ['SAPPEL (C)', 'SAPPEL (H)']
        annee_fabrication_num = pd.to_numeric(row['Année de fabrication'], errors='coerce')
        if pd.isnull(row['Numéro de tête']):
            if not (is_sappel and annee_fabrication_num < 22):
                anomalies_row.append('Numéro de tête vide')
        
        # Contrôles spécifiques aux marques
        if row['Marque'] == 'KAMSTRUP':
            if pd.isnull(row['Numéro de compteur']) or len(str(row['Numéro de compteur'])) != 8:
                anomalies_row.append("Numéro de compteur KAMSTRUP invalide (longueur)")
            if not pd.isnull(row['Numéro de tête']) and row['Numéro de compteur'] != row['Numéro de tête']:
                anomalies_row.append("KAMSTRUP: Numéros de compteur et tête différents")
            if not pd.isnull(row['Numéro de compteur']) and not str(row['Numéro de compteur']).isdigit():
                anomalies_row.append("KAMSTRUP: Numéro de compteur non numérique")
            if not pd.isnull(row['Numéro de tête']) and not str(row['Numéro de tête']).isdigit():
                anomalies_row.append("KAMSTRUP: Numéro de tête non numérique")
            if not pd.to_numeric(row['Diametre'], errors='coerce') in range(15, 81):
                anomalies_row.append("KAMSTRUP: Diamètre hors-plage")
            if row['Protocole Radio'] != 'WMS':
                anomalies_row.append("KAMSTRUP: Protocole Radio n'est pas WMS")
        
        if is_sappel:
            # Règle 5
            if not pd.isnull(row['Numéro de tête']) and str(row['Numéro de tête']).startswith('DME') and len(str(row['Numéro de tête'])) != 15:
                anomalies_row.append("Sappel: Numéro de tête DME invalide (longueur)")
            
            # Règle 6
            if not pd.isnull(row['Numéro de compteur']) and not pd.Series(str(row['Numéro de compteur'])).str.match(r'^[a-zA-Z]\d{2}[a-zA-Z]{2}\d{6}$').iloc[0]:
                anomalies_row.append("Sappel: Numéro de compteur format invalide")
            
            # Règle 7
            if not pd.isnull(row['Numéro de compteur']) and not str(row['Numéro de compteur']).startswith(('C', 'H')):
                anomalies_row.append("Sappel: Numéro de compteur doit commencer par C ou H")
            
            # Règle 8
            if (str(row['Numéro de compteur']).startswith('C') and row['Marque'] != 'SAPPEL (C)') or \
               (str(row['Numéro de compteur']).startswith('H') and row['Marque'] != 'SAPPEL (H)'):
                anomalies_row.append("Incohérence Numéro de compteur / Marque")
            
            # Règle 10a
            if annee_fabrication_num > 22 and not pd.isnull(row['Numéro de tête']) and not str(row['Numéro de tête']).startswith('DME'):
                anomalies_row.append("Sappel: Année > 22 sans Numéro de tête DME")
            
            # Règle 10b
            if annee_fabrication_num > 22 and row['Protocole Radio'] != 'OMS':
                anomalies_row.append("Sappel: Année > 22 sans Protocole Radio OMS")
            
            # Règle FP2E
            compteur = str(row['Numéro de compteur'])
            annee = str(row['Année de fabrication'])
            diametre = pd.to_numeric(row['Diametre'], errors='coerce')
            
            if not (pd.isnull(compteur) or len(compteur) < 5 or pd.isnull(annee) or pd.isnull(diametre)):
                first_letter_ok = (row['Marque'] == 'SAPPEL (C)' and compteur.startswith('C')) or (row['Marque'] == 'SAPPEL (H)' and compteur.startswith('H'))
                year_ok = compteur[1:3] == annee[-2:]
                
                lettre_diam = compteur[4].upper()
                expected_diametre = diameter_map.get(lettre_diam)
                
                diameter_ok = False
                if expected_diametre is not None:
                    if isinstance(expected_diametre, list):
                        diameter_ok = diametre in expected_diametre
                    else:
                        diameter_ok = diametre == expected_diametre
                
                if not first_letter_ok or not year_ok or not diameter_ok:
                    anomalies_row.append("Sappel: Non conforme à la loi FP2E")

        if anomalies_row:
            df_with_anomalies.loc[index, 'Anomalie'] = ' / '.join(anomalies_row)
            
    return df_with_anomalies[df_with_anomalies['Anomalie'] != '']

def app_logic():
    st.title("Contrôle des données de Radiorelève")
    st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

    uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

    if 'anomalies_df' not in st.session_state:
        st.session_state['anomalies_df'] = pd.DataFrame()
    if 'df' not in st.session_state:
        st.session_state['df'] = pd.DataFrame()
    if 'file_extension' not in st.session_state:
        st.session_state['file_extension'] = None
    
    if uploaded_file:
        try:
            file_extension = uploaded_file.name.split('.')[-1]
            st.session_state['file_extension'] = file_extension
            if file_extension == 'csv':
                delimiter = get_csv_delimiter(uploaded_file)
                st.session_state['df'] = pd.read_csv(uploaded_file, sep=delimiter)
            elif file_extension == 'xlsx':
                st.session_state['df'] = pd.read_excel(uploaded_file)
            else:
                st.error("Format de fichier non pris en charge.")
                st.stop()
            st.success("Fichier chargé avec succès !")
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier : {e}")
            st.stop()
        
        st.subheader("Aperçu des 5 premières lignes")
        st.dataframe(st.session_state['df'].head())
        
        if st.button("Lancer les contrôles"):
            with st.spinner('Contrôles en cours...'):
                st.session_state['anomalies_df'] = check_data(st.session_state['df'])

    if not st.session_state['anomalies_df'].empty:
        st.error("Anomalies détectées !")
        st.subheader("Résumé des anomalies")
        anomaly_counts = st.session_state['anomalies_df']['Anomalie'].str.split(' / ').explode().value_counts().rename_axis('Type d\'anomalie').reset_index(name='Nombre')
        st.dataframe(anomaly_counts)
        st.subheader("Tableau complet des anomalies")
        st.dataframe(st.session_state['anomalies_df'])
        
        if st.session_state['file_extension'] == 'csv':
            delimiter = get_csv_delimiter(uploaded_file)
            csv_file = st.session_state['anomalies_df'].to_csv(index=False, sep=delimiter).encode('utf-8')
            st.download_button(label="Télécharger les anomalies en CSV", data=csv_file, file_name='anomalies_radioreleve.csv', mime='text/csv')
        elif st.session_state['file_extension'] == 'xlsx':
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                st.session_state['anomalies_df'].to_excel(writer, index=False, sheet_name='Anomalies')
            excel_buffer.seek(0)
            st.download_button(label="Télécharger les anomalies en Excel", data=excel_buffer, file_name='anomalies_radioreleve.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    elif uploaded_file:
        st.info("Cliquez sur 'Lancer les contrôles' pour démarrer l'analyse.")

app_logic()
