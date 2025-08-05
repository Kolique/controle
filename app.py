import streamlit as st
import pandas as pd
import io
import csv

# @st.cache_data est conservé pour optimiser le temps de traitement initial
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

@st.cache_data
def check_data(df):
    """
    Effectue tous les contrôles sur le DataFrame et retourne un DataFrame avec les anomalies.
    """
    df_with_anomalies = df.copy()
    
    required_columns = ['Protocole Radio', 'Marque', 'Numéro de tête', 'Numéro de compteur', 'Latitude', 'Longitude', 'Commune', 'Année de fabrication', 'Diametre']
    if not all(col in df_with_anomalies.columns for col in required_columns):
        missing_columns = [col for col in required_columns if col not in df_with_anomalies.columns]
        st.error(f"Votre fichier ne contient pas toutes les colonnes requises. Colonnes manquantes : {', '.join(missing_columns)}")
        return pd.DataFrame()
    
    df_with_anomalies['Anomalie'] = ''

    is_kamstrup = df_with_anomalies['Marque'] == 'KAMSTRUP'
    is_sappel = df_with_anomalies['Marque'].isin(['SAPPEL (C)', 'SAPPEL (H)'])
    annee_fabrication_num = pd.to_numeric(df_with_anomalies['Année de fabrication'], errors='coerce')
    
    condition_num_tete_vide = df_with_anomalies['Numéro de tête'].isnull() & (~is_sappel | (annee_fabrication_num >= 22))
    df_with_anomalies.loc[condition_num_tete_vide, 'Anomalie'] += 'Numéro de tête vide / '
    df_with_anomalies.loc[df_with_anomalies['Protocole Radio'].isnull(), 'Anomalie'] += 'Protocole Radio vide / '
    df_with_anomalies.loc[df_with_anomalies['Marque'].isnull(), 'Anomalie'] += 'Marque vide / '
    df_with_anomalies.loc[df_with_anomalies['Latitude'] == 0, 'Anomalie'] += 'Latitude = 0 / '
    df_with_anomalies.loc[df_with_anomalies['Longitude'] == 0, 'Anomalie'] += 'Longitude = 0 / '
    df_with_anomalies.loc[~df_with_anomalies['Latitude'].between(-90, 90, inclusive='both'), 'Anomalie'] += 'Latitude invalide / '
    df_with_anomalies.loc[~df_with_anomalies['Longitude'].between(-180, 180, inclusive='both'), 'Anomalie'] += 'Longitude invalide / '
    kamstrup_len_condition = (is_kamstrup) & (df_with_anomalies['Numéro de compteur'].astype(str).str.len() != 8)
    df_with_anomalies.loc[kamstrup_len_condition, 'Anomalie'] += "Numéro de compteur KAMSTRUP n'a pas 8 caractères / "
    
    condition2 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de compteur'] != df_with_anomalies['Numéro de tête'])
    df_with_anomalies.loc[condition2, 'Anomalie'] += "KAMSTRUP: Numéros de compteur et tête différents / "
    
    num_compteur_is_digit = df_with_anomalies['Numéro de compteur'].astype(str).str.isdigit()
    num_tete_is_digit = df_with_anomalies['Numéro de tête'].astype(str).str.isdigit()
    condition3 = (is_kamstrup) & (~df_with_anomalies['Numéro de tête'].isnull()) & (~num_compteur_is_digit | ~num_tete_is_digit)
    df_with_anomalies.loc[condition3, 'Anomalie'] += "KAMSTRUP: Numéro de compteur ou tête contient une lettre / "
    
    condition4 = (is_kamstrup) & (~df_with_anomalies['Diametre'].between(15, 80, inclusive='both'))
    df_with_anomalies.loc[condition4, 'Anomalie'] += "KAMSTRUP: Diamètre n'est pas entre 15 et 80 / "
    
    condition5 = (is_sappel) & (~df_with_anomalies['Numéro de tête'].isnull()) & (df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME')) & (df_with_anomalies['Numéro de tête'].astype(str).str.len() != 15)
    df_with_anomalies.loc[condition5, 'Anomalie'] += "Sappel: Numéro de tête (DME) n'a pas 15 caractères / "

    regex_sappel_compteur = r'^[a-zA-Z]{1}\d{2}[a-zA-Z]{2}\d{6}$'
    condition6 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.match(regex_sappel_compteur))
    df_with_anomalies.loc[condition6, 'Anomalie'] += "Sappel: Numéro de compteur ne respecte pas le format / "

    condition7 = (is_sappel) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (~df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H'))
    df_with_anomalies.loc[condition7, 'Anomalie'] += "Sappel: Numéro de compteur ne commence ni par 'C' ni par 'H' / "

    condition8 = ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('C')) & (df_with_anomalies['Marque'] != 'SAPPEL (C)')) | \
                 ((df_with_anomalies['Numéro de compteur'].astype(str).str.startswith('H')) & (df_with_anomalies['Marque'] != 'SAPPEL (H)'))
    df_with_anomalies.loc[condition8, 'Anomalie'] += "Incohérence Numéro de compteur / Marque / "

    condition9 = (is_kamstrup) & (df_with_anomalies['Protocole Radio'] != 'WMS')
    df_with_anomalies.loc[condition9, 'Anomalie'] += "KAMSTRUP: Protocole Radio n'est pas 'WMS' / "
    
    # Règle 10a (nouvelle)
    condition10a = (is_sappel) & (annee_fabrication_num > 22) & (~df_with_anomalies['Numéro de tête'].isnull()) & (~df_with_anomalies['Numéro de tête'].astype(str).str.startswith('DME'))
    df_with_anomalies.loc[condition10a, 'Anomalie'] += "Sappel: Année > 22 sans Numéro de tête DME / "
    
    # Règle 10b (nouvelle)
    condition10b = (is_sappel) & (annee_fabrication_num > 22) & (df_with_anomalies['Protocole Radio'] != 'OMS')
    df_with_anomalies.loc[condition10b, 'Anomalie'] += "Sappel: Année > 22 sans Protocole Radio 'OMS' / "

    df_with_anomalies['Anomalie'] = df_with_anomalies['Anomalie'].str.strip().str.rstrip(' /')
    
    anomalies_df = df_with_anomalies[df_with_anomalies['Anomalie'] != '']
    return anomalies_df

