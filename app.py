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

    # Regroupement des conditions pour les marques pour plus de lisibilité
    is_kamstrup = df_with_anomalies['Marque'] == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].isin(['SAPPEL (C)', 'SAPPEL (H)'])

    # Récupérer l'année de fabrication en numérique pour les comparaisons
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    
    # --- CONTROLES MODIFIÉS ET PRIORISÉS ---
    
    # Priorité 1: Règle sur la colonne "Numéro de tête" vide avec exception Sappel
    # Condition d'anomalie : 'Numéro de tête' est vide ET (ce n'est pas une marque Sappel OU l'année est >= 22)
    condition_num_tete_vide = df_with_anomalies['Numéro de tête'].isnull() & (~is_sappel | (annee_fabrication_num >= 22))
    df_with_anomalies.loc[condition_num_tete_vide, 'Anomalie'] += 'Numéro de tête vide / '
    
    # Contrôle de la colonne "Protocole Radio" vide
    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Protocole Radio vide / '
    
    # Contrôle de la colonne "Marque" vide
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Marque vide / '
    
    # Contrôle "Latitude = 0"
    df_with_anomalies.loc[df_with_anomalies['Latitude'] == 0, 'Anomalie'] += 'Latitude = 0 / '
    
    # Contrôle "Longitude = 0"
    df_with_anomalies.loc[df_with_anomalies['Longitude'] == 0, 'Anomalie'] += 'Longitude = 0 / '
    
    # Contrôle de la plage de la Latitude
    df_with_anomalies.loc[~df_with_anomalies['Latitude'].between(-90, 90, inclusive='both'), 'Anomalie'] += 'Latitude invalide / '
    
    # Contrôle de la plage de la Longitude
    df_with_anomalies.loc[~df_with_anomalies['Longitude'].between(-180, 180, inclusive='both'), 'Anomalie'] += 'Longitude invalide / '
    
    # Contrôle de la longueur du Numéro de compteur pour KAMSTRUP
    kamstrup_len_condition = (is_kamstrup) & (df_with_anomalies['Numéro de compteur'].astype(str).str.len() != 8)
    df_with_anomalies.loc[kamstrup_len_condition, 'Anomalie'] += "Numéro de compteur KAMSTRUP n'a pas 8 caractères / "
    
    # --- NOUVELLES RÈGLES ---

    # Règle 2 : Numéro de compteur différent de Numéro de tête pour KAMSTRUP
    condition2 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête'])
    df_with_anomalies.loc[condition2, 'Anomalie'] += "KAMSTRUP: Numéros de compteur et tête différents / "
    
    # Règle 3 : Numéros de compteur et de tête non numériques pour KAMSTRUP
    num_compteur_is_digit = df_with_anomalies['Numéro de compteur'].astype(str).str.isdigit()
    num_tete_is_digit = df_with_anomalies['Numéro de tête'].astype(str).str.isdigit()
    condition3 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (~num_compteur_is_digit | ~num_tete_is_digit)
    df_with_anomalies.loc[condition3, 'Anomalie'] += "KAMSTRUP: Numéro de compteur ou tête contient une lettre / "
    
    # Règle 4 : Diamètre hors de la plage 15-80 pour KAMSTRUP
    condition4 = (is_kamstrup) & (~df_with_anomalies['Diametre'].between(15, 80, inclusive='both'))
    df_with_anomalies.loc[condition4, 'Anomalie'] += "KAMSTRUP: Diamètre n'est pas entre 15 et 80 / "
    
    # Règle 5 : Numéro de tête (DME) n'a pas 15 caractères pour Sappel
    condition5 = (is_sappel) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME')) & (df_with_anomalies['Numéro de tête'].astype(str).str.len() != 15)
    df_with_anomalies.loc[condition5, 'Anomalie'] += "Sappel: Numéro de tête (DME) n'a pas 15 caractères / "

    # Règle 6 : Format du Numéro de compteur pour Sappel
    regex_sappel_compteur = r'^[a-zA-Z]{1}\d{2}[a-zA-Z]{2}\d{6}$'
    condition6 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.match(regex_sappel_compteur))
    df_with_anomalies.loc[condition6, 'Anomalie'] += "Sappel: Numéro de compteur ne respecte pas le format / "

    # Règle 7 : Numéro de compteur ne commence ni par 'C' ni par 'H' pour Sappel
    condition7 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H'))
    df_with_anomalies.loc[condition7, 'Anomalie'] += "Sappel: Numéro de compteur ne commence ni par 'C' ni par 'H' / "

    # Règle 8 : Incohérence entre Numéro de compteur et Marque
    condition8 = ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (df_with_anomalies['Marque'] != 'SAPPEL (C)')) | \
                 ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H')) & (df_with_anomalies['Marque'] != 'SAPPEL (H)'))
    df_with_anomalies.loc[condition8, 'Anomalie'] += "Incohérence Numéro de compteur / Marque / "

    # Règle 9 : Protocole Radio non 'WMS' pour KAMSTRUP
    condition9 = (is_kamstrup) & (df_with_anomalies['Protocole Radio'] != 'WMS')
    df_with_anomalies.loc[condition9, 'Anomalie'] += "KAMSTRUP: Protocole Radio n'est pas 'WMS' / "

    # Règle 10 : Année >= 22 sans Protocole OMS ou Numéro de tête DME pour Sappel
    condition10 = (is_sappel) & (annee_fabrication_num >= 22) & (df_with_anomalies['Protocole Radio'] != 'OMS') & (~df_with_anomalies['Numéro de tête'].isnull()) & (~df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME'))
    df_with_anomalies.loc[condition10, 'Anomalie'] += "Sappel: Année >= 22 sans Protocole OMS ou Numéro de tête DME / "
    
    # -----------------------------
    
    # Nettoyer la colonne d'anomalies (retirer le dernier ' / ')
    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
    
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
