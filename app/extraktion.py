"""Extraktion der Kundenanfrage nach JSON: Schema (Pydantic), Prompt, Antwort parsen.

Das Modell sieht nur den pseudonymisierten Text; Platzhalter wie [NAME_1],
[FIRMA_1] müssen wörtlich übernommen werden. Kennungen (Kunden-, Bestell-,
Rechnungs-, Veredelungs-, Artikel- und Sendungsnummern) sind keine Platzhalter
und bleiben buchstabengetreu stehen.

Das Schema ist absichtlich tolerant: ein ungültiger Enum-Wert fällt auf den
Standard zurück, statt die ganze Antwort zu verwerfen. Jede solche Korrektur
wird als Hinweis protokolliert, damit sie sichtbar bleibt.
"""
import json
from datetime import date
from typing import Literal, get_args

from pydantic import BaseModel, ValidationError, field_validator

Kategorie = Literal["bestellstatus", "ruecksendung", "reklamation", "veredelung",
                    "angebot", "rechnung", "verfuegbarkeit", "sonstiges"]
KATEGORIEN = list(get_args(Kategorie))
DRINGLICHKEITEN = ("niedrig", "mittel", "hoch")
ANREDEN = ("Herr", "Frau")

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

KATEGORIE_BEDEUTUNG = [
    ("bestellstatus", "Lieferstand einer bestehenden Bestellung"),
    ("ruecksendung", "Rückgabe oder Größentausch"),
    ("reklamation", "Mangel an gelieferter Ware oder Falschlieferung"),
    ("veredelung", "Logo, Stick, Druck, Stickdatei, Freigabe"),
    ("angebot", "Preisanfrage oder Ausstattung neuer Mitarbeiter"),
    ("rechnung", "Rechnungskopie, Kostenstelle, Zahlungsziel"),
    ("verfuegbarkeit", "lieferbar, Nachfolgeartikel, Bestand"),
    ("sonstiges", "alles andere, auch Werbung und Lieferantenangebote"),
]


class Kunde(BaseModel):
    firma: str | None = None
    kundennummer: str | None = None


class Ansprechpartner(BaseModel):
    anrede: str | None = None
    name: str | None = None

    @field_validator("anrede", mode="before")
    @classmethod
    def _nur_herr_frau(cls, v):
        return v if v in ANREDEN else None


class Bezug(BaseModel):
    bestellnummer: str | None = None
    rechnungsnummer: str | None = None
    veredelungsauftrag: str | None = None


class Artikel(BaseModel):
    artikelnummer: str | None = None
    bezeichnung: str | None = None
    groesse: str | None = None
    farbe: str | None = None
    menge: int | None = None


class Anliegen(BaseModel):
    kategorie: Kategorie
    beschreibung: str

    @field_validator("kategorie", mode="before")
    @classmethod
    def _kategorie(cls, v):
        return v if v in KATEGORIEN else "sonstiges"


class Extraktion(BaseModel):
    kunde: Kunde = Kunde()
    ansprechpartner: Ansprechpartner = Ansprechpartner()
    bezug: Bezug = Bezug()
    artikel: list[Artikel] = []
    anliegen: list[Anliegen] = []
    dringlichkeit: Literal["niedrig", "mittel", "hoch"] = "mittel"
    frist: str | None = None
    unklarheiten: list[str] = []

    @field_validator("dringlichkeit", mode="before")
    @classmethod
    def _dringlichkeit(cls, v):
        return v if v in DRINGLICHKEITEN else "mittel"

    @field_validator("frist", mode="before")
    @classmethod
    def _frist(cls, v):
        """Nimmt auch einen Zeitstempel an: Modelle hängen gern 'T00:00:00' an.

        Dann zählt der führende Datumsteil; nur wirklich unlesbare Angaben
        ('nächste Woche') werden null.
        """
        if not v:
            return None
        for kandidat in ([v, v[:10]] if isinstance(v, str) else [v]):
            try:
                return date.fromisoformat(kandidat).isoformat()
            except (TypeError, ValueError):
                continue
        return None


class ExtraktionsFehler(Exception):
    pass


SCHEMA_TEXT = """{
  "kunde": {"firma": "Platzhalter der Form [FIRMA_n] oder null", "kundennummer": "Kundennummer wörtlich oder null"},
  "ansprechpartner": {"anrede": "Herr, Frau oder null", "name": "Platzhalter der Form [NAME_n] oder null"},
  "bezug": {"bestellnummer": "wörtlich oder null", "rechnungsnummer": "wörtlich oder null", "veredelungsauftrag": "wörtlich oder null"},
  "artikel": [{"artikelnummer": "wörtlich oder null", "bezeichnung": "Text oder null", "groesse": "Text oder null", "farbe": "Text oder null", "menge": "Zahl oder null"}],
  "anliegen": [{"kategorie": "eine der Kategorien aus der Liste unten", "beschreibung": "kurz, deutsch"}],
  "dringlichkeit": "niedrig, mittel oder hoch",
  "frist": "Datum YYYY-MM-DD oder null",
  "unklarheiten": ["Text"]
}"""


def _kategorienliste() -> str:
    return "\n".join(f"- {name}: {bedeutung}" for name, bedeutung in KATEGORIE_BEDEUTUNG)


