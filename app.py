import streamlit as st
import pandas as pd
import io
import csv

def get_csv_delimiter(file):
    """Détecte le délimiteur d'un fichier CSV."""
    try:
        # Lire les premières lignes pour deviner le délimiteur
        sample = file.read(2048).decode('utf-8')
        dialect = csv.Sniffer().sniff(sample)
        file.seek(0) # Revenir au début du fichier
        return dialect.delimiter
    except Exception:
        file.seek(0)
        return ',' # Retourner la virgule par défaut si la détection échoue

def check_data(df):
    """
    Effectue tous les contrôles sur le DataFrame et retourne un DataFrame avec les anomalies.
    """
    df_with_anomalies = df.copy()
    
    # Vérifier la présence des colonnes requises
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Votre fichier ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_columns)}")
        st.stop()
    
    # Ajouter une colonne 'Anomalie' pour marquer les problèmes
    df_with_anomalies['Anomalie'] = ''

    # --- CONTROLES PRÉCÉDENTS ---
    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Colonne "Protocole Radio" vide; '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Colonne "Marque" vide; '
    df_with_anomalies.loc[df_with_anomalies['Numéro de tête'].isnull(), 'Anomalie'] += 'Colonne "Numéro de tête" vide; '
    df_with_anomalies.loc[df_with_anomalies['Latitude'] == 0, 'Anomalie'] += 'Latitude égale à zéro; '
    df_with_anomalies.loc[df_with_anomalies['Longitude'] == 0, 'Anomalie'] += 'Longitude égale à zéro; '
    df_with_anomalies.loc[~df_with_anomalies['Latitude'].between(-90, 90, inclusive='both'), 'Anomalie'] += "Latitude invalide (hors de la plage [-90, 90]); "
    df_with_anomalies.loc[~df_with_anomalies['Longitude'].between(-180, 180, inclusive='both'), 'Anomalie'] += "Longitude invalide (hors de la plage [-180, 180]); "
    kamstrup_condition = (df_with_anomalies['Marque'] == 'KAMSTRUP') & (df_with_anomalies['Numéro de compteur'].astype(str).str.len() != 8)
    df_with_anomalies.loc[kamstrup_condition, 'Anomalie'] += "Marque KAMSTRUP : 'Numéro de compteur' n'a pas 8 caractères; "

    # --- NOUVEAUX CONTRÔLES AJOUTÉS ---

    # Regroupement des conditions pour les marques pour plus de lisibilité
    is_kamstrup = df_with_anomalies['Marque'] == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].isin(['SAPPEL (C)', 'SAPPEL (H)'])
    
    # Règle 1 (Pas de changement, cette règle vérifie déjà si Numéro de tête est vide)
    condition1 = (is_sappel) & (df_with_anomalies['Numéro de tête'].isnull()) & (pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce') >= 22)
    df_with_anomalies.loc[condition1, 'Anomalie'] += "Marque Sappel : 'Numéro de tête' vide pour année de fabrication >= 22; "
    
    # Règle 2 - CORRIGÉE : Ajout de la condition pour que 'Numéro de tête' ne soit pas vide
    condition2 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête'])
    df_with_anomalies.loc[condition2, 'Anomalie'] += "Marque KAMSTRUP : 'Numéro de compteur' différent de 'Numéro de tête'; "
    
    # Règle 3 - CORRIGÉE : Ajout de la condition pour que 'Numéro de tête' ne soit pas vide
    num_compteur_is_digit = df_with_anomalies['Numéro de compteur'].astype(str).str.isdigit()
    num_tete_is_digit = df_with_anomalies['Numéro de tête'].astype(str).str.isdigit()
    condition3 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (~num_compteur_is_digit | ~num_tete_is_digit)
    df_with_anomalies.loc[condition3, 'Anomalie'] += "Marque KAMSTRUP : 'Numéro de compteur' ou 'Numéro de tête' contient une lettre; "
    
    # Règle 4
    condition4 = (is_kamstrup) & (~df_with_anomalies['Diametre'].between(15, 80, inclusive='both'))
    df_with_anomalies.loc[condition4, 'Anomalie'] += "Marque KAMSTRUP : 'Diametre' n'est pas entre 15 et 80; "
    
    # Règle 5 - CORRIGÉE : Ajout de la condition pour que 'Numéro de tête' ne soit pas vide
    condition5 = (is_sappel) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME')) & (df_with_anomalies['Numéro de tête'].astype(str).str.len() != 15)
    df_with_anomalies.loc[condition5, 'Anomalie'] += "Marque Sappel : 'Numéro de tête' (DME) n'a pas 15 caractères; "

    # Règle 6
    regex_sappel_compteur = r'^[a-zA-Z]{1}\d{2}[a-zA-Z]{2}\d{6}$'
    condition6 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.match(regex_sappel_compteur))
    df_with_anomalies.loc[condition6, 'Anomalie'] += "Marque Sappel : 'Numéro de compteur' ne respecte pas le format; "

    # Règle 7
    condition7 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H'))
    df_with_anomalies.loc[condition7, 'Anomalie'] += "Marque Sappel : 'Numéro de compteur' ne commence ni par 'C' ni par 'H'; "

    # Règle 8
    condition8 = ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (df_with_anomalies['Marque'] != 'SAPPEL (C)')) | \
                 ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H')) & (df_with_anomalies['Marque'] != 'SAPPEL (H)'))
    df_with_anomalies.loc[condition8, 'Anomalie'] += "Incohérence entre 'Numéro de compteur' et 'Marque'; "

    # Règle 9
    condition9 = (is_kamstrup) & (df_with_anomalies['Protocole Radio'] != 'WMS')
    df_with_anomalies.loc[condition9, 'Anomalie'] += "Marque KAMSTRUP : 'Protocole Radio' n'est pas 'WMS'; "

    # Règle 10 - CORRIGÉE : Ajout de la condition pour que 'Numéro de tête' ne soit pas vide
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    condition10 = (is_sappel) & (annee_fabrication_num >= 22) & (df_with_anomalies['Protocole Radio'] != 'OMS') & (~df_with_anomalies['Numéro de tête'].isnull()) & (~df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME'))
    df_with_anomalies.loc[condition10, 'Anomalie'] += "Marque Sappel : Année >= 22 sans Protocole Radio='OMS' ou 'Numéro de tête' commençant par 'DME'; "
    
    # -----------------------------
    
    # Nettoyer la colonne d'anomalies (retirer le dernier '; ')
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(';')
    
    # Filtrer uniquement les lignes avec des anomalies
    anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != '']
    return anomalies_df

