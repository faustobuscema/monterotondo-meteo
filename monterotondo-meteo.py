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
# SIDEBAR
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

if "lat" not in st.session_state:
    st.session_state.lat = 42.056747
    st.session_state.lon = 12.574791
    st.session_state.city_name = "Monterotondo, Italia"

st.sidebar.write(f"📍 **{st.session_state.city_name}**")
st.sidebar.write(f"Lat: {st.session_state.lat:.4f} | Lon: {st.session_state.lon:.4f}")

# Caricamento dati storici (sotto)
st.sidebar.header("📂 Dati storici")
csv_file = st.sidebar.file_uploader("Carica CSV (opzionale)", type=["csv"])

if csv_file is not None:
    df = pd.read_csv(csv_file)
    st.sidebar.success("✅ CSV caricato dall'utente")
else:
    df = load_data()

# ==============================
# METEO ATTUALE
# ==============================
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

# ==============================
# ANALISI STORICHE
# ==============================
st.header("📊 Analisi storiche a Monterotondo -RM- periodo 2000–2025")

years = sorted(df.index.year.unique())
default_years = [y for y in [2024, 2025] if y in years]

selected_years = st.multiselect(
    "Seleziona anni da confrontare", 
    years, 
    default=default_years if default_years else years[-3:]
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

# ==================== GRAFICI ====================
# ==================== Andamento temperature ====================
st.subheader("Andamento temperature (minime e massime giornaliere)")

df_daily = df_filtered.resample('D').agg({'temperatura': ['min', 'max']}).dropna()

if not df_daily.empty:
    df_daily.columns = ['temp_min', 'temp_max']
    df_daily = df_daily.reset_index()
    df_daily['anno'] = df_daily['time'].dt.year.astype(str)   # importante per la legenda
    
    chart_temp = alt.Chart(df_daily).mark_bar(opacity=0.75).encode(
        x=alt.X('monthdate(time):O', title='Data'),
        y=alt.Y('temp_max:Q', title='Temperatura (°C)'),
        y2=alt.Y2('temp_min:Q'),
        color=alt.Color('anno:N', title='Anno'),        # ← semplificato
        tooltip=[
            alt.Tooltip('time:T', title='Data', format='%d %b %Y'),
            alt.Tooltip('temp_max:Q', title='Max (°C)'),
            alt.Tooltip('temp_min:Q', title='Min (°C)'),
            alt.Tooltip('anno:N', title='Anno')
        ]
    ).properties(height=420)
    
    st.altair_chart(chart_temp, use_container_width=True)
else:
    st.info("Dati insufficienti per il grafico delle temperature.")

# Distribuzione nuvolosità
st.subheader("Distribuzione della nuvolosità")
if 'nuvolosità' in df_filtered.columns:
    df_nuv = df_filtered['nuvolosità'].value_counts().reset_index()
    df_nuv.columns = ['nuvolosità', 'conteggio']
    chart_nuv = alt.Chart(df_nuv).mark_arc().encode(
        theta='conteggio:Q',
        color=alt.Color('nuvolosità:Q', title='Nuvolosità (%)'),
        tooltip=['nuvolosità', 'conteggio']
    ).properties(height=300)
    st.altair_chart(chart_nuv, use_container_width=True)

# Vento medio mensile
st.subheader("Vento medio mensile")
df_wind = df_filtered.groupby(['anno', 'mese'])['vento'].mean().reset_index()
chart_wind = alt.Chart(df_wind).mark_line(point=True).encode(
    x=alt.X('mese:O', title='Mese'),
    y=alt.Y('vento:Q', title='Velocità vento (km/h)'),
    color='anno:N'
).properties(height=350)
st.altair_chart(chart_wind, use_container_width=True)

# Precipitazioni mensili
st.subheader("Precipitazioni totali per mese")
df_prec = df_filtered.groupby(['anno', 'mese'])['precipitazione'].sum().reset_index()
chart_prec = alt.Chart(df_prec).mark_bar().encode(
    x='mese:O',
    y='precipitazione:Q',
    color='anno:N',
    column='anno:N'
).properties(height=300)
st.altair_chart(chart_prec, use_container_width=True)

# Matrice di correlazione
st.subheader("Matrice di correlazione")
corr_vars = ['temperatura', 'umidità', 'precipitazione', 'vento', 'nuvolosità', 'pressione']
existing_vars = [v for v in corr_vars if v in df_filtered.columns]

if len(existing_vars) >= 2:
    corr_matrix = df_filtered[existing_vars].corr().stack().reset_index()
    corr_matrix.columns = ['var1', 'var2', 'correlazione']
    
    heatmap = alt.Chart(corr_matrix).mark_rect().encode(
        x='var1:O',
        y='var2:O',
        color=alt.Color('correlazione:Q', scale=alt.Scale(scheme='redblue', domain=[-1,1]))
    ).properties(width=500, height=500)
    
    text = alt.Chart(corr_matrix).mark_text().encode(
        x='var1:O',
        y='var2:O',
        text=alt.Text('correlazione:Q', format='.2f')
    )
    st.altair_chart(heatmap + text, use_container_width=True)

# Dati grezzi
st.subheader("Dati grezzi (ultimi 1000 record)")
st.dataframe(df_filtered.tail(1000), use_container_width=True)

st.caption("Fonte: Open-Meteo | Dati storici in Parquet")