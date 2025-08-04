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
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Votre fichier ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_columns)}")
        st.stop()
    
    # Ajouter une colonne 'Anomalie' pour marquer les problèmes
    df_with_anomalies['Anomalie'] = ''

    # 1. Contrôle des cases vides dans la colonne 'Protocole Radio'
    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Colonne "Protocole Radio" vide; '

    # 2. Contrôle des cases vides dans la colonne 'Marque'
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Colonne "Marque" vide; '

    # 3. Contrôle des cases vides dans la colonne 'Numéro de tête'
    df_with_anomalies.loc[df_with_anomalies['Numéro de tête'].isnull(), 'Anomalie'] += 'Colonne "Numéro de tête" vide; '

    # 4. Contrôle de la longueur des caractères pour la marque KAMSTRUP
    kamstrup_condition = (df_with_anomalies['Marque'] == 'KAMSTRUP') & (df_with_anomalies['Numéro de compteur'].astype(str).str.len() != 8)
    df_with_anomalies.loc[kamstrup_condition, 'Anomalie'] += "Marque KAMSTRUP : 'Numéro de compteur' n'a pas 8 caractères; "

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

    # Charger le fichier en DataFrame et détecter le délimiteur pour les CSV
    try:
        file_extension = uploaded_file.name.split('.')[-1]
        delimiter = ','
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

    if st.button("Lancer les contrôles"):
        st.write("Contrôles en cours...")
        anomalies_df = check_data(df)

        if not anomalies_df.empty:
            st.error("Anomalies détectées !")
            st.dataframe(anomalies_df)
            
            # Utiliser le même délimiteur pour le fichier de sortie
            if file_extension == 'csv':
                csv_file = anomalies_df.to_csv(index=False, sep=delimiter).encode('utf-8')
            else: # Pour les fichiers Excel, pas de délimiteur, on peut juste utiliser un CSV par défaut
                csv_file = anomalies_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="Télécharger les anomalies",
                data=csv_file,
                file_name=f'anomalies_radioreleve.{file_extension}', # Nom du fichier avec la bonne extension
                mime='text/csv' if file_extension == 'csv' else 'application/vnd.ms-excel',
            )
        else:
            st.success("Aucune anomalie détectée ! Les données sont conformes.")
