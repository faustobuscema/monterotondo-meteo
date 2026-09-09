# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import requests
import openmeteo_requests
from retry_requests import retry
import requests_cache
from pathlib import Path

st.set_page_config(
    page_title="Monterotondo Meteo - Advanced Dashboard",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# DESIGN & CSS CUSTOM (UI/UX)
# ------------------------------
st.markdown("""
<style>
    .main {
        background-color: transparent;
    }
    h1, h2, h3 {
        letter-spacing: -0.5px;
    }
    .weather-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 24px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        margin-bottom: 20px;
        height: 100%;
    }
    .weather-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255, 255, 255, 0.3);
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.35);
    }
    .row-item { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        padding: 10px 0; 
        border-bottom: 1px solid rgba(255, 255, 255, 0.06); 
        font-size: 0.95rem;
    }
    .forecast-row { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        padding: 12px 16px; 
        margin: 8px 0; 
        background: rgba(255, 255, 255, 0.03); 
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        transition: all 0.2s ease;
    }
    .forecast-row:hover { 
        background: rgba(255, 255, 255, 0.08); 
        transform: scale(1.01);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

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
        script_dir = Path(__file__).parent
        file_path = script_dir / "dati_meteo.csv"
        df = pd.read_csv(file_path)
        return prepare_dataframe(df)
    except Exception as e:
        st.error(f"❌ Errore caricamento file dati: {e}")
        st.stop()

def prepare_dataframe(df):
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    df.rename(columns={
        'temperature_2m': 'temperatura',
        'relative_humidity_2m': 'umidità',
        'rain': 'precipitazione',
        'wind_speed_10m': 'vento',
        'cloud_cover': 'nuvolosità',
        'pressure_msl': 'pressione'
    }, inplace=True, errors='ignore')
    
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    return df

# ------------------------------
# Funzioni meteo & Utility
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

def get_weather_code_description(code):
    mapping = {
        0: ("☀️", "Sereno"),
        1: ("🌤️", "Principalmente sereno"),
        2: ("⛅", "Parzialmente nuvoloso"),
        3: ("☁️", "Coperto"),
        45: ("🌫️", "Nebbia"),
        48: ("🌫️", "Brina/Nebbia con rel. brina"),
        51: ("🌦️", "Pioviggine leggera"),
        53: ("🌧️", "Pioviggine moderata"),
        55: ("🌧️", "Pioviggine densa"),
        61: ("🌧️", "Pioggia debole"),
        63: ("🌧️", "Pioggia moderata"),
        65: ("🌧️", "Pioggia forte"),
        71: ("🌨️", "Neve debole"),
        73: ("🌨️", "Neve moderata"),
        75: ("❄️", "Neve forte"),
        95: ("⚡", "Temporale"),
    }
    return mapping.get(code, ("🌦️", "Variabile"))

def get_weather_forecast(lat, lon):
    try:
        client = get_openmeteo_client()
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": ["temperature_2m", "apparent_temperature", "relative_humidity_2m",
                       "precipitation", "rain", "showers", "cloud_cover", "wind_speed_10m", "weather_code"],
            "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "weather_code"],
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
            "weather_code": int(current.Variables(8).Value())
        }

        daily = response.Daily()
        daily_data = pd.DataFrame({
            "data": pd.date_range(start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                                  periods=len(daily.Variables(0).ValuesAsNumpy()),
                                  freq=pd.Timedelta(seconds=daily.Interval())).tz_convert("Europe/Rome").date,
            "tmax": daily.Variables(0).ValuesAsNumpy(),
            "tmin": daily.Variables(1).ValuesAsNumpy(),
            "precip": daily.Variables(2).ValuesAsNumpy(),
            "weather_code": daily.Variables(3).ValuesAsNumpy().astype(int)
        })
        return current_data, daily_data
    except Exception as e:
        st.error(f"❌ Errore nel recupero dati meteo: {str(e)}")
        return None, None

# ==============================
# SIDEBAR
# ==============================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/partly-cloudy-day--v1.png", width=70)
    st.title("Meteo Control Panel")
    
    st.markdown("### 🌍 Localizzazione")
    city = st.text_input("Cerca Comune Italiano", value="Monterotondo")

    if st.button("🔍 Aggiorna Posizione", use_container_width=True):
        lat, lon, city_name, country = geocode_city(city)
        if lat is not None:
            st.session_state.lat = lat
            st.session_state.lon = lon
            st.session_state.city_name = f"{city_name}, {country}"
            st.success(f"Trovato: {city_name}")
            st.rerun()
        else:
            st.error("Città non trovata.")

    if "lat" not in st.session_state:
        st.session_state.lat = 42.056747
        st.session_state.lon = 12.574791
        st.session_state.city_name = "Monterotondo, Italia"

    st.markdown(f"""
    <div style="background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; font-size: 0.85rem; margin-bottom: 20px;">
        📍 <b>{st.session_state.city_name}</b><br>
        Lat: {st.session_state.lat:.4f} | Lon: {st.session_state.lon:.4f}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📂 Gestione Dati Storici")
    csv_file = st.file_uploader("Carica CSV personalizzato", type=["csv"])

    if csv_file is not None:
        df_raw = pd.read_csv(csv_file)
        df = prepare_dataframe(df_raw)
        st.success("✅ CSV caricato con successo")
    else:
        df = load_data()

# ==============================
# CORPO PRINCIPALE - HEADER & REALTIME
# ==============================
st.title("🌦️ Dashboard Meteorologica")
st.markdown(f"Monitoraggio in tempo reale e analisi climatiche avanzate per **{st.session_state.city_name}**.")
st.markdown("")

current, daily = get_weather_forecast(st.session_state.lat, st.session_state.lon)

if current:
    icon_emoji, condition_text = get_weather_code_description(current['weather_code'])
    
    col1, col2 = st.columns(2, gap="large")

    with col1:
        html_1 = f"""<div class="weather-card">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
<h3 style="margin:0; font-size:1.3rem;">📍 Condizioni Attuali</h3>
<span style="font-size: 2.2rem;" title="{condition_text}">{icon_emoji}</span>
</div>
<div style="font-size: 0.9rem; color: #a0a0a0; margin-bottom: 15px;">Stato: <b>{condition_text}</b></div>
<div class="row-item"><span>🌡️ Temperatura</span><strong>{current['temperatura']:.1f} °C</strong></div>
<div class="row-item"><span>🤔 Percepita</span><strong>{current['percepita']:.1f} °C</strong></div>
<div class="row-item"><span>💧 Umidità</span><strong>{current['umidità']:.0f} %</strong></div>
<div class="row-item"><span>💨 Vento</span><strong>{current['vento']:.1f} km/h</strong></div>
<div class="row-item" style="border:none;"><span>☁️ Copertura nuvolosa</span><strong>{current['nuvolosità']:.0f} %</strong></div>
</div>"""
        st.markdown(html_1, unsafe_allow_html=True)

    with col2:
        forecast_rows = ""
        if daily is not None:
            for _, row in daily.iterrows():
                d_icon, _ = get_weather_code_description(row['weather_code'])
                forecast_rows += f'<div class="forecast-row"><span><b>{row["data"].strftime("%A %d")}</b></span><span style="font-size: 1.2rem;">{d_icon}</span><span>🌧️ {row["precip"]:.1f} mm</span><span><b style="color:#FF6B6B">{row["tmax"]:.0f}°</b> / <b style="color:#4D96FF">{row["tmin"]:.0f}°</b></span></div>'
        
        html_2 = f"""<div class="weather-card">
<h3 style="margin:0 0 15px 0; font-size:1.3rem;">📅 Previsioni a 3 Giorni</h3>
<div style="display: flex; flex-direction: column; justify-content: space-around; height: 80%;">
{forecast_rows}
</div>
</div>"""
        st.markdown(html_2, unsafe_allow_html=True)

# ==============================
# ANALISI STORICHE
# ==============================
st.markdown("---")
st.header("📊 Analisi Storiche e Trend Climatici")

years = sorted(df.index.year.unique())
default_years = [y for y in [2024, 2025] if y in years]

selected_years = st.multiselect(
    "Filtra e confronta gli anni storici:", 
    years, 
    default=default_years if default_years else years[-3:]
)

if not selected_years:
    st.warning("⚠️ Seleziona almeno un anno dal selettore sopra per visualizzare le analisi.")
    st.stop()

df_filtered = df[df.index.year.isin(selected_years)].copy()
df_filtered['anno'] = df_filtered.index.year
df_filtered['mese'] = df_filtered.index.month

last_year = max(selected_years)
df_last = df_filtered[df_filtered.index.year == last_year]

mcol1, mcol2, mcol3 = st.columns(3)
with mcol1:
    st.metric(label=f"🌡️ Temp. Media ({last_year})", value=f"{df_last['temperatura'].mean():.1f} °C" if not df_last.empty else "N/D")
with mcol2:
    st.metric(label=f"🌧️ Piogge Totali ({last_year})", value=f"{df_last['precipitazione'].sum():.0f} mm" if 'precipitazione' in df_last.columns and not df_last.empty else "N/D")
with mcol3:
    st.metric(label=f"💨 Vento Medio ({last_year})", value=f"{df_last['vento'].mean():.1f} km/h" if 'vento' in df_last.columns and not df_last.empty else "N/D")

st.markdown("")

st.subheader("📈 Andamento Termico Giornaliero (Min / Max)")
df_daily = df_filtered.resample('D').agg({'temperatura': ['min', 'max']}).dropna()
if not df_daily.empty:
    df_daily.columns = ['temp_min', 'temp_max']
    df_daily = df_daily.reset_index()
    df_daily['anno'] = df_daily['time'].dt.year.astype(str)
    
    chart_temp = alt.Chart(df_daily).mark_bar(opacity=0.6, width=2).encode(
        x=alt.X('monthdate(time):O', title='Periodo dell\'anno', axis=alt.Axis(labelAngle=0, format='%b')),
        y=alt.Y('temp_max:Q', title='Temperatura (°C)', scale=alt.Scale(zero=False)),
        y2=alt.Y2('temp_min:Q'),
        color=alt.Color('anno:N', title='Anno', scale=alt.Scale(scheme='tableau10')),
        tooltip=[
            alt.Tooltip('time:T', title='Data', format='%d %B'),
            alt.Tooltip('temp_max:Q', title='Max (°C)', format='.1f'),
            alt.Tooltip('temp_min:Q', title='Min (°C)', format='.1f'),
            alt.Tooltip('anno:N', title='Anno')
        ]
    ).properties(height=400).interactive()
    
    st.altair_chart(chart_temp, use_container_width=True)

st.subheader("🌧️ Bilancio Idrico: Precipitazioni Mensili")
if 'precipitazione' in df_filtered.columns:
    df_prec = df_filtered.groupby(['anno', 'mese'])['precipitazione'].sum().reset_index()
    month_names = {1: 'Gen', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'Mag', 6: 'Gug', 7: 'Lug', 8: 'Ago', 9: 'Set', 10: 'Ott', 11: 'Nov', 12: 'Dic'}
    df_prec['nome_mese'] = df_prec['mese'].map(month_names)

    chart_prec = alt.Chart(df_prec).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X('nome_mese:O', sort=list(month_names.values()), title='Mese'),
        y=alt.Y('precipitazione:Q', title='Precipitazioni Totali (mm)'),
        color=alt.Color('anno:N', title='Anno', scale=alt.Scale(scheme='tableau10')),
        column=alt.Column('anno:N', title=None),
        tooltip=[alt.Tooltip('anno:N', title='Anno'), alt.Tooltip('nome_mese:N', title='Mese'), alt.Tooltip('precipitazione:Q', title='Mm', format='.1f')]
    ).properties(height=280, width=120)

    st.altair_chart(chart_prec)

st.subheader("📋 Tabelle Dettaglio Giornaliero a Confronto")

def get_yearly_table(df_y):
    agg_dict = {'temperatura': ['min', 'max']}
    if 'precipitazione' in df_y.columns:
        agg_dict['precipitazione'] = 'sum'
    if 'vento' in df_y.columns:
        agg_dict['vento'] = 'mean'
    if 'umidità' in df_y.columns:
        agg_dict['umidità'] = 'mean'

    df_t = df_y.resample('D').agg(agg_dict)
    if isinstance(df_t.columns, pd.MultiIndex):
        df_t.columns = ['_'.join(col).strip() for col in df_t.columns.values]

    rename_cols = {
        'temperatura_min': 'Temp Min (°C)',
        'temperatura_max': 'Temp Max (°C)',
        'precipitazione_sum': 'Precipitazioni (mm)',
        'vento_mean': 'Vento Medio (km/h)',
        'umidità_mean': 'Umidità Media (%)'
    }
    df_t = df_t.rename(columns=rename_cols).reset_index()
    df_t = df_t.sort_values(by='time', ascending=False)
    
    # Arrotondamento a 1 cifra decimale per vento e umidità
    if 'Vento Medio (km/h)' in df_t.columns:
        df_t['Vento Medio (km/h)'] = df_t['Vento Medio (km/h)'].round(1)
    if 'Umidità Media (%)' in df_t.columns:
        df_t['Umidità Media (%)'] = df_t['Umidità Media (%)'].round(1)

    df_t['Data'] = df_t['time'].dt.strftime('%d-%m-%Y')

    cols_to_show = ['Data', 'Temp Min (°C)', 'Temp Max (°C)']
    if 'Precipitazioni (mm)' in df_t.columns:
        cols_to_show.append('Precipitazioni (mm)')
    if 'Vento Medio (km/h)' in df_t.columns:
        cols_to_show.append('Vento Medio (km/h)')
    if 'Umidità Media (%)' in df_t.columns:
        cols_to_show.append('Umidità Media (%)')

    return df_t[cols_to_show]

# Mostra tabelle affiancate se ci sono almeno 2 anni selezionati
comparison_years = sorted(selected_years)[-2:] if len(selected_years) >= 2 else selected_years

if len(comparison_years) == 2:
    tcol1, tcol2 = st.columns(2)
    y1, y2 = comparison_years
    
    with tcol1:
        st.markdown(f"**Anno {y1}**")
        df_y1 = df_filtered[df_filtered['anno'] == y1]
        st.dataframe(get_yearly_table(df_y1), use_container_width=True, hide_index=True)
        
    with tcol2:
        st.markdown(f"**Anno {y2}**")
        df_y2 = df_filtered[df_filtered['anno'] == y2]
        st.dataframe(get_yearly_table(df_y2), use_container_width=True, hide_index=True)
else:
    y1 = comparison_years[0]
    st.markdown(f"**Anno {y1}**")
    df_y1 = df_filtered[df_filtered['anno'] == y1]
    st.dataframe(get_yearly_table(df_y1), use_container_width=True, hide_index=True)

with st.expander("🔍 Visualizza Matrice di Correlazione Avanzata"):
    corr_vars = ['temperatura', 'umidità', 'precipitazione', 'vento', 'nuvolosità', 'pressione']
    existing_vars = [v for v in corr_vars if v in df_filtered.columns]
    if len(existing_vars) >= 2:
        corr_matrix = df_filtered[existing_vars].corr().stack().reset_index()
        corr_matrix.columns = ['var1', 'var2', 'correlazione']
        
        heatmap = alt.Chart(corr_matrix).mark_rect().encode(
            x=alt.X('var1:O', title=None), 
            y=alt.Y('var2:O', title=None),
            color=alt.Color('correlazione:Q', scale=alt.Scale(scheme='magma', domain=[-1,1]))
        ).properties(width=500, height=500)
        
        text = alt.Chart(corr_matrix).mark_text(fontSize=11).encode(
            x='var1:O', y='var2:O', 
            text=alt.Text('correlazione:Q', format='.2f'),
            color=alt.condition(alt.datum.correlazione > 0.5, alt.value('white'), alt.value('black'))
        )
        st.altair_chart(heatmap + text, use_container_width=True)

with st.expander("📄 Esamina gli ultimi record grezzi filtrati"):
    st.dataframe(df_filtered.tail(1000), use_container_width=True)

st.markdown("---")
st.caption("🚀 **Monterotondo Meteo Dashboard** — Powered by Streamlit & Open-Meteo API.")
