# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests

# ------------------------------
# Configurazione pagina
# ------------------------------
st.set_page_config(
    page_title="Monterotondo Meteo",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
        st.stop()
    except Exception as e:
        st.error(f"Errore caricamento: {e}")
        st.stop()
    
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
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
# Funzioni meteo attuale
# ------------------------------
def geocode_city(city_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
    try:
        resp = requests.get(url).json()
        if resp.get("results"):
            r = resp["results"][0]
            return r["latitude"], r["longitude"], r["name"], r["country"]
        return None, None, None, None
    except:
        return None, None, None, None

def current_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": True,
        "hourly": ["relative_humidity_2m", "pressure_msl", "cloudcover"],
        "timezone": "Europe/Rome"
    }
    try:
        resp = requests.get(url, params=params).json()
        current = resp.get("current_weather", {})
        hourly = resp.get("hourly", {})
        times = hourly.get("time", [])
        idx = times.index(current.get("time")) if current.get("time") in times else None
        
        return {
            "data": current.get("time"),
            "temperatura": current.get("temperature"),
            "vento": current.get("windspeed"),
            "umidità": hourly.get("relative_humidity_2m")[idx] if idx is not None else None,
            "pressione": hourly.get("pressure_msl")[idx] if idx is not None else None,
            "nuvolosità": hourly.get("cloudcover")[idx] if idx is not None else None
        }
    except:
        return None

# ==============================
# SIDEBAR - NUOVO ORDINE
# ==============================
st.sidebar.header("🌍 Meteo in tempo reale")

city = st.sidebar.text_input("Nome città italiana", value="Monterotondo")

if st.sidebar.button("🔍 Cerca città"):
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
# Caricamento dati storici (sotto)
# ------------------------------
st.sidebar.header("📂 Dati storici")
csv_file = st.sidebar.file_uploader("Carica CSV (opzionale)", type=["csv"])

if csv_file is not None:
    df = pd.read_csv(csv_file)
    st.sidebar.success("✅ CSV caricato dall'utente")
else:
    df = load_data()

# ------------------------------
# Meteo attuale
# ------------------------------
st.header("🌤️ Meteo attuale")
with st.spinner("Recupero dati in tempo reale..."):
    current = current_weather(st.session_state.lat, st.session_state.lon)

if current and current["temperatura"] is not None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Temperatura", f"{current['temperatura']:.1f} °C")
    col2.metric("💧 Umidità", f"{current['umidità']:.0f} %" if current['umidità'] else "N/D")
    col3.metric("💨 Vento", f"{current['vento']:.0f} km/h" if current['vento'] else "N/D")
    col4.metric("📈 Pressione", f"{current['pressione']:.0f} hPa" if current['pressione'] else "N/D")
    
    if current['data']:
        st.caption(f"Aggiornato: {current['data']}")
else:
    st.error("Impossibile recuperare il meteo attuale.")

# ------------------------------
# Analisi storiche
# ------------------------------
st.header("📊 Analisi storiche (2000–2025)")

years = sorted(df.index.year.unique())
# Default 2024 e 2025
default_years = [y for y in [2024, 2025] if y in years]

selected_years = st.multiselect(
    "Seleziona anni da confrontare", 
    years, 
    default=default_years if default_years else years[-2:]
)

if not selected_years:
    st.warning("Seleziona almeno un anno")
    st.stop()

df_filtered = df[df.index.year.isin(selected_years)].copy()
df_filtered['anno'] = df_filtered.index.year
df_filtered['mese'] = df_filtered.index.month

# Riepilogo
last_year = max(selected_years)
df_last = df_filtered[df_filtered.index.year == last_year]

col1, col2 = st.columns(2)
with col1:
    st.metric(f"Temperatura media {last_year}", f"{df_last['temperatura'].mean():.1f} °C")
with col2:
    st.metric(f"Precipitazione totale {last_year}", f"{df_last['precipitazione'].sum():.0f} mm")

# Il resto dei tuoi grafici rimane uguale...
# (puoi incollare qui sotto il resto del codice che avevi prima per i grafici)

st.caption("Fonte: Open-Meteo | Dati storici in Parquet")