"""Antwortentwurf aus einer deutschen Vorlage. Kein Modell: der Text bleibt vorhersagbar."""
from datetime import date

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KATEGORIE_TEXT = {
    "ersatzteil": "Ersatzteil", "wartung": "Wartung", "stoerung": "Störung", "angebot": "Angebot",
    "reklamation": "Reklamation", "sonstiges": "Sonstiges",
}
QUALIFIKATION_TEXT = {"elektrik": "Elektrik", "vakuumtechnik": "Vakuumtechnik", "steuerung": "Steuerung", "mechanik": "Mechanik"}


def _anrede(person: dict) -> str:
    name = (person or {}).get("name")
    anrede = (person or {}).get("anrede")
    if not name:
        return "Guten Tag,"
    nachname = name.split()[-1]
    if anrede == "Frau":
        return f"Sehr geehrte Frau {nachname},"
    if anrede == "Herr":
        return f"Sehr geehrter Herr {nachname},"
    return f"Guten Tag {name},"


def _datum_text(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{WOCHENTAGE[d.weekday()]}, {d.strftime('%d.%m.%Y')}"


def _anlage_text(ex: dict) -> str:
    a = ex.get("anlage") or {}
    text = a.get("typ") or ""
    if a.get("nummer"):
        text = f"{text} ({a['nummer']})" if text else a["nummer"]
    return f"Ihre Anlage {text}" if text else "Ihre Anlage"


def _anliegen_zeilen(ex: dict) -> list[str]:
    return [f"- {KATEGORIE_TEXT.get(a['kategorie'], a['kategorie'])}: {a['beschreibung']}" for a in ex.get("anliegen") or []]


def _ersatzteil_zeilen(ersatzteile: list[dict] | None) -> list[str]:
    return [f"Ersatzteil {e['teil']}: {e['status']}" for e in ersatzteile or []]


def baue_antwort(ex: dict, termin: dict | None, betreff: str, ersatzteile: list[dict] | None = None) -> str:
    dank = f"vielen Dank für Ihre Anfrage „{betreff}“." if betreff else "vielen Dank für Ihre Anfrage."
    zeilen = [_anrede(ex.get("ansprechpartner")), "", dank]
    anliegen = _anliegen_zeilen(ex)
    nur_ersatzteil = bool(ex.get("anliegen")) and all(a.get("kategorie") == "ersatzteil" for a in ex["anliegen"])
    if ex.get("zustaendigkeit") == "vertrieb":
        zeilen += ["", "Ihr Anliegen betrifft unseren Vertrieb. Ich habe Ihre Nachricht an die Kolleginnen und "
                   "Kollegen dort weitergeleitet, sie melden sich in Kürze bei Ihnen."]
        if anliegen:
            zeilen += ["", "Wir haben notiert:"] + anliegen
    else:
        if anliegen:
            zeilen += ["", f"Für {_anlage_text(ex)} haben wir notiert:"] + anliegen
        teile = _ersatzteil_zeilen(ersatzteile)
        if teile:
            zeilen += [""] + teile + ["Ein Angebot mit Preisen und Lieferzeit folgt gesondert."]
        if termin:
            quali = QUALIFIKATION_TEXT.get(termin.get("qualifikation"), termin.get("qualifikation", ""))
            zeilen += ["", f"Wir schlagen Ihnen den Einsatz eines Servicetechnikers ({quali}) am "
                       f"{_datum_text(termin['datum'])} vor."]
            if termin.get("hinweis"):
                zeilen.append(termin["hinweis"])
            zeilen.append("Bitte bestätigen Sie den Termin kurz per Antwort auf diese E-Mail.")
        elif not nur_ersatzteil:
            zeilen += ["", "Wir melden uns mit einem Terminvorschlag, sobald die offenen Punkte geklärt sind."]
    unklar = ex.get("unklarheiten") or []
    if unklar:
        zeilen += ["", "Damit wir den Einsatz passend planen können, benötigen wir noch:"]
        zeilen += [f"- {u}" for u in unklar]
    zeilen += ["", "Mit freundlichen Grüßen", "Ihr Serviceteam"]
    return "\n".join(zeilen)
