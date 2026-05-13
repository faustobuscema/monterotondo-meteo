# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests
import openmeteo_requests
from retry_requests import retry
import requests_cache

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
# Caricamento e preparazione dati
# ------------------------------
@st.cache_data(ttl=3600)
def load_data():
    try:
        df = pd.read_parquet("dati_meteo.parquet")
        st.sidebar.success("✅ Dati storici caricati da Parquet")
        return prepare_dataframe(df)
    except Exception as e:
        st.error(f"❌ Errore caricamento Parquet: {e}")
        st.stop()

def prepare_dataframe(df):
    """Prepara il dataframe (usato sia per Parquet che per CSV)"""
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
    
    # Ottimizzazione memoria
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    return df

# ------------------------------
# Funzioni meteo
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
    df_raw = pd.read_csv(csv_file)
    df = prepare_dataframe(df_raw)
    st.sidebar.success("✅ CSV caricato e preparato")
else:
    df = load_data()

# ==============================
# METEO ATTUALE + PREVISIONE (ANIMATED BUTTONS)
# ==============================
st.header("🌤️ Situazione Meteo")

current, daily = get_weather_forecast(st.session_state.lat, st.session_state.lon)

if current:
    # CSS con Animazioni e Transizioni
    st.markdown("""
    <style>
        .weather-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 25px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            
            /* Animazione base */
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            cursor: pointer;
            margin-bottom: 20px;
            min-height: 380px;
        }

        /* Effetto Sollevamento al passaggio (Hover) */
        .weather-card:hover {
            transform: translateY(-8px);
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.4);
            box-shadow: 0 15px 30px rgba(0,0,0,0.3);
        }

        /* Effetto Pressione al click (Active) */
        .weather-card:active {
            transform: translateY(-2px);
            box-shadow: 0 5px 10px rgba(0,0,0,0.2);
            transition: all 0.1s;
        }

        .row-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .forecast-row { 
            display: flex; justify-content: space-between; align-items: center; 
            padding: 10px; margin: 8px 0; background: rgba(0,0,0,0.1); border-radius: 12px;
            transition: background 0.3s;
        }
        .forecast-row:hover { background: rgba(255,255,255,0.1); }
    </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # Box 1: Meteo Attuale (Stringa compatta per evitare bug di rendering)
        html_1 = f"""<div class="weather-card">
<h2 style="margin:0 0 20px 0; font-size:1.4rem; color:white;">📍 Ora a {st.session_state.city_name.split(',')[0]}</h2>
<div class="row-item"><span>🌡️ Temp.</span><strong>{current['temperatura']:.1f} °C</strong></div>
<div class="row-item"><span>🤔 Perc.</span><strong>{current['percepita']:.1f} °C</strong></div>
<div class="row-item"><span>💧 Umid.</span><strong>{current['umidità']:.0f} %</strong></div>
<div class="row-item"><span>💨 Vento</span><strong>{current['vento']:.1f} km/h</strong></div>
<div class="row-item" style="border:none;"><span>☁️ Nuvole</span><strong>{current['nuvolosità']:.0f} %</strong></div>
</div>"""
        st.markdown(html_1, unsafe_allow_html=True)

    with col2:
        # Box 2: Previsioni (Stringa compatta)
        forecast_rows = ""
        if daily is not None:
            for _, row in daily.iterrows():
                emoji = "🌧️" if row['precip'] > 1 else "☀️"
                forecast_rows += f'<div class="forecast-row">' \
                                 f'<span><strong>{row["data"].strftime("%a %d")}</strong></span>' \
                                 f'<span>{emoji} {row["precip"]:.1f}mm</span>' \
                                 f'<span><b style="color:#FF4B4B">{row["tmax"]:.0f}°</b> / <b style="color:#00ACEE">{row["tmin"]:.0f}°</b></span>' \
                                 f'</div>'
        
        html_2 = f'<div class="weather-card">' \
                 f'<h2 style="margin:0 0 20px 0; font-size:1.4rem; color:white;">📅 Prossimi 3 Giorni</h2>' \
                 f'{forecast_rows}</div>'
        
        st.markdown(html_2, unsafe_allow_html=True)

# ==============================
# ANALISI STORICHE
# ==============================
st.header("📊 Analisi storiche a Monterotondo (2000–2025)")

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
    st.metric(f"Temp. media {last_year}", f"{df_last['temperatura'].mean():.1f} °C")
with col2:
    st.metric(f"Precip. totale {last_year}", f"{df_last['precipitazione'].sum():.0f} mm")

# Grafici completi
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

st.subheader("Precipitazioni totali per mese")
df_prec = df_filtered.groupby(['anno', 'mese'])['precipitazione'].sum().reset_index()
chart_prec = alt.Chart(df_prec).mark_bar().encode(
    x='mese:O', y='precipitazione:Q', color='anno:N', column='anno:N'
).properties(height=300)
st.altair_chart(chart_prec, use_container_width=True)

st.subheader("Matrice di correlazione")
corr_vars = ['temperatura', 'umidità', 'precipitazione', 'vento', 'nuvolosità', 'pressione']
existing_vars = [v for v in corr_vars if v in df_filtered.columns]
if len(existing_vars) >= 2:
    corr_matrix = df_filtered[existing_vars].corr().stack().reset_index()
    corr_matrix.columns = ['var1', 'var2', 'correlazione']
    heatmap = alt.Chart(corr_matrix).mark_rect().encode(
        x='var1:O', y='var2:O',
        color=alt.Color('correlazione:Q', scale=alt.Scale(scheme='redblue', domain=[-1,1]))
    ).properties(width=550, height=550)
    text = alt.Chart(corr_matrix).mark_text().encode(
        x='var1:O', y='var2:O', text=alt.Text('correlazione:Q', format='.2f')
    )
    st.altair_chart(heatmap + text, use_container_width=True)

st.subheader("Dati grezzi (ultimi 1000 record)")
st.dataframe(df_filtered.tail(1000), use_container_width=True)

st.caption("Fonte: Open-Meteo | Dati storici in Parquet")