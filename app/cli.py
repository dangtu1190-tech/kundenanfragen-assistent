"""Alle Mails verarbeiten und Ergebnisse schreiben.

    python -m app.cli            alle Mails, überspringt bereits vorhandene Ergebnisse
    python -m app.cli --neu      alles neu verarbeiten
    python -m app.cli --nur m03  nur diese Mail
    python -m app.cli --pages    zusätzlich docs/data/ für GitHub Pages aktualisieren

Ohne SYSTEME_BASE_URL läuft die Systemlandschaft im Prozess: die angelegten
CRM-Tickets landen dann in systeme/daten/tickets.json. Für einen sauberen
Ausgangsstand vor dem Aufzeichnungslauf diese Datei auf [] zurücksetzen.
"""
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from app.integration import Systeme
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite
from app.speicher import DATEN, lade_ergebnisse, lade_konfig as lade_daten_konfig, lade_mails, speichere_ergebnisse

PAGES = Path(__file__).resolve().parent.parent / "docs" / "data"


def kopiere_fuer_pages() -> None:
    """Kopiert die Dateien für die statische Seite.

    Ohne Ergebnisse (noch kein Lauf gegen ein Modell) wird nur gemeldet und
    übersprungen: ein Abbruch mitten im Kopieren wäre hier keine Hilfe.
    """
    PAGES.mkdir(parents=True, exist_ok=True)
    for name in ("mails.json", "ergebnisse.json"):
        quelle = DATEN / name
        if not quelle.is_file():
            print(f"{name} fehlt in data/, wird nicht kopiert (erst einen Lauf ohne --pages machen).",
                  file=sys.stderr)
            continue
        shutil.copyfile(quelle, PAGES / name)


def _kurzfassung(erg: dict) -> str:
    if erg["extraktion_fehler"]:
        return erg["extraktion_fehler"]
    kategorien = ", ".join(a["kategorie"] for a in erg["extraktion"]["anliegen"]) or "kein Anliegen"
    text = f"{kategorien}; {erg['zustaendigkeit']}, {erg['dringlichkeit']}"
    if erg["ticket"]:
        text += f", {erg['ticket']['ticket_id']}"
    if erg["integrationsfehler"]:
        text += f"; {len(erg['integrationsfehler'])} Integrationsfehler"
    return text


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--neu", action="store_true")
    p.add_argument("--nur")
    p.add_argument("--pages", action="store_true")
    args = p.parse_args(argv)

    konfig = lade_konfig()
    if not konfig.api_key:
        print("LLM_API_KEY fehlt (siehe .env.example).", file=sys.stderr)
        return 2
    client = LLMClient(konfig)
    systeme = Systeme.aus_umgebung()
    heute = date.fromisoformat(lade_daten_konfig()["basisdatum"])
    ergebnisse = lade_ergebnisse()
    print(f"Anbieter {konfig.provider}, Modell {konfig.model}, heute {heute}")

    for mail in lade_mails():
        if args.nur and mail["id"] != args.nur:
            continue
        if not args.neu and not args.nur and mail["id"] in ergebnisse:
            continue
        erg = verarbeite(mail, client, heute, systeme)
        ergebnisse[mail["id"]] = erg
        speichere_ergebnisse(ergebnisse)
        print(f"{mail['id']} {erg['status']:16} {erg['dauer_ms']:5} ms  {_kurzfassung(erg)}")

    if args.pages:
        kopiere_fuer_pages()
        print("docs/data aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
