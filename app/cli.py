"""Alle Mails verarbeiten und Ergebnisse schreiben.

    python -m app.cli            alle Mails, überspringt bereits vorhandene Ergebnisse
    python -m app.cli --neu      alles neu verarbeiten
    python -m app.cli --nur m03  nur diese Mail
    python -m app.cli --pages    zusätzlich docs/data/ für GitHub Pages aktualisieren
"""
import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from app.kalender import lade_kalender
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite
from app.speicher import DATEN, lade_ergebnisse, lade_mails, speichere_ergebnisse

PAGES = Path(__file__).resolve().parent.parent / "docs" / "data"


def kopiere_fuer_pages() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    for name in ("mails.json", "ergebnisse.json"):
        shutil.copyfile(DATEN / name, PAGES / name)


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
    kalender = lade_kalender(DATEN / "kalender.json")
    heute = date.fromisoformat(kalender["basisdatum"])
    ergebnisse = lade_ergebnisse()
    print(f"Anbieter {konfig.provider}, Modell {konfig.model}, heute {heute}")

    for mail in lade_mails():
        if args.nur and mail["id"] != args.nur:
            continue
        if not args.neu and not args.nur and mail["id"] in ergebnisse:
            continue
        erg = verarbeite(mail, client, kalender, heute)
        ergebnisse[mail["id"]] = erg
        speichere_ergebnisse(ergebnisse)
        kurz = erg["extraktion_fehler"] or f"{len(erg['extraktion']['anliegen'])} Anliegen, {erg['extraktion']['zustaendigkeit']}, Termin {erg['termin']}"
        print(f"{mail['id']} {erg['status']:16} {erg['dauer_ms']:5} ms  {kurz}")

    if args.pages:
        kopiere_fuer_pages()
        print("docs/data aktualisiert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
