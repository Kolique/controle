import streamlit as st
import pandas as pd
import io
import csv

def get_csv_delimiter(file):
    """
    Détermine le délimiteur d'un fichier CSV.
    """
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
    Vérifie les données du DataFrame et ajoute une colonne 'Anomalie'.
    """
    df_with_anomalies = df.copy()
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre']
    
    # Vérification des colonnes requises
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Colonnes manquantes : {', '.join(missing_columns)}")
        st.stop()

    df_with_anomalies['Anomalie'] = ''
    
    # Conversion des colonnes pour les analyses
    df_with_anomalies['Numéro de compteur'] = df_with_anomalies['Numéro de compteur'].astype(str)
    df_with_anomalies['Numéro de tête'] = df_with_anomalies['Numéro de tête'].astype(str)
    
    # Marqueurs pour les conditions
    is_kamstrup = df_with_anomalies['Marque'] == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].isin(['SAPPEL (C)', 'SAPPEL (H)'])
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    
    # Anomalies simples (colonnes manquantes)
    # Correction: Utilisation de .str.lower() pour être insensible à la casse
    df_with_anomalies.loc[df_with_anomalies['Numéro de compteur'].str.lower() == 'nan', 'Anomalie'] += 'Numéro de compteur manquant / '
    
    # Correction de l'erreur TypeError : les conditions sont bien parenthésées
    condition_num_tete_manquant = (df_with_anomalies['Numéro de tête'].str.lower() == 'nan') & (~is_sappel | (annee_fabrication_num >= 22))
    df_with_anomalies.loc[condition_num_tete_manquant, 'Anomalie'] += 'Numéro de tête manquant / '

    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Protocole manquant / '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Marque manquante / '
    
    # Coordonnées
    df_with_anomalies['Latitude'] = pd.to_numeric(df_with_anomalies['Latitude'], errors='coerce')
    df_with_anomalies['Longitude'] = pd.to_numeric(df_with_anomalies['Longitude'], errors='coerce')
    coord_invalid = ((df_with_anomalies['Latitude'] == 0) | (~df_with_anomalies['Latitude'].between(-90, 90))) | \
                    ((df_with_anomalies['Longitude'] == 0) | (~df_with_anomalies['Longitude'].between(-180, 180)))
    df_with_anomalies.loc[coord_invalid, 'Anomalie'] += 'Coordonnées invalides / '

    # Règles pour KAMSTRUP
    kamstrup_len_condition = is_kamstrup & (df_with_anomalies['Numéro de compteur'].str.len() != 8)
    df_with_anomalies.loc[kamstrup_len_condition, 'Anomalie'] += "KAMSTRUP: compteur ≠ 8 caractères / "
    
    condition2 = is_kamstrup & (df_with_anomalies['Numéro de tête'].str.lower() != 'nan') & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête'])
    df_with_anomalies.loc[condition2, 'Anomalie'] += "KAMSTRUP: compteur ≠ tête / "
    
    num_compteur_is_digit = df_with_anomalies['Numéro de compteur'].str.isdigit()
    num_tete_is_digit = df_with_anomalies['Numéro de tête'].str.isdigit()
    condition3 = is_kamstrup & (df_with_anomalies['Numéro de tête'].str.lower() != 'nan') & (~num_compteur_is_digit | ~num_tete_is_digit)
    df_with_anomalies.loc[condition3, 'Anomalie'] += "KAMSTRUP: compteur ou tête non numérique / "
    
    df_with_anomalies['Diametre'] = pd.to_numeric(df_with_anomalies['Diametre'], errors='coerce')
    condition4 = is_kamstrup & (~df_with_anomalies['Diametre'].between(15, 80))
    df_with_anomalies.loc[condition4, 'Anomalie'] += "KAMSTRUP: diamètre hors plage / "
    
    condition9 = is_kamstrup & (df_with_anomalies['Protocole Radio'] != 'WMS')
    df_with_anomalies.loc[condition9, 'Anomalie'] += "KAMSTRUP: protocole ≠ WMS / "
    
    # Règles pour SAPPEL
    condition5 = is_sappel & (df_with_anomalies['Numéro de tête'].str.startswith('DME')) & (df_with_anomalies['Numéro de tête'].str.len() != 15)
    df_with_anomalies.loc[condition5, 'Anomalie'] += "SAPPEL: tête DME ≠ 15 caractères / "
    
    regex_sappel_compteur = r'^[a-zA-Z]{1}\d{2}[a-zA-Z]{2}\d{6}$'
    condition6 = is_sappel & (~df_with_anomalies['Numéro de compteur'].str.match(regex_sappel_compteur))
    df_with_anomalies.loc[condition6, 'Anomalie'] += "SAPPEL: compteur ≠ format attendu / "
    
    condition7 = is_sappel & (~df_with_anomalies['Numéro de compteur'].str.startswith(('C', 'H')))
    df_with_anomalies.loc[condition7, 'Anomalie'] += "SAPPEL: compteur ne commence pas par C ou H / "
    
    condition8 = ((df_with_anomalies['Numéro de compteur'].str.startswith('C')) & (df_with_anomalies['Marque'] != 'SAPPEL (C)')) | \
                 ((df_with_anomalies['Numéro de compteur'].str.startswith('H')) & (df_with_anomalies['Marque'] != 'SAPPEL (H)'))
    df_with_anomalies.loc[condition8, 'Anomalie'] += "SAPPEL: incohérence Marque/compteur / "
    
    condition_sappel_tete = is_sappel & (annee_fabrication_num > 22) & (~df_with_anomalies['Numéro de tête'].str.startswith('DME'))
    df_with_anomalies.loc[condition_sappel_tete, 'Anomalie'] += "SAPPEL: Année >22 & tête ≠ DME / "
    
    condition_sappel_protocole = is_sappel & (annee_fabrication_num > 22) & (df_with_anomalies['Protocole Radio'] != 'OMS')
    df_with_anomalies.loc[condition_sappel_protocole, 'Anomalie'] += "SAPPEL: Année >22 & protocole ≠ OMS / "
    
    # Règle FP2E
    fp2e_map = {'A': 15, 'U': 15, 'V': 15, 'B': 20, 'C': 25, 'D': 30, 'E': 40, 'F': 50, 'G': 60, 'H': 80, 'I': 100, 'J': 125, 'K': 150}
    def check_fp2e(row):
        compteur = str(row['Numéro de compteur'])
        marque = row['Marque']
        annee = str(int(row['Année de fabrication'])) if not pd.isnull(row['Année de fabrication']) else ''
        diametre = row['Diametre']
        if len(compteur) < 6 or pd.isnull(diametre):
            return False
        if (marque == 'SAPPEL (C)' and not compteur.startswith('C')) or (marque == 'SAPPEL (H)' and not compteur.startswith('H')):
            return False
        if compteur[1:3] != annee.zfill(2)[-2:]:
            return False
        lettre_diam = compteur[4].upper()
        return fp2e_map.get(lettre_diam, None) == diametre
    
    condition_fp2e = is_sappel & (~df_with_anomalies.apply(check_fp2e, axis=1))
    df_with_anomalies.loc[condition_fp2e, 'Anomalie'] += "SAPPEL: non conforme FP2E / "
    
    # Nettoyage de la colonne 'Anomalie'
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
    return df_with_anomalies[df_with_anomalies['Anomalie'] != '']

def afficher_resume_anomalies(df_anomalies):
    """
    Affiche un résumé des anomalies.
    """
    resume = df_anomalies['Anomalie'].str.split(' / ').explode().value_counts().reset_index()
    resume.columns = ["Type d'anomalie", "Nombre d'occurrences"]
    st.subheader("Résumé des anomalies")
    st.dataframe(resume)

st.title("Contrôle des données de Radiorelève")
st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success("Fichier chargé avec succès !")
    try:
        file_extension = uploaded_file.name.split('.')[-1]
        if file_extension == 'csv':
            delimiter = get_csv_delimiter(uploaded_file)
            df = pd.read_csv(uploaded_file, sep=delimiter)
        elif file_extension == 'xlsx':
            df = pd.read_excel(uploaded_file)
        else:
            st.error("Format de fichier non pris en charge. Utilisez un fichier .csv ou .xlsx.")
            st.stop()
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
        st.stop()
    
    st.subheader("Aperçu des 5 premières lignes")
    st.dataframe(df.head())

    if st.button("Extraire les communes uniques"):
        if 'Commune' in df.columns:
            communes_uniques = df['Commune'].dropna().unique()
            st.write("Communes uniques trouvées dans le fichier :")
            st.write(communes_uniques)
        else:
            st.error("Colonne 'Commune' introuvable.")

    if st.button("Lancer les contrôles"):
        st.write("Contrôles en cours...")
        anomalies_df = check_data(df)
        if not anomalies_df.empty:
            st.error("Anomalies détectées !")
            st.dataframe(anomalies_df)
            afficher_resume_anomalies(anomalies_df)
            if file_extension == 'csv':
                csv_file = anomalies_df.to_csv(index=False, sep=delimiter).encode('utf-8')
                st.download_button("Télécharger les anomalies en CSV", csv_file, "anomalies_radioreleve.csv", "text/csv")
            elif file_extension == 'xlsx':
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    anomalies_df.to_excel(writer, index=False, sheet_name='Anomalies')
                excel_buffer.seek(0)
                st.download_button("Télécharger les anomalies en Excel", excel_buffer, "anomalies_radioreleve.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.success("Aucune anomalie détectée. Les données sont conformes.")