# --- Interface Streamlit ---
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
            st.error("Format de fichier non pris en charge. Veuillez utiliser un fichier .csv ou .xlsx.")
            st.stop()
    except Exception as e:
        st.error(f"Une erreur est survenue lors de la lecture du fichier : {e}")
        st.stop()

    st.subheader("Aperçu des 5 premières lignes")
    st.dataframe(df.head())

    if st.button("Extraire les communes uniques"):
        if 'Commune' in df.columns:
            communes_uniques = df['Commune'].dropna().unique()
            st.write("Communes uniques trouvées dans le fichier :")
            st.write(communes_uniques)
        else:
            st.error("La colonne 'Commune' est introuvable. Veuillez vérifier que le nom de la colonne est correct.")

    if st.button("Lancer les contrôles"):
        st.write("Contrôles en cours...")
        anomalies_df = check_data(df)

        if not anomalies_df.empty:
            st.error("Anomalies détectées !")
            st.dataframe(anomalies_df)
            
            if file_extension == 'csv':
                csv_file = anomalies_df.to_csv(index=False, sep=delimiter).encode('utf-8')
                st.download_button(
                    label="Télécharger les anomalies en CSV",
                    data=csv_file,
                    file_name='anomalies_radioreleve.csv',
                    mime='text/csv',
                )
            elif file_extension == 'xlsx':
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    anomalies_df.to_excel(writer, index=False, sheet_name='Anomalies')
                excel_buffer.seek(0)

                st.download_button(
                    label="Télécharger les anomalies en Excel",
                    data=excel_buffer,
                    file_name='anomalies_radioreleve.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )
        else:
            st.success("Aucune anomalie détectée ! Les données sont conformes.")
