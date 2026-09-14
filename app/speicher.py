"""JSON-Dateien lesen und schreiben: Mails, Ergebnisse. Einzige Datenhaltung der Demo."""
import json
from pathlib import Path

DATEN = Path(__file__).resolve().parent.parent / "data"


def _lies(pfad: Path, leer):
    return json.loads(pfad.read_text(encoding="utf-8")) if pfad.is_file() else leer


def _schreib(pfad: Path, obj) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def lade_mails(pfad=None) -> list[dict]:
    return _lies(Path(pfad) if pfad else DATEN / "mails.json", [])


def speichere_mails(mails: list[dict], pfad=None) -> None:
    _schreib(Path(pfad) if pfad else DATEN / "mails.json", mails)


def lade_ergebnisse(pfad=None) -> dict[str, dict]:
    return _lies(Path(pfad) if pfad else DATEN / "ergebnisse.json", {})


def speichere_ergebnisse(ergebnisse: dict[str, dict], pfad=None) -> None:
    _schreib(Path(pfad) if pfad else DATEN / "ergebnisse.json", ergebnisse)
