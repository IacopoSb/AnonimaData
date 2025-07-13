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

# Filtra solo la metrica 'iteration_duration'
df_iter = df[df['metric_name'] == 'iteration_duration']

# Converte timestamp in datetime
df_iter['datetime'] = pd.to_datetime(df_iter['timestamp'], unit='s')
# Converti il datettime in tempo relativo dall'inizio del test
df_iter['relative_time'] = (df_iter['datetime'] - df_iter['datetime'].min()).dt.total_seconds()

# Se hai la colonna 'group' che rappresenta l'utente (VU), puoi usarla.
# In caso contrario, ogni iterazione è per ogni VU. Qui raggruppo per tempo e uso il valore.

plt.figure(figsize=(12,6))
plt.plot(df_iter['relative_time'], df_iter['metric_value'], marker='o', linestyle='-', label='iteration_duration')

plt.title('Durata di ogni iterazione nel tempo')
plt.xlabel('Tempo [s]')
plt.ylabel('Durata iterazione [ms]')
plt.grid()
plt.tight_layout()
plt.show()