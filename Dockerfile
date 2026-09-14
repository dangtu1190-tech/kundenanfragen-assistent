# syntax=docker/dockerfile:1
# Stufe 1: Abhängigkeiten in ein eigenes Prefix installieren. pip-Cache und
# Build-Reste bleiben in dieser Stufe zurück.
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stufe 2: Laufzeitbild. Enthält nur Python, die installierten Pakete und die
# Anwendung. Keine Konfigurationswerte im Image; alles kommt aus Umgebungsvariablen.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8040 \
    LIVE_MODELLAUFRUFE=0
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /install /usr/local
# data/ gehört dem Laufzeit-User: der Server schreibt Status und neue Mails
# dorthin. Im Container ist das flüchtig (siehe README, Betrieb).
COPY --chown=app:app app/ app/
COPY --chown=app:app data/ data/
COPY --chown=app:app docs/index.html docs/index.html
# Dasselbe Image kann zwei Rollen: als App (app.main:app, Port 8040) oder als
# Mock-Systemlandschaft (systeme.main:app, Port 8050, siehe docker-compose.yml
# und infra/azure/main.tf). systeme/daten/ enthält die Ausgangsdaten der Mocks,
# tickets.json enthält die 15 Tickets des aufgezeichneten Laufs (data/ergebnisse.json)
# und wird zur Laufzeit weiter beschrieben; im Container ist das flüchtig.
COPY --chown=app:app systeme/ systeme/
USER app
EXPOSE 8040
# /api/health, nicht /api/status: der Status ruft die Systemlandschaft wirklich
# auf. Als Healthcheck würde ein Ausfall des systeme-Containers diesen hier
# fälschlich als ungesund melden, obwohl die App selbst läuft.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8040'), timeout=3)" || exit 1
# exec, damit uvicorn PID 1 ist und Stopp-Signale direkt bekommt. Der Compose-
# Dienst "systeme" überschreibt dieses CMD mit dem uvicorn-Aufruf für systeme.main:app.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8040}"]
