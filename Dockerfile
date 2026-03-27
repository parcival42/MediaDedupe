FROM python:3.12-slim

# System-Abhängigkeiten: ffmpeg für Video-Analyse
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python-Abhängigkeiten zuerst (Layer-Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App-Dateien
COPY app.py engine.py frontend.html report_template.py translations.js ./

# Datenbank + Arbeitsverzeichnis als Volume
ENV DUPFINDER_DATA=/data
VOLUME ["/data"]

EXPOSE 8080

# Medienverzeichnis muss beim Start als -d angegeben werden
ENTRYPOINT ["python", "app.py", "--host", "0.0.0.0"]
CMD ["--port", "8080"]
