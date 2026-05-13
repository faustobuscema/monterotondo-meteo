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
    page_title="Meteo Monterotondo -RM-",
    page_icon="🌦️",
    layout="wide"
)

# ------------------------------
# Cache per caricare i dati CSV
# ------------------------------
@st.cache_data
def load_data(csv_path):
    df = pd.read_csv(csv_path)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    # Rinomina colonne per comodità (se i nomi sono diversi)
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
# Funzioni per meteo attuale
# ------------------------------
def geocode_city(city_name):
    """Converte nome città in (lat, lon) usando Open-Meteo Geocoding."""
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=it"
    try:
        resp = requests.get(url).json()
    except:
        return None, None, None, None
    if resp.get("results"):
        result = resp["results"][0]
        return result["latitude"], result["longitude"], result["name"], result["country"]
    else:
        return None, None, None, None

def current_weather(lat, lon, timezone="Europe/Rome"):
    """Richiede i dati meteo attuali a Open-Meteo. Gestisce valori mancanti."""
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
    except:
        return None
    current = resp.get("current_weather", {})
    hourly = resp.get("hourly", {})
    times = hourly.get("time", [])
    current_time = current.get("time")
    idx = times.index(current_time) if current_time in times else None
    # Gestione valori mancanti
    humidity = hourly["relative_humidity_2m"][idx] if idx is not None and idx < len(hourly.get("relative_humidity_2m", [])) else None
    pressure = hourly["pressure_msl"][idx] if idx is not None and idx < len(hourly.get("pressure_msl", [])) else None
    cloudcover = hourly["cloudcover"][idx] if idx is not None and idx < len(hourly.get("cloudcover", [])) else None
    return {
        "data": current_time,
        "temperatura": current.get("temperature"),
        "vento": current.get("windspeed"),
        "direzione_vento": current.get("winddirection"),
        "umidità": humidity,
        "pressione": pressure,
        "nuvolosità": cloudcover
    }

# ------------------------------
# Caricamento dati storici
# ------------------------------
st.sidebar.header("📂 Dati storici")
csv_file = st.sidebar.file_uploader("Carica il tuo CSV (opzionale)", type=["csv"])
if csv_file is not None:
    df = load_data(csv_file)
    st.sidebar.success("CSV caricato!")
else:
    default_csv = "dati_meteo.csv"
    try:
        df = load_data(default_csv)
        st.sidebar.info(f"Usando dati da {default_csv}")
    except FileNotFoundError:
        st.sidebar.error("Nessun CSV fornito e 'dati_meteo.csv' non trovato.")
        st.stop()

# ------------------------------
# Sidebar: selezione città / coordinate
# ------------------------------
st.sidebar.header("🌍 Località per meteo attuale")
city = st.sidebar.text_input("Nome città italiana (es. Roma, Milano)", value="Monterotondo")
if st.sidebar.button("Cerca città"):
    lat, lon, city_name, country = geocode_city(city)
    if lat is not None:
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.session_state.city_name = f"{city_name}, {country}"
        st.sidebar.success(f"Coordinate: {lat:.4f}, {lon:.4f}")
    else:
        st.sidebar.error("Città non trovata")

# Inizializza coordinate di default (Monterotondo RM)
if "lat" not in st.session_state:
    st.session_state.lat = 42.056747
    st.session_state.lon = 12.574791
    st.session_state.city_name = "Monterotondo, Italia"

st.sidebar.write(f"📍 **{st.session_state.city_name}**")
st.sidebar.write(f"Lat: {st.session_state.lat:.4f}, Lon: {st.session_state.lon:.4f}")

# ------------------------------
# Meteo attuale
# ------------------------------
st.header("🌤️ Meteo attuale")
with st.spinner("Recupero dati in tempo reale..."):
    current = current_weather(st.session_state.lat, st.session_state.lon)

if current and current["temperatura"] is not None:
    # Funzione helper per formattare valori None
    def fmt(value, unit=""):
        if value is None:
            return "N/D"
        try:
            return f"{value:.1f}{unit}" if unit else f"{value:.0f}"
        except:
            return str(value)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🌡️ Temperatura", fmt(current['temperatura'], " °C"))
    col2.metric("💧 Umidità", fmt(current['umidità'], " %"))
    col3.metric("💨 Vento", fmt(current['vento'], " km/h"))
    col4.metric("📈 Pressione", fmt(current['pressione'], " hPa"))
    if current['data']:
        st.caption(f"Dati aggiornati al {current['data']} (ora locale)")
else:
    st.error("Impossibile ottenere meteo attuale. Verifica la connessione o riprova più tardi.")

# ------------------------------
# Analisi storiche
# ------------------------------
st.header("📊 Analisi storiche (2000–2025)")
years = sorted(df.index.year.unique())
selected_years = st.multiselect("Anni da confrontare", years, default=years[:3] if len(years)>=3 else years)

if not selected_years:
    st.warning("Seleziona almeno un anno.")
    st.stop()

