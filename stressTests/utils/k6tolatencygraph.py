import pandas as pd
import matplotlib.pyplot as plt
import sys

# Carica il CSV dall'argomento della riga di comando
if len(sys.argv) < 2:
    print("Usage: python k6tointerationtime.py <path_to_csv>")
    sys.exit(1)
csv_path = sys.argv[1]
# Leggi il CSV
df = pd.read_csv(csv_path)

# Filtra solo la metrica che vuoi graficare, ad esempio http_req_duration
metric = 'http_req_duration'
df_metric = df[df['metric_name'] == metric]

# Converte timestamp (secondi da UNIX EPOCH) in datetime
df_metric['datetime'] = pd.to_datetime(df_metric['timestamp'], unit='s')
# Converti il datetime in tempo relativo dall'inizio del test
df_metric['relative_time'] = (df_metric['datetime'] - df_metric['datetime'].min()).dt.total_seconds()

# Plot
plt.figure(figsize=(10,5))
plt.plot(df_metric['relative_time'], df_metric['metric_value'], marker='.', linestyle='-')
plt.title(f'Latenza richieste http')
plt.xlabel('Tempo [s]')
plt.ylabel('Latenza [ms]')
plt.grid()
plt.tight_layout()
plt.show()