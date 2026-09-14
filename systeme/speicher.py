"""JSON-Dateien der Mock-Systemlandschaft lesen und schreiben.

Der Datenordner wird zur Laufzeit ermittelt (nicht beim Import), damit Tests
ihn über die Umgebungsvariable SYSTEME_DATEN umschalten können.
"""
import json
import os
import threading
from pathlib import Path


def daten_ordner() -> Path:
    return Path(os.getenv("SYSTEME_DATEN") or Path(__file__).parent / "daten")


def lies(name: str):
    pfad = daten_ordner() / name
    return json.loads(pfad.read_text(encoding="utf-8"))


def schreib(name: str, obj) -> None:
    """Schreibt über eine Zwischendatei im selben Verzeichnis und benennt um.

    Wie app/speicher.py: os.replace ist atomar, ein direktes write_text ließe
    bei einem Absturz mitten im Schreiben eine abgeschnittene tickets.json
    zurück, die beim nächsten Lesen gar nicht mehr zu parsen wäre.
    """
    pfad = daten_ordner() / name
    pfad.parent.mkdir(parents=True, exist_ok=True)
    zwischen = pfad.with_name(f"{pfad.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    zwischen.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(zwischen, pfad)