df_filtered = df[df.index.year.isin(selected_years)].copy()
df_filtered['anno'] = df_filtered.index.year
df_filtered['mese'] = df_filtered.index.month
df_filtered['giorno'] = df_filtered.index.day

# Riepilogo metriche (ultimo anno selezionato)
last_year = max(selected_years)
df_last = df_filtered[df_filtered.index.year == last_year]
col1, col2 = st.columns(2)
with col1:
    st.metric(f"Temperatura media {last_year}", f"{df_last['temperatura'].mean():.1f} °C" if not df_last.empty else "N/D")
with col2:
    st.metric(f"Precipitazione totale {last_year}", f"{df_last['precipitazione'].sum():.0f} mm" if not df_last.empty else "N/D")

# Andamento temperatura (min/max giornalieri)
st.subheader("Andamento temperature (minime e massime giornaliere)")
df_daily = df_filtered.resample('D').agg({'temperatura': ['min', 'max']}).dropna()
if not df_daily.empty:
    df_daily.columns = ['temp_min', 'temp_max']
    df_daily = df_daily.reset_index()
    df_daily['anno'] = df_daily['time'].dt.year
    chart_temp = alt.Chart(df_daily).mark_bar(opacity=0.7).encode(
        x=alt.X('monthdate(time):O', title='Data'),
        y=alt.Y('temp_max:Q', title='Temperatura (°C)'),
        y2='temp_min:Q',
        color=alt.Color('anno:N', title='Anno'),
        tooltip=['time', 'temp_min', 'temp_max']
    ).properties(height=400)
    st.altair_chart(chart_temp, use_container_width=True)
else:
    st.info("Dati insufficienti per il grafico delle temperature.")

# Distribuzione nuvolosità
st.subheader("Distribuzione della nuvolosità")
if 'nuvolosità' in df_filtered.columns and not df_filtered['nuvolosità'].dropna().empty:
    df_nuv = df_filtered.groupby('nuvolosità').size().reset_index(name='conteggio')
    chart_nuv = alt.Chart(df_nuv).mark_arc().encode(
        theta='conteggio:Q',
        color=alt.Color('nuvolosità:Q', scale=alt.Scale(scheme='blues'), title='Nuvolosità (%)'),
        tooltip=['nuvolosità', 'conteggio']
    ).properties(height=300)
    st.altair_chart(chart_nuv, use_container_width=True)
else:
    st.info("Nessun dato di nuvolosità disponibile.")

# Vento medio mensile
st.subheader("Vento medio mensile")
if 'vento' in df_filtered.columns:
    df_wind = df_filtered.groupby(['anno', 'mese'])['vento'].mean().reset_index()
    chart_wind = alt.Chart(df_wind).mark_line(point=True).encode(
        x=alt.X('mese:O', title='Mese'),
        y=alt.Y('vento:Q', title='Velocità vento (km/h)'),
        color='anno:N'
    ).properties(height=350)
    st.altair_chart(chart_wind, use_container_width=True)
else:
    st.info("Nessun dato di vento disponibile.")

# Precipitazioni mensili totali
st.subheader("Precipitazioni totali per mese")
if 'precipitazione' in df_filtered.columns:
    df_prec = df_filtered.groupby(['anno', 'mese'])['precipitazione'].sum().reset_index()
    chart_prec = alt.Chart(df_prec).mark_bar().encode(
        x='mese:O',
        y='precipitazione:Q',
        color='anno:N',
        column='anno:N'
    ).properties(height=300)
    st.altair_chart(chart_prec, use_container_width=True)
else:
    st.info("Nessun dato di precipitazione disponibile.")

# Matrice di correlazione
st.subheader("Correlazioni tra variabili")
corr_vars = ['temperatura', 'umidità', 'precipitazione', 'vento', 'nuvolosità', 'pressione']
# Filtra colonne esistenti
existing_vars = [v for v in corr_vars if v in df_filtered.columns]
if len(existing_vars) >= 2:
    corr_matrix = df_filtered[existing_vars].corr().stack().reset_index()
    corr_matrix.columns = ['var1', 'var2', 'correlazione']
    heatmap = alt.Chart(corr_matrix).mark_rect().encode(
        x='var1:O',
        y='var2:O',
        color=alt.Color('correlazione:Q', scale=alt.Scale(scheme='redblue', domain=[-1,1]), legend=alt.Legend(title='Correlazione'))
    ).properties(width=400, height=400)
    text = alt.Chart(corr_matrix).mark_text(baseline='middle', fontSize=10).encode(
        x='var1:O',
        y='var2:O',
        text=alt.Text('correlazione:Q', format='.2f'),
        color=alt.condition(alt.datum.correlazione > 0.5, alt.value('white'), alt.value('black'))
    )
    st.altair_chart(heatmap + text, use_container_width=True)
else:
    st.info("Dati insufficienti per la matrice di correlazione.")

# Raw data
st.subheader("Dati grezzi (ultimi 1000 record)")
st.dataframe(df_filtered.tail(1000))

st.caption("Fonte: CSV storico (2000-2025) | Meteo attuale: Open‑Meteo")