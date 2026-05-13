# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests
import openmeteo_requests
from retry_requests import retry
import requests_cache

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
# Client Open-Meteo
# ------------------------------
@st.cache_resource
def get_openmeteo_client():
    cache_session = requests_cache.CachedSession('.cache', expire_after=1800)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)

# ------------------------------
# Caricamento dati storici
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
        return df
    except Exception as e:
        st.error(f"❌ Errore caricamento Parquet: {e}")
        st.stop()

# ------------------------------
# Funzioni supporto
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

def get_weather_forecast(lat, lon):
    try:
        client = get_openmeteo_client()
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": ["temperature_2m", "apparent_temperature", "relative_humidity_2m",
                       "precipitation", "rain", "showers", "cloud_cover", "wind_speed_10m"],
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
            "timezone": "Europe/Rome", "forecast_days": 3
        }
        
        responses = client.weather_api(url, params=params)
        response = responses[0]
        
        current = response.Current()
        current_data = {
            "temperatura": current.Variables(0).Value(),
            "percepita": current.Variables(1).Value(),
            "umidità": current.Variables(2).Value(),
            "precipitazione": current.Variables(3).Value(),
            "nuvolosità": current.Variables(6).Value(),
            "vento": current.Variables(7).Value(),
        }
        
        daily = response.Daily()
        daily_data = pd.DataFrame({
            "data": pd.date_range(start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                                  periods=len(daily.Variables(0).ValuesAsNumpy()),
                                  freq=pd.Timedelta(seconds=daily.Interval())).tz_convert("Europe/Rome").date,
            "tmax": daily.Variables(0).ValuesAsNumpy(),
            "tmin": daily.Variables(1).ValuesAsNumpy(),
            "precip": daily.Variables(2).ValuesAsNumpy()
        })
        return current_data, daily_data
    except Exception as e:
        st.error(f"❌ Errore meteo: {str(e)}")
        return None, None

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
        st.rerun()

if "lat" not in st.session_state:
    st.session_state.lat = 42.056747
    st.session_state.lon = 12.574791
    st.session_state.city_name = "Monterotondo, Italia"

st.sidebar.write(f"📍 **{st.session_state.city_name}**")
st.sidebar.write(f"Lat: {st.session_state.lat:.4f} | Lon: {st.session_state.lon:.4f}")

st.sidebar.header("📂 Dati storici")
csv_file = st.sidebar.file_uploader("Carica CSV (opzionale)", type=["csv"])

if csv_file is not None:
    df = pd.read_csv(csv_file)
    st.sidebar.success("✅ CSV caricato")
else:
    df = load_data()

# ==============================
# METEO ATTUALE + PREVISIONE
# ==============================
st.header("🌤️ Meteo Attuale e Previsione")

current, daily = get_weather_forecast(st.session_state.lat, st.session_state.lon)

if current:
    col1, col2 = st.columns(2, gap="large")
    
    # Box 1 - Condizioni Attuali (stile card/bottone)
    with col1:
        st.markdown("""
        <div style="background: linear-gradient(145deg, rgba(255,255,255,0.25), rgba(255,255,255,0.1));
                    backdrop-filter: blur(12px); border-radius: 20px; padding: 24px;
                    border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.2);">
            <h3 style="margin:0; color:white;">📍 Condizioni Attuali</h3>
            <hr style="margin:15px 0;">
        """, unsafe_allow_html=True)
        
        st.metric("🌡️ Temperatura", f"{current['temperatura']:.1f} °C")
        st.metric("🌡️ Percepita", f"{current['percepita']:.1f} °C")
        st.metric("💧 Umidità", f"{current['umidità']:.0f} %")
        st.metric("💨 Vento", f"{current['vento']:.1f} km/h")
        st.metric("☁️ Nuvolosità", f"{current['nuvolosità']:.0f} %")
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Box 2 - Previsione 3 Giorni
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(145deg, rgba(255,255,255,0.25), rgba(255,255,255,0.1));
                    backdrop-filter: blur(12px); border-radius: 20px; padding: 24px;
                    border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 8px 32px rgba(0,0,0,0.2);">
            <h3 style="margin:0; color:white;">📅 Previsione 3 Giorni</h3>
            <hr style="margin:15px 0;">
        """, unsafe_allow_html=True)
        
        if daily is not None:
            for _, row in daily.iterrows():
                emoji = "🌧️" if row['precip'] > 1 else "☀️"
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.15); border-radius: 12px; padding: 14px; margin: 10px 0;">
                    <strong>{row['data'].strftime('%A %d %b')}</strong> {emoji}<br>
                    <span style="font-size:1.2em;">{row['tmin']:.1f}° / {row['tmax']:.1f}°C</span><br>
                    <small>🌧️ {row['precip']:.1f} mm</small>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ==============================
# ANALISI STORICHE
# ==============================
st.header("📊 Analisi storiche a Monterotondo (2000–2025)")

years = sorted(df.index.year.unique())
default_years = [y for y in [2024, 2025] if y in years]

selected_years = st.multiselect("Seleziona anni da confrontare", years, 
                               default=default_years if default_years else years[-3:])

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
    st.metric(f"Temp. media {last_year}", f"{df_last['temperatura'].mean():.1f} °C")
with col2:
    st.metric(f"Precip. totale {last_year}", f"{df_last['precipitazione'].sum():.0f} mm")

# Grafico Temperature
st.subheader("Andamento temperature (minime e massime giornaliere)")
df_daily = df_filtered.resample('D').agg({'temperatura': ['min', 'max']}).dropna()
if not df_daily.empty:
    df_daily.columns = ['temp_min', 'temp_max']
    df_daily = df_daily.reset_index()
    df_daily['anno'] = df_daily['time'].dt.year.astype(str)
    
    chart_temp = alt.Chart(df_daily).mark_bar(opacity=0.75).encode(
        x=alt.X('monthdate(time):O', title='Data'),
        y=alt.Y('temp_max:Q', title='Temperatura (°C)'),
        y2=alt.Y2('temp_min:Q'),
        color=alt.Color('anno:N', title='Anno'),
        tooltip=['time', 'temp_max', 'temp_min', 'anno']
    ).properties(height=420)
    st.altair_chart(chart_temp, use_container_width=True)

st.caption("Fonte: Open-Meteo | Dati storici in Parquet")
