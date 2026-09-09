import pandas as pd

print("🚀 Inizio conversione del file...")

# Leggi il CSV
df = pd.read_csv("dati_meteo.csv")

print(f"✅ File CSV letto correttamente! Righe: {len(df):,}")

# Converti in Parquet (molto più efficiente)
df.to_parquet("dati_meteo.parquet", 
              compression='gzip', 
              index=False)

print("✅ Conversione completata!")
print(f"   File creato: dati_meteo.parquet")
print(f"   Dimensione originale: ~14 MB → Nuova dimensione: molto più piccola")