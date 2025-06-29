FROM python:3.13-slim

WORKDIR /app

# Copia il file dei requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice sorgente
COPY . .

# Espone la porta usata da uvicorn
EXPOSE 5000

# Comando per avviare il server FastAPI
CMD ["main:app"]
