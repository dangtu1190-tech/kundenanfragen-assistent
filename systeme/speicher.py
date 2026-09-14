"""JSON-Dateien der Mock-Systemlandschaft lesen und schreiben.

Der Datenordner wird zur Laufzeit ermittelt (nicht beim Import), damit Tests
ihn über die Umgebungsvariable SYSTEME_DATEN umschalten können.
"""
import json
import os
from pathlib import Path


def daten_ordner() -> Path:
    return Path(os.getenv("SYSTEME_DATEN") or Path(__file__).parent / "daten")


def lies(name: str):
    pfad = daten_ordner() / name
    return json.loads(pfad.read_text(encoding="utf-8"))


def schreib(name: str, obj) -> None:
    pfad = daten_ordner() / name
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
