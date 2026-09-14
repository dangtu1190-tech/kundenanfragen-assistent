#!/usr/bin/env sh
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  echo "Hinweis: .env fehlt. Der Server startet trotzdem und zeigt die"
  echo "vorberechneten Ergebnisse aus data/. Ein neuer Modellaufruf scheitert"
  echo "dann am fehlenden Schluessel: .env.example kopieren, LLM_API_KEY setzen."
fi
python -m pip install -r requirements.txt -q
python -m uvicorn app.main:app --port 8040