# --- Interface Streamlit ---

st.title("Contrôle des données de Radiorelève")
st.markdown("Veuillez téléverser votre fichier pour lancer les contrôles.")

uploaded_file = st.file_uploader("Choisissez un fichier", type=['csv', 'xlsx'])

if 'anomalies_df' not in st.session_state:
    st.session_state['anomalies_df'] = pd.DataFrame()
if 'df' not in st.session_state:
    st.session_state['df'] = pd.DataFrame()
if 'file_extension' not in st.session_state:
    st.session_state['file_extension'] = None

if uploaded_file is not None:
    st.success("Fichier chargé avec succès !")

    try:
        file_extension = uploaded_file.name.split('.')[-1]
        st.session_state['file_extension'] = file_extension
        if file_extension == 'csv':
            delimiter = get_csv_delimiter(uploaded_file)
            st.session_state['df'] = pd.read_csv(uploaded_file, sep=delimiter)
        elif file_extension == 'xlsx':
            st.session_state['df'] = pd.read_excel(uploaded_file)
        else:
            st.error("Format de fichier non pris en charge. Veuillez utiliser un fichier .csv ou .xlsx.")
            st.stop()
    except Exception as e:
        st.error(f"Une erreur est survenue lors de la lecture du fichier : {e}")
        st.stop()

    st.subheader("Aperçu des 5 premières lignes")
    st.dataframe(st.session_state['df'].head())
    
    if st.button("Extraire les communes uniques"):
        if 'Commune' in st.session_state['df'].columns:
            communes_uniques = st.session_state['df']['Commune'].dropna().unique()
            st.write("Communes uniques trouvées dans le fichier :")
            st.write(communes_uniques)
        else:
            st.error("La colonne 'Commune' est introuvable. Veuillez vérifier que le nom de la colonne est correct.")

    if st.button("Lancer les contrôles"):
        with st.spinner('Contrôles en cours...'):
            st.session_state['anomalies_df'] = check_data(st.session_state['df'])

if not st.session_state['anomalies_df'].empty:
    st.error("Anomalies détectées !")
    
    st.subheader("Résumé des anomalies")
    anomaly_counts = st.session_state['anomalies_df']['Anomalie'].str.split(' / ').explode().value_counts().rename_axis('Type d\'anomalie').reset_index(name='Nombre')
    st.dataframe(anomaly_counts)
    
    st.subheader("Filtrer les anomalies")
    all_anomaly_types = anomaly_counts['Type d\'anomalie'].tolist()
    
    if 'selected_anomalies' not in st.session_state:
        st.session_state['selected_anomalies'] = all_anomaly_types

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Sélectionner tout", key='select_all_btn'):
            st.session_state['selected_anomalies'] = all_anomaly_types
    with col2:
        if st.button("Désélectionner tout", key='deselect_all_btn'):
            st.session_state['selected_anomalies'] = []

    selected_anomalies = []
    for atype in all_anomaly_types:
        if st.checkbox(atype, value=(atype in st.session_state['selected_anomalies']), key=atype):
            selected_anomalies.append(atype)

    if not selected_anomalies:
        st.warning("Aucun filtre sélectionné. Le tableau des anomalies est vide.")
        filtered_anomalies_df = pd.DataFrame()
    else:
        filtered_anomalies_df = st.session_state['anomalies_df'][st.session_state['anomalies_df']['Anomalie'].apply(lambda x: any(atype in x for atype in selected_anomalies))]

    st.dataframe(filtered_anomalies_df)
    
    if not filtered_anomalies_df.empty:
        if st.session_state['file_extension'] == 'csv':
            delimiter = get_csv_delimiter(uploaded_file)
            csv_file = filtered_anomalies_df.to_csv(index=False, sep=delimiter).encode('utf-8')
            st.download_button(
                label="Télécharger les anomalies filtrées en CSV",
                data=csv_file,
                file_name='anomalies_radioreleve_filtrees.csv',
                mime='text/csv',
            )
        elif st.session_state['file_extension'] == 'xlsx':
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                filtered_anomalies_df.to_excel(writer, index=False, sheet_name='Anomalies')
            excel_buffer.seek(0)

            st.download_button(
                label="Télécharger les anomalies filtrées en Excel",
                data=excel_buffer,
                file_name='anomalies_radioreleve_filtrees.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
else:
    if 'df' in st.session_state and not st.session_state['df'].empty:
        st.info("Cliquez sur 'Lancer les contrôles' pour démarrer l'analyse.")