def baue_prompt(heute: date) -> str:
    return (
        "Du bist der Kundenservice eines Versenders für Berufsbekleidung und Arbeitsschutz. "
        "Du bekommst eine Kunden-E-Mail, in der personenbezogene Daten und Firmennamen durch "
        "Platzhalter ersetzt sind, zum Beispiel [NAME_1], [FIRMA_1], [TELEFON_1], [ORT_1]. "
        "Übernimm Platzhalter wörtlich und erfinde nichts dahinter.\n"
        "Kundennummern, Bestellnummern, Rechnungsnummern, Veredelungsaufträge, Artikelnummern "
        "und Sendungsnummern sind keine Platzhalter. Übernimm sie buchstabengetreu, Zeichen für "
        "Zeichen, auch wenn sie ungewöhnlich oder unvollständig aussehen. Korrigiere sie nie "
        "und ergänze keine Stellen.\n"
        f"Heute ist {heute.isoformat()} ({WOCHENTAGE[heute.weekday()]}). Relative Angaben wie "
        "'nächste Woche' oder 'übermorgen' rechnest du auf Kalenderdaten um.\n"
        "Antworte ausschließlich mit einem JSON-Objekt nach diesem Schema:\n" + SCHEMA_TEXT + "\n"
        "Diese Kategorien gibt es:\n" + _kategorienliste() + "\n"
        "Regeln: Jedes eigenständige Anliegen ist ein eigener Listeneintrag; eine Mail kann "
        "mehrere Anliegen und mehrere Artikel enthalten. "
        "In ansprechpartner.name steht nur der Personenname, also ein Platzhalter der Form "
        "[NAME_n], nie eine Firma. "
        "Setze frist nur, wenn der Kunde selbst einen Termin nennt, bis zu dem er die Ware oder "
        "eine Antwort braucht; nimm dann genau den Tag, den er nennt, und rechne nicht von dir "
        "aus auf einen früheren Tag zurück. Nennt er keinen Termin, bleibt frist null. "
        "Bei weitergeleiteten Mails gilt der ganze Verlauf: die eigentliche Anfrage kann "
        "über den Zitaten stehen oder in ihnen, und Kennungen zählen an jeder Stelle des "
        "Verlaufs. "
        "Du bekommst die Mail immer ohne Anhänge, auch wenn welche mitgeschickt wurden. "
        "Jeden Anhang, den der Kunde ankündigt oder erwähnt (Foto, Stickdatei, Logo, "
        "Lieferschein, 'anbei', 'im Anhang'), trägst du deshalb als fehlend in "
        "unklarheiten ein; ebenso alles andere, was für die Bearbeitung fehlt. "
        "Keine Erklärungen außerhalb des JSON."
    )


_FEHLT = object()


def _hinweis(feld: str, roh, ersatz: str) -> str:
    wert = "null" if roh is None else f"'{roh}'"
    return f"{feld} {wert} ungültig, auf {ersatz} gesetzt"


def _sammle_hinweise(daten: dict, ex: Extraktion) -> list[str]:
    """Vergleicht Rohwerte mit den validierten Werten.

    Nur so bleibt sichtbar, dass ein Vorvalidator eingegriffen hat: das Ergebnis
    allein sähe aus wie eine saubere Modellantwort.
    """
    hinweise: list[str] = []
    ansprechpartner = daten.get("ansprechpartner")
    if isinstance(ansprechpartner, dict):
        roh = ansprechpartner.get("anrede", _FEHLT)
        if roh is not _FEHLT and roh is not None and ex.ansprechpartner.anrede is None:
            hinweise.append(_hinweis("anrede", roh, "null"))
    for i, roh_anliegen in enumerate(daten.get("anliegen") or []):
        if not isinstance(roh_anliegen, dict) or i >= len(ex.anliegen):
            continue
        roh = roh_anliegen.get("kategorie", _FEHLT)
        if roh is not _FEHLT and roh != ex.anliegen[i].kategorie:
            hinweise.append(_hinweis("kategorie", roh, "'sonstiges'"))
    roh = daten.get("dringlichkeit", _FEHLT)
    if roh is not _FEHLT and roh != ex.dringlichkeit:
        hinweise.append(_hinweis("dringlichkeit", roh, "'mittel'"))
    roh = daten.get("frist", _FEHLT)
    if roh is not _FEHLT and roh and ex.frist is None:
        hinweise.append(_hinweis("frist", roh, "null"))
    return hinweise


def parse_antwort(content: str) -> tuple[Extraktion, list[str]]:
    """Liefert (Extraktion, Hinweise). Hinweise nennen jeden korrigierten Wert."""
    text = content.strip()
    if "```" in text:
        text = text.split("```json")[-1] if "```json" in text else text.split("```")[1]
        text = text.split("```")[0]
    try:
        daten = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtraktionsFehler(f"Antwort ist kein JSON: {e}") from e
    try:
        ex = Extraktion.model_validate(daten)
    except ValidationError as e:
        raise ExtraktionsFehler(
            f"Antwort passt nicht zum Schema: {e.errors()[0]['msg']} bei {e.errors()[0]['loc']}") from e
    return ex, _sammle_hinweise(daten, ex) if isinstance(daten, dict) else []


def extrahiere(client, pseudonym_text: str, heute: date) -> tuple[Extraktion, list[str]]:
    return parse_antwort(client.frage_json(baue_prompt(heute), pseudonym_text))
