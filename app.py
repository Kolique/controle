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

    df_with_anomalies['Anomalie'] = ''
    is_kamstrup = df_with_anomalies['Marque'] == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].isin(['SAPPEL (C)', 'SAPPEL (H)'])
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')

    # Nettoyage des données pour les comparaisons
    for col in required_columns:
        if pd.api.types.is_string_dtype(df_with_anomalies[col]):
            df_with_anomalies[col] = df_with_anomalies[col].str.strip()

    # --- Contrôles de base (vides, valeurs hors-plage) ---
    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Protocole Radio vide / '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Marque vide / '
    df_with_anomalies.loc[df_with_anomalies['Latitude'].isnull(), 'Anomalie'] += 'Latitude vide / '
    df_with_anomalies.loc[df_with_anomalies['Longitude'].isnull(), 'Anomalie'] += 'Longitude vide / '
    df_with_anomalies.loc[~df_with_anomalies['Latitude'].isnull() & ~df_with_anomalies['Latitude'].between(-90, 90, inclusive='both'), 'Anomalie'] += 'Latitude invalide / '
    df_with_anomalies.loc[~df_with_anomalies['Longitude'].isnull() & ~df_with_anomalies['Longitude'].between(-180, 180, inclusive='both'), 'Anomalie'] += 'Longitude invalide / '
    
    # Règle spéciale pour Numéro de tête vide (Sappel avec année < 22)
    condition_num_tete_vide_anomale = (df_with_anomalies['Numéro de tête'].isnull()) & (~is_sappel | (annee_fabrication_num >= 22))
    df_with_anomalies.loc[condition_num_tete_vide_anomale, 'Anomalie'] += 'Numéro de tête vide / '
    
    # --- Contrôles spécifiques aux marques ---
    
    # KAMSTRUP : Numéro de compteur a une longueur != 8
    kamstrup_len_condition = is_kamstrup & ~df_with_anomalies['Numéro de compteur'].isnull() & (df_with_anomalies['Numéro de compteur'].astype(str).str.len() != 8)
    df_with_anomalies.loc[kamstrup_len_condition, 'Anomalie'] += "Numéro de compteur KAMSTRUP invalide (longueur) / "
    
    # KAMSTRUP : Numéro de compteur != Numéro de tête
    kamstrup_num_diff_condition = is_kamstrup & ~df_with_anomalies['Numéro de tête'].isnull() & ~df_with_anomalies['Numéro de compteur'].isnull() & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête'])
    df_with_anomalies.loc[kamstrup_num_diff_condition, 'Anomalie'] += "KAMSTRUP: Numéros de compteur et tête différents / "
    
    # KAMSTRUP : Numéro de compteur ou tête contient une lettre
    num_compteur_is_digit = df_with_anomalies['Numéro de compteur'].astype(str).str.isdigit()
    num_tete_is_digit = df_with_anomalies['Numéro de tête'].astype(str).str.isdigit()
    kamstrup_digit_condition = is_kamstrup & (~num_compteur_is_digit | ~num_tete_is_digit)
    df_with_anomalies.loc[kamstrup_digit_condition, 'Anomalie'] += "KAMSTRUP: Numéro de compteur ou tête non numérique / "
    
    # KAMSTRUP : Diamètre hors de la plage
    kamstrup_diam_condition = is_kamstrup & ~pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce').between(15, 80, inclusive='both')
    df_with_anomalies.loc[kamstrup_diam_condition, 'Anomalie'] += "KAMSTRUP: Diamètre hors-plage / "
    
    # KAMSTRUP : Protocole Radio non 'WMS'
    kamstrup_proto_condition = is_kamstrup & (df_with_anomalies['Protocole Radio'] != 'WMS')
    df_with_anomalies.loc[kamstrup_proto_condition, 'Anomalie'] += "KAMSTRUP: Protocole Radio n'est pas WMS / "
    
    # SAPPEL : Numéro de tête (DME) n'a pas 15 caractères
    sappel_dme_condition = is_sappel & df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME') & (df_with_anomalies['Numéro de tête'].astype(str).str.len() != 15)
    df_with_anomalies.loc[sappel_dme_condition, 'Anomalie'] += "Sappel: Numéro de tête DME invalide (longueur) / "
    
    # SAPPEL : Numéro de compteur ne respecte pas le format
    regex_sappel_compteur = r'^[a-zA-Z]\d{2}[a-zA-Z]{2}\d{6}$'
    sappel_format_condition = is_sappel & ~df_with_anomalies['Numéro de compteur'].isnull() & (~df_with_anomalies['Numéro de compteur'].astype(str).str.match(regex_sappel_compteur))
    df_with_anomalies.loc[sappel_format_condition, 'Anomalie'] += "Sappel: Numéro de compteur format invalide / "
    
    # SAPPEL : Numéro de compteur ne commence ni par 'C' ni par 'H'
    sappel_first_char_condition = is_sappel & ~df_with_anomalies['Numéro de compteur'].isnull() & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H'))
    df_with_anomalies.loc[sappel_first_char_condition, 'Anomalie'] += "Sappel: Numéro de compteur doit commencer par C ou H / "
    
    # SAPPEL : Incohérence Numéro de compteur / Marque
    sappel_marque_condition = ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (df_with_anomalies['Marque'] != 'SAPPEL (C)')) | \
                              ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H')) & (df_with_anomalies['Marque'] != 'SAPPEL (H)'))
    df_with_anomalies.loc[sappel_marque_condition, 'Anomalie'] += "Incohérence Numéro de compteur / Marque / "

    # SAPPEL : Année > 22 sans Numéro de tête DME
    sappel_annee_dme_condition = is_sappel & (annee_fabrication_num > 22) & (~df_with_anomalies['Numéro de tête'].isnull()) & (~df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME'))
    df_with_anomalies.loc[sappel_annee_dme_condition, 'Anomalie'] += "Sappel: Année > 22 sans Numéro de tête DME / "
    
    # SAPPEL : Année > 22 sans Protocole OMS
    sappel_annee_proto_condition = is_sappel & (annee_fabrication_num > 22) & (df_with_anomalies['Protocole Radio'] != 'OMS')
    df_with_anomalies.loc[sappel_annee_proto_condition, 'Anomalie'] += "Sappel: Année > 22 sans Protocole Radio OMS / "

    # RÈGLE FP2E
    diameter_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': 60, 'H': 80, 'I': 100, 'J': 125, 'K': 150}

    def check_fp2e(row):
        try:
            compteur = str(row['Numéro de compteur'])
            marque = row['Marque']
            annee = str(row['Année de fabrication'])
            diametre = pd.to_numeric(row['Diametre'], errors='coerce')
            
            if pd.isnull(compteur) or len(compteur) < 5 or pd.isnull(annee) or pd.isnull(diametre):
                return True

            # 1. Première lettre
            if (marque == 'SAPPEL (C)' and not compteur.startswith('C')) or (marque == 'SAPPEL (H)' and not compteur.startswith('H')):
                return True

            # 2. Année
            if compteur[1:3] != annee[-2:]:
                return True

            # 3. Diamètre
            lettre_diam = compteur[4].upper()
            expected_diametre = fp2e_map.get(lettre_diam)
            
            if isinstance(expected_diametre, list):
                if diametre not in expected_diametre:
                    return True
            elif diametre != expected_diametre:
                return True

            return False # Aucune anomalie détectée
        except (IndexError, ValueError):
            return True # Anomalie si le format est invalide

    fp2e_not_respected = is_sappel & df_with_anomalies.apply(check_fp2e, axis=1)
    df_with_anomalies.loc[fp2e_not_respected, 'Anomalie'] += "Sappel: Non conforme à la loi FP2E / "

    # Nettoyage final
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
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
