"""Technikerkalender: fünf Servicetechniker mit Qualifikationen, je Werktag eine Belegtliste.

Regeln (Spec 4): vertrieb -> kein Termin. Nur Ersatzteil-Anliegen -> kein Termin.
stillstand -> erster Tag ab heute mit freiem Techniker der benötigten
Qualifikation, Hinweis "vorgezogen". Sonst erster freier Tag im Wunschzeitraum,
danach erster freier Tag nach dem Zeitraum mit Hinweis. Ohne Wunsch: ab morgen.
Der Vorschlag reserviert nichts; erst `belege()` trägt den Techniker ein.
"""
import json
import re
from datetime import date, timedelta
from pathlib import Path

TECHNIKER = [
    {"kuerzel": "T1", "name": "Techniker 1", "qualifikationen": ["elektrik", "steuerung"]},
    {"kuerzel": "T2", "name": "Techniker 2", "qualifikationen": ["vakuumtechnik", "mechanik"]},
    {"kuerzel": "T3", "name": "Techniker 3", "qualifikationen": ["steuerung"]},
    {"kuerzel": "T4", "name": "Techniker 4", "qualifikationen": ["mechanik", "elektrik"]},
    {"kuerzel": "T5", "name": "Techniker 5", "qualifikationen": ["vakuumtechnik"]},
]
_STEUERUNG = re.compile(r"fehlercode|steuerung|sps|bedienfeld|display|software|touch|f-\d|e\d\d", re.I)
# "Vakuum" ist hier das Produktwort des Herstellers und steht in fast jedem
# Anlagennamen (Vakuumofen, Vakuumhaerteofen, Vakuumloetofen, Vakuumanlage).
# Als Qualifikationswort gewertet, landete jede Heizungsstoerung an einem
# Vakuumofen bei der Vakuumtechnik statt bei der Elektrik. Es zaehlt deshalb
# nur, wenn kein Maschinenwort folgt.
_VAKUUM = re.compile(r"vakuum(?!(?:härte|haerte|löt|loet|glüh|glueh)?ofen|anlage)|pumpe|leck|mbar", re.I)
_ELEKTRIK = re.compile(r"heiz|elektr|sicherung|thermoelement|strom|trafo|schütz", re.I)


def erzeuge_kalender(basisdatum: date, wochen: int = 3) -> dict:
    tage = []
    tag = basisdatum
    while tag < basisdatum + timedelta(weeks=wochen):
        if tag.weekday() < 5:
            tage.append({"datum": tag.isoformat(), "belegt": []})
        tag += timedelta(days=1)
    return {"basisdatum": basisdatum.isoformat(), "techniker": [dict(t, qualifikationen=list(t["qualifikationen"])) for t in TECHNIKER], "tage": tage}


def lade_kalender(pfad) -> dict:
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def speichere_kalender(kalender: dict, pfad) -> None:
    Path(pfad).write_text(json.dumps(kalender, ensure_ascii=False, indent=2), encoding="utf-8")


def qualifikation_fuer(extraktion: dict) -> str:
    """Benötigte Qualifikation aus Kategorie und Beschreibung der Anliegen."""
    text = " ".join(f"{a.get('kategorie', '')} {a.get('beschreibung', '')}" for a in extraktion.get("anliegen") or [])
    if _STEUERUNG.search(text):
        return "steuerung"
    if _VAKUUM.search(text):
        return "vakuumtechnik"
    if _ELEKTRIK.search(text):
        return "elektrik"
    return "mechanik"


def _braucht_einsatz(extraktion: dict) -> bool:
    anliegen = extraktion.get("anliegen") or []
    return any(a.get("kategorie") != "ersatzteil" for a in anliegen) if anliegen else True


def _freier_techniker(kalender: dict, tag: dict, qualifikation: str) -> str | None:
    for t in kalender["techniker"]:
        if qualifikation in t["qualifikationen"] and t["kuerzel"] not in tag["belegt"]:
            return t["kuerzel"]
    return None


def _erster_freier(kalender: dict, von: date, bis: date | None, qualifikation: str) -> tuple[str, str] | None:
    for tag in kalender["tage"]:
        d = date.fromisoformat(tag["datum"])
        if d < von or (bis and d > bis):
            continue
        frei = _freier_techniker(kalender, tag, qualifikation)
        if frei:
            return tag["datum"], frei
    return None


def _datum(wert) -> date | None:
    try:
        return date.fromisoformat(wert) if wert else None
    except ValueError:
        return None


def _termin(treffer, qualifikation: str, hinweis: str) -> dict:
    return {"datum": treffer[0], "techniker": treffer[1], "qualifikation": qualifikation, "hinweis": hinweis}


def finde_termin(kalender: dict, extraktion: dict, heute: date) -> dict | None:
    if extraktion.get("zustaendigkeit") == "vertrieb" or not _braucht_einsatz(extraktion):
        return None
    qualifikation = qualifikation_fuer(extraktion)
    wunsch = extraktion.get("wunschzeitraum") or {}

    if extraktion.get("dringlichkeit") == "stillstand":
        treffer = _erster_freier(kalender, heute, None, qualifikation)
        return _termin(treffer, qualifikation, "Produktionsstillstand, Einsatz vorgezogen.") if treffer else None

    von, bis = _datum(wunsch.get("von")), _datum(wunsch.get("bis"))
    if von is None:
        von = heute + timedelta(days=1)
        while von.weekday() >= 5:
            von += timedelta(days=1)
    if von < heute:
        von = heute
    if bis is not None and bis < von:
        bis = None
    treffer = _erster_freier(kalender, von, bis, qualifikation)
    if treffer:
        return _termin(treffer, qualifikation, "")
    treffer = _erster_freier(kalender, (bis or von) + timedelta(days=1), None, qualifikation)
    if treffer:
        return _termin(treffer, qualifikation, "Im Wunschzeitraum ist kein passender Techniker frei, Vorschlag liegt außerhalb.")
    return None


def belege(kalender: dict, datum: str, techniker: str) -> bool:
    for tag in kalender["tage"]:
        if tag["datum"] == datum:
            if techniker in tag["belegt"]:
                return False
            tag["belegt"].append(techniker)
            return True
    return False


def gebe_frei(kalender: dict, datum: str, techniker: str) -> bool:
    """Gegenstück zu belege()."""
    for tag in kalender["tage"]:
        if tag["datum"] == datum and techniker in tag["belegt"]:
            tag["belegt"].remove(techniker)
            return True
    return False
