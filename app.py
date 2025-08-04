import streamlit as st
import pandas as pd
import io

def check_data(df):
    """
    Effectue tous les contrôles sur le DataFrame et retourne les anomalies.
    """
    anomalies = []
    
    # Créer une copie du DataFrame pour éviter de modifier l'original
    df_copy = df.copy()

    # Vérifier la présence des colonnes requises
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur']
    if not all(col in df_copy.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_copy.columns]
        st.error(f"Votre fichier ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_columns)}")
        st.stop()
        
    # 1. Contrôle des cases vides dans la colonne 'Protocole Radio'
    empty_b = df_copy[df_copy['Protocole Radio'].isnull()]
    if not empty_b.empty:
        empty_b['Anomalie'] = "Colonne 'Protocole Radio' vide"
        anomalies.append(empty_b)

    # 2. Contrôle des cases vides dans la colonne 'Marque'
    empty_c = df_copy[df_copy['Marque'].isnull()]
    if not empty_c.empty:
        empty_c['Anomalie'] = "Colonne 'Marque' vide"
        anomalies.append(empty_c)

    # 3. Contrôle des cases vides dans la colonne 'Numéro de tête'
    empty_g = df_copy[df_copy['Numéro de tête'].isnull()]
    if not empty_g.empty:
        empty_g['Anomalie'] = "Colonne 'Numéro de tête' vide"
        anomalies.append(empty_g)

    # 4. Contrôle de la longueur des caractères pour la marque KAMSTRUP
    kamstrup_df = df_copy[df_copy['Marque'] == 'KAMSTRUP'].copy()
    if not kamstrup_df.empty:
        # Assurez-vous que la colonne 'Numéro de compteur' est de type string
        kamstrup_df['num_len'] = kamstrup_df['Numéro de compteur'].astype(str).str.len()
        length_anomalies = kamstrup_df[kamstrup_df['num_len'] != 8]
        if not length_anomalies.empty:
            length_anomalies['Anomalie'] = "Marque KAMSTRUP : nombre de caractères dans 'Numéro de compteur' n'est pas 8"
            anomalies.append(length_anomalies)

    if anomalies:
        anomalies_df = pd.concat(anomalies).drop_duplicates()
        return anomalies_df.reset_index(drop=True)
    else:
        return pd.DataFrame()

# --- Interface Streamlit ---
st.title("Contrôle des données de Radiorelève")
st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

if uploaded_file is not None:
    st.success("Fichier chargé avec succès !")

    # Charger le fichier en DataFrame
    try:
        file_extension = uploaded_file.name.split('.')[-1]
        if file_extension == 'csv':
            df = pd.read_csv(uploaded_file)
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
            
            csv_file = anomalies_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Télécharger les anomalies en CSV",
                data=csv_file,
                file_name='anomalies_radioreleve.csv',
                mime='text/csv',
            )
        else:
            st.success("Aucune anomalie détectée ! Les données sont conformes.")
