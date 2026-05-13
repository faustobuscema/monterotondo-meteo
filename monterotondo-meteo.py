# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests
from datetime import datetime

# ------------------------------
# Configurazione pagina
# ------------------------------
st.set_page_config(
    page_title="Monterotondo (RM) Meteo",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# Funzioni per meteo attuale
# ------------------------------
def geocode_city(city_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
    try:
        resp = requests.get(url).json()
        if resp.get("results"):
            result = resp["results"][0]
            return result["latitude"], result["longitude"], result["name"], result["country"]
        else:
            return None, None, None, None
    except:
        return None, None, None, None

def current_weather(lat, lon, timezone="Europe/Rome"):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "hourly": ["relative_humidity_2m", "pressure_msl", "cloudcover"],
        "timezone": timezone
    }
    try:
        resp = requests.get(url, params=params).json()
        current = resp.get("current_weather", {})
        hourly = resp.get("hourly", {})
        
        current_time = current.get("time")
        times = hourly.get("time", [])
        idx = times.index(current_time) if current_time in times else None
        
        return {
            "data": current_time,
            "temperatura": current.get("temperature"),
            "vento": current.get("windspeed"),
            "direzione_vento": current.get("winddirection"),
            "umidità": hourly["relative_humidity_2m"][idx] if idx is not None else None,
            "pressione": hourly["pressure_msl"][idx] if idx is not None else None,
            "nuvolosità": hourly["cloudcover"][idx] if idx is not None else None
        }
    except:
        return None
    
# ------------------------------
# Cache per caricare i dati Parquet
# ------------------------------
@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_parquet("dati_meteo.parquet")
        st.sidebar.success("✅ Dati storici caricati da Parquet")
        
        # Ottimizzazione memoria
        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='float')
        for col in df.select_dtypes(include=['int64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='integer')
            
    except FileNotFoundError:
        st.error("❌ File 'dati_meteo.parquet' non trovato!")
        st.info("Carica il file dati_meteo.parquet nella root del repository GitHub.")
        st.stop()
    except Exception as e:
        st.error(f"Errore caricamento Parquet: {e}")
        st.stop()
    
    # Conversione data
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Rinomina colonne
    df.rename(columns={
        'temperature_2m': 'temperatura',
        'relative_humidity_2m': 'umidità',
        'precipitation': 'precipitazione',
        'windspeed_10m': 'vento',
        'cloudcover': 'nuvolosità',
        'pressure_msl': 'pressione',
        'shortwave_radiation': 'radiazione'
    }, inplace=True, errors='ignore')
    
    return df

# ------------------------------
# Caricamento dati
# ------------------------------
st.sidebar.header("📂 Dati storici")

csv_file = st.sidebar.file_uploader("Carica CSV (opzionale)", type=["csv"])

if csv_file is not None:
    df = pd.read_csv(csv_file)
    st.sidebar.success("✅ CSV caricato dall'utente")
else:
    df = load_data()

# ------------------------------
# Sidebar: selezione città
# ------------------------------
st.sidebar.header("🌍 Meteo in tempo reale")
city = st.sidebar.text_input("Nome città italiana", value="Monterotondo")

if st.sidebar.button("Cerca città"):
    lat, lon, city_name, country = geocode_city(city)
    if lat is not None:
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.city_name = f"{city_name}, {country}"
        st.sidebar.success("Città trovata!")
    else:
        st.sidebar.error("Città non trovata")

# Coordinate di default
if "lat" not in st.session_state:
    st.session_state.lat = 42.056747
    st.session_state.lon = 12.574791
    st.session_state.city_name = "Monterotondo, Italia"

st.sidebar.write(f"📍 **{st.session_state.city_name}**")
st.sidebar.write(f"Lat: {st.session_state.lat:.4f} | Lon: {st.session_state.lon:.4f}")

# ------------------------------
# Meteo attuale
# ------------------------------
st.header("🌤️ Meteo attuale")
with st.spinner("Recupero dati in tempo reale..."):
    current = current_weather(st.session_state.lat, st.session_state.lon)

if current and current["temperatura"] is not None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Temperatura", f"{current['temperatura']:.1f} °C")
    col2.metric("💧 Umidità", f"{current['umidità']:.0f} %" if current['umidità'] is not None else "N/D")
    col3.metric("💨 Vento", f"{current['vento']:.0f} km/h" if current['vento'] is not None else "N/D")
    col4.metric("📈 Pressione", f"{current['pressione']:.0f} hPa" if current['pressione'] is not None else "N/D")
    
    if current['data']:
        st.caption(f"Aggiornato: {current['data']}")
else:
    st.error("Impossibile recuperare il meteo attuale.")

# ------------------------------
# Analisi storiche (il resto del codice rimane uguale)
# ------------------------------
st.header("📊 Analisi storiche (2000–2025)")

years = sorted(df.index.year.unique())
selected_years = st.multiselect("Seleziona anni da confrontare", years, default=years[-3:] if len(years) >= 3 else years)

if not selected_years:
    st.warning("Seleziona almeno un anno")
    st.stop()

df_filtered = df[df.index.year.isin(selected_years)].copy()
df_filtered['anno'] = df_filtered.index.year
df_filtered['mese'] = df_filtered.index.month

# ... (il resto del tuo codice con i grafici rimane uguale)

last_year = max(selected_years)
df_last = df_filtered[df_filtered.index.year == last_year]

col1, col2 = st.columns(2)
with col1:
    st.metric(f"Temp. media {last_year}", f"{df_last['temperatura'].mean():.1f} °C")
with col2:
    st.metric(f"Precip. totale {last_year}", f"{df_last['precipitazione'].sum():.0f} mm")

# (Puoi lasciare il resto dei grafici come era prima)

st.caption("Fonte: Open-Meteo | Dati storici in Parquet")