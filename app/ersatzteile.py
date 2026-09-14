"""Ersatzteil-Verfügbarkeit aus einer kleinen Katalogdatei. Kein Modell, reine Begriffssuche."""
import json
from pathlib import Path

KATALOG_PFAD = Path(__file__).resolve().parent.parent / "data" / "ersatzteile.json"
FALLBACK = "Verfügbarkeit wird geprüft"


def lade_katalog(pfad=None) -> list[dict]:
    p = Path(pfad) if pfad else KATALOG_PFAD
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []


def hinweise(extraktion: dict, katalog: list[dict] | None = None) -> list[dict]:
    katalog = lade_katalog() if katalog is None else katalog
    ergebnis = []
    for a in extraktion.get("anliegen") or []:
        if a.get("kategorie") != "ersatzteil":
            continue
        beschreibung = (a.get("beschreibung") or "").lower()
        treffer = next((k for k in katalog if any(b in beschreibung for b in k["begriffe"])), None)
        if treffer:
            ergebnis.append({"teil": treffer["teil"], "status": treffer["status"]})
        else:
            ergebnis.append({"teil": a.get("beschreibung") or "Ersatzteil", "status": FALLBACK})
    return ergebnis
