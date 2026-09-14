"""JSON-Dateien lesen und schreiben: Mails, Ergebnisse, Konfiguration.

Einzige Datenhaltung der Demo."""
import json
import os
import threading
from pathlib import Path

DATEN = Path(__file__).resolve().parent.parent / "data"

# Dieselbe Begründung wie in systeme/crm.py: FastAPI führt synchrone Routen in
# einem Threadpool aus, mehrere gleichzeitige Anfragen laufen also in echten
# Parallel-Threads. Lesen, Ändern und Schreiben derselben Datei muss deshalb
# als ein Block laufen, sonst vergeben zwei parallele POST /api/mails dieselbe
# Mail-ID oder eine Statusänderung überschreibt die andere. Ein Lock je Prozess
# reicht, weil die Dateien in data/ ohnehin nur von diesem Prozess beschrieben
# werden; genau deshalb ist der Server auf eine Instanz ausgelegt (README, 12).
SPERRE = threading.Lock()


def _lies(pfad: Path, leer):
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.is_file() else leer


def _schreib(pfad: Path, obj) -> None:
    """Schreibt über eine Zwischendatei im selben Verzeichnis und benennt um.

    os.replace ist auf einem Dateisystem atomar: entweder steht der alte oder
    der neue Inhalt in der Datei, nie ein halb geschriebener. Ein direktes
    write_text ließe bei einem Absturz oder einem parallelen Leser mitten im
    Schreiben eine abgeschnittene und damit unlesbare JSON-Datei zurück. Der
    Name der Zwischendatei enthält Prozess- und Thread-Kennung: unter Windows
    scheitert os.replace, wenn ein zweiter Thread dieselbe Zwischendatei noch
    offen hält.
    """
    pfad.parent.mkdir(parents=True, exist_ok=True)
    zwischen = pfad.with_name(f"{pfad.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    zwischen.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(zwischen, pfad)


def lade_mails(pfad=None) -> list[dict]:
    return _lies(Path(pfad) if pfad else DATEN / "mails.json", [])


def speichere_mails(mails: list[dict], pfad=None) -> None:
    _schreib(Path(pfad) if pfad else DATEN / "mails.json", mails)


def lade_ergebnisse(pfad=None) -> dict[str, dict]:
    return _lies(Path(pfad) if pfad else DATEN / "ergebnisse.json", {})


def speichere_ergebnisse(ergebnisse: dict[str, dict], pfad=None) -> None:
    _schreib(Path(pfad) if pfad else DATEN / "ergebnisse.json", ergebnisse)


def lade_konfig(pfad=None) -> dict:
    """Basisdatum und Versendername aus data/konfig.json."""
    return _lies(Path(pfad) if pfad else DATEN / "konfig.json", {})
