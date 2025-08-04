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
    
    # 1. Contrôle des cases vides dans la colonne B
    empty_b = df_copy[df_copy['B'].isnull()]
    if not empty_b.empty:
        empty_b['Anomalie'] = "Colonne B vide"
        anomalies.append(empty_b)

    # 2. Contrôle des cases vides dans la colonne C
    empty_c = df_copy[df_copy['C'].isnull()]
    if not empty_c.empty:
        empty_c['Anomalie'] = "Colonne C vide"
        anomalies.append(empty_c)

    # 3. Contrôle des cases vides dans la colonne G
    empty_g = df_copy[df_copy['G'].isnull()]
    if not empty_g.empty:
        empty_g['Anomalie'] = "Colonne G vide"
        anomalies.append(empty_g)

    # 4. Contrôle de la longueur des caractères pour la marque KAMSTRUP
    kamstrup_df = df_copy[df_copy['C'] == 'KAMSTRUP']
    length_anomalies = kamstrup_df[kamstrup_df['F'].apply(lambda x: len(str(x)) != 8)]
    if not length_anomalies.empty:
        length_anomalies['Anomalie'] = "Marque KAMSTRUP : nombre de caractères dans F n'est pas 8"
        anomalies.append(length_anomalies)

    if anomalies:
        # Concaténer toutes les anomalies en un seul DataFrame
        anomalies_df = pd.concat(anomalies)
        # Supprimer les doublons si une ligne a plusieurs anomalies
        return anomalies_df.drop_duplicates()
    else:
        return pd.DataFrame()

# Interface Streamlit
st.title("Contrôle des données de Radiorelève")
st.write("Veuillez téléverser votre fichier pour lancer les contrôles.")

uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

if uploaded_file is not None:
    # Déterminer le type de fichier et le charger
    file_extension = uploaded_file.name.split('.')[-1]
    if file_extension == 'csv':
        df = pd.read_csv(uploaded_file)
    elif file_extension == 'xlsx':
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Format de fichier non pris en charge. Veuillez utiliser un fichier .csv ou .xlsx.")
        df = None

    if df is not None:
        st.subheader("Aperçu des données")
        st.dataframe(df.head())
        
        if st.button("Lancer les contrôles"):
            anomalies_df = check_data(df)
            
            if not anomalies_df.empty:
                st.subheader("Anomalies détectées")
                st.dataframe(anomalies_df)
                
                # Option pour télécharger les anomalies
                csv_file = anomalies_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Télécharger les anomalies en CSV",
                    data=csv_file,
                    file_name='anomalies_radioreleve.csv',
                    mime='text/csv',
                )
            else:
                st.success("Aucune anomalie détectée ! Les données sont conformes.")
