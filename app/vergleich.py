"""Modellvergleich gegen handgeschriebene Soll-Werte.

    python -m app.vergleich --modelle gpt-oss:20b,qwen2.5:14b-instruct
    python -m app.vergleich --modelle gpt-4.1-mini --anbieter openai
    python -m app.vergleich --modelle gpt-oss:20b --ausgabe docs/modellvergleich.md

Läuft je Modell Pseudonymisierung, Extraktion und Regeln für alle 15 Mails
(`app.pipeline.extrahiere_und_bewerte`, ohne Systemzugriff und ohne Ticket)
und vergleicht das Ergebnis gegen `data/erwartet.json`. Referenz sind die
Soll-Werte, nicht ein anderes Modell. Schreibt `data/vergleich.json` (Rohdaten
je Mail) und eine Markdown-Tabelle, standardmäßig nach `docs/modellvergleich.md`.
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from app import speicher
from app.llm_client import DEFAULTS, Konfig, LLMClient, lade_konfig
from app.pipeline import extrahiere_und_bewerte

AUSGABE_STANDARD = Path(__file__).resolve().parent.parent / "docs" / "modellvergleich.md"
FELDER = ("kategorien", "zustaendigkeit", "dringlichkeit", "bestellnummer", "kundennummer", "frist")
SPALTEN = (("Modell", None), ("Kategorien", "kategorien"), ("Zuständigkeit", "zustaendigkeit"),
           ("Dringlichkeit", "dringlichkeit"), ("Bestellnummer", "bestellnummer"),
           ("Kundennummer", "kundennummer"), ("Frist", "frist"), ("Schemafehler", "schemafehler"),
           ("Ø Dauer", "mittlere_dauer_ms"))


def konfig_fuer_modell(modell: str, anbieter: str | None, basis: Konfig) -> Konfig:
    """Konfiguration für einen Modelllauf: `model` wird immer überschrieben.

    Ist `--anbieter` gesetzt und weicht er vom Anbieter der Basiskonfiguration
    ab, kommen Basis-URL und Schlüssel-Standard aus `DEFAULTS` für diesen
    Anbieter. LLM_API_KEY aus der Umgebung gilt trotzdem weiter (ein Schlüssel
    in der .env ist nicht an einen bestimmten Anbieter gebunden, ohne ihn
    scheitert sonst jeder Aufruf an einen Schlüssel-Anbieter wie OpenAI still
    als Schemafehler). LLM_BASE_URL dagegen gilt nur, wenn LLM_PROVIDER in der
    Umgebung auch wirklich dem angeforderten Anbieter entspricht, sonst würde
    eine für den Standardanbieter gesetzte URL beim Wechsel fälschlich mitreisen.
    """
    if anbieter and anbieter != basis.provider:
        d = DEFAULTS.get(anbieter, DEFAULTS["openai"])
        base_url = d["base_url"]
        if os.getenv("LLM_BASE_URL") and os.getenv("LLM_PROVIDER", "").lower() == anbieter:
            base_url = os.environ["LLM_BASE_URL"]
        api_key = os.getenv("LLM_API_KEY", d.get("api_key", ""))
        return Konfig(provider=anbieter, base_url=base_url, model=modell, api_key=api_key)
    return Konfig(provider=basis.provider, base_url=basis.base_url, model=modell, api_key=basis.api_key)


def _warne_bei_fehlendem_schluessel(konfig: Konfig) -> None:
    """Ollama braucht keinen echten Schlüssel; jeder andere Anbieter ohne
    LLM_API_KEY würde sonst erst mitten im Lauf als Schemafehler auffallen."""
    if konfig.provider != "ollama" and not konfig.api_key:
        print(f"LLM_API_KEY fehlt, Aufrufe an {konfig.provider} werden scheitern", file=sys.stderr)


def _kurzfassung(erg: dict) -> str:
    if erg["extraktion_fehler"]:
        return erg["extraktion_fehler"]
    kategorien = ", ".join(a["kategorie"] for a in erg["extraktion"]["anliegen"]) or "kein Anliegen"
    return f"{kategorien}; {erg['zustaendigkeit']}, {erg['dringlichkeit']}"


def laufe_modell(client, mails: list[dict], heute: date) -> dict[str, dict]:
    """Führt ein Modell gegen alle Mails aus, mit Fortschrittszeile je Mail."""
    ergebnisse: dict[str, dict] = {}
    for mail in mails:
        erg = extrahiere_und_bewerte(mail, client, heute)
        ergebnisse[erg["mail_id"]] = erg
        print(f"  {erg['mail_id']} {erg['dauer_ms']:5} ms  {_kurzfassung(erg)}")
    return ergebnisse


def _feld_treffer(ex: dict, soll: dict, feld: str) -> bool:
    """Vergleich für die vier Felder aus der Extraktion; zustaendigkeit und
    dringlichkeit prüft `bewerte` direkt gegen das Regelergebnis."""
    if feld == "kategorien":
        return {a.get("kategorie") for a in (ex.get("anliegen") or [])} == set(soll["kategorien"])
    if feld == "bestellnummer":
        return (ex.get("bezug") or {}).get("bestellnummer") == soll["bestellnummer"]
    if feld == "kundennummer":
        return (ex.get("kunde") or {}).get("kundennummer") == soll["kundennummer"]
    return ex.get("frist") == soll["frist"]


def bewerte(ergebnisse: dict[str, dict], erwartet: dict) -> dict:
    """Trefferzahlen je Feld für ein Modell, gegen die Soll-Werte aus `erwartet`.

    Eine Mail mit `extraktion_fehler` zählt als Fehlschlag in jedem Feld und
    erhöht `schemafehler`. `n` ist die Zahl der Soll-Mails, nicht der Läufe.
    """
    treffer = dict.fromkeys(FELDER, 0)
    schemafehler = 0
    dauern: list[int] = []
    for mail_id, soll in erwartet.items():
        erg = ergebnisse.get(mail_id)
        if erg is None:
            continue
        dauern.append(erg.get("dauer_ms", 0))
        if erg.get("extraktion_fehler"):
            schemafehler += 1
            continue
        ex = erg.get("extraktion") or {}
        if erg.get("zustaendigkeit") == soll["zustaendigkeit"]:
            treffer["zustaendigkeit"] += 1
        if erg.get("dringlichkeit") == soll["dringlichkeit"]:
            treffer["dringlichkeit"] += 1
        for feld in ("kategorien", "bestellnummer", "kundennummer", "frist"):
            if _feld_treffer(ex, soll, feld):
                treffer[feld] += 1
    return {
        **treffer,
        "schemafehler": schemafehler,
        "mittlere_dauer_ms": round(sum(dauern) / len(dauern), 1) if dauern else 0.0,
        "n": len(erwartet),
    }


def schreibe_tabelle(bewertungen: dict[str, dict], pfad) -> None:
    """Markdown-Tabelle mit einer Zeile je Modell und Soll-Werte-Fußnote."""
    n = next(iter(bewertungen.values()))["n"] if bewertungen else 15
    zeilen = ["| " + " | ".join(titel for titel, _ in SPALTEN) + " |",
              "| " + " | ".join("---" for _ in SPALTEN) + " |"]
    for modell, b in bewertungen.items():
        werte = [modell]
        for titel, feld in SPALTEN[1:]:
            if feld == "schemafehler":
                werte.append(str(b["schemafehler"]))
            elif feld == "mittlere_dauer_ms":
                werte.append(f"{b['mittlere_dauer_ms']:.0f} ms")
            else:
                werte.append(f"{b[feld]}/{b['n']}")
        zeilen.append("| " + " | ".join(werte) + " |")
    zeilen += ["", f"Soll-Werte: data/erwartet.json, n = {n}, Stand {date.today().isoformat()}"]
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelle", required=True, help="Kommagetrennte Modellnamen")
    p.add_argument("--anbieter", help="ollama oder openai; ohne Angabe der Anbieter aus der Umgebung")
    p.add_argument("--ausgabe", default=str(AUSGABE_STANDARD))
    args = p.parse_args(argv)

    basis = lade_konfig()
    heute = date.fromisoformat(speicher.lade_konfig()["basisdatum"])
    mails = speicher.lade_mails()
    erwartet = json.loads((speicher.DATEN / "erwartet.json").read_text(encoding="utf-8"))

    rohdaten: dict[str, dict] = {}
    bewertungen: dict[str, dict] = {}
    for modell in [m.strip() for m in args.modelle.split(",") if m.strip()]:
        konfig = konfig_fuer_modell(modell, args.anbieter, basis)
        _warne_bei_fehlendem_schluessel(konfig)
        print(f"Modell {modell} (Anbieter {konfig.provider})")
        client = LLMClient(konfig)
        ergebnisse = laufe_modell(client, mails, heute)
        rohdaten[modell] = ergebnisse
        bewertungen[modell] = bewerte(ergebnisse, erwartet)

    speicher.DATEN.mkdir(parents=True, exist_ok=True)
    (speicher.DATEN / "vergleich.json").write_text(
        json.dumps({"ergebnisse": rohdaten, "bewertungen": bewertungen}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    schreibe_tabelle(bewertungen, args.ausgabe)
    print()
    print(Path(args.ausgabe).read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
