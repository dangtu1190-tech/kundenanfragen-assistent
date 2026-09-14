#!/usr/bin/env sh
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "Hinweis: .env fehlt. Der Server startet trotzdem und zeigt die"
  echo "vorberechneten Ergebnisse aus data/. Fuer einen neuen Modellaufruf:"
  echo "Ollama lokal starten (Standard, kein Schluessel noetig) oder"
  echo ".env.example kopieren und einen anderen Anbieter eintragen."
fi
python -m pip install -r requirements.txt -q
python -m uvicorn app.main:app --port 8040
