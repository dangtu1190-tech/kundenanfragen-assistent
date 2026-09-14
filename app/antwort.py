"""Antwortentwurf aus einer deutschen Vorlage. Kein Modell: der Text bleibt vorhersagbar.

`systemdaten` wird in dieser Fassung noch nicht ausgewertet (Bestellstatus,
Sendungsnummer, Veredelungsauftrag kommen mit der Anreicherung dazu); der
Parameter steht schon hier, damit die Aufrufstelle stabil bleibt.
"""
KATEGORIE_TEXT = {
    "bestellstatus": "Bestellstatus",
    "ruecksendung": "Rücksendung",
    "reklamation": "Reklamation",
    "veredelung": "Veredelung",
    "angebot": "Angebot",
    "rechnung": "Rechnung",
    "verfuegbarkeit": "Verfügbarkeit",
    "sonstiges": "Sonstiges",
}
ZUSTAENDIGKEIT_TEXT = {
    "vertrieb": "Ihr Anliegen betrifft unseren Vertrieb, die Kolleginnen und Kollegen melden sich mit einem Angebot.",
    "buchhaltung": "Ihre Rechnungsfrage haben wir an die Buchhaltung weitergegeben.",
    "veredelung": "Unsere Veredelung prüft Ihren Auftrag.",
}


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


def _anliegen_zeilen(ex: dict) -> list[str]:
    return [f"- {KATEGORIE_TEXT.get(a['kategorie'], a['kategorie'])}: {a['beschreibung']}"
            for a in ex.get("anliegen") or []]


def baue_antwort(ex: dict, systemdaten: dict, zustaendigkeit: str, betreff: str, versender: str) -> str:
    dank = f"vielen Dank für Ihre Nachricht „{betreff}“." if betreff else "vielen Dank für Ihre Nachricht."
    zeilen = [_anrede(ex.get("ansprechpartner")), "", dank]

    anliegen = _anliegen_zeilen(ex)
    if anliegen:
        zeilen += ["", "Wir haben notiert:"] + anliegen

    satz = ZUSTAENDIGKEIT_TEXT.get(zustaendigkeit)
    zeilen += ["", satz or "Wir kümmern uns darum und melden uns mit einer verbindlichen Aussage."]

    unklar = ex.get("unklarheiten") or []
    if unklar:
        zeilen += ["", "Damit wir Ihr Anliegen abschließen können, benötigen wir noch:"]
        zeilen += [f"- {u}" for u in unklar]

    zeilen += ["", "Mit freundlichen Grüßen", "Ihr Kundenservice", versender]
    return "\n".join(zeilen)
