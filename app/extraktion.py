"""Extraktion der Anfrage nach JSON: Schema (Pydantic), Prompt, Antwort parsen.

Das Modell sieht nur den pseudonymisierten Text; Platzhalter wie [NAME_1],
[FIRMA_1] müssen wörtlich übernommen werden. Ungültige Antworten werfen
ExtraktionsFehler, nie einen rohen Absturz.
"""
import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, ValidationError

Kategorie = Literal["ersatzteil", "wartung", "stoerung", "angebot", "reklamation", "sonstiges"]

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


class Kunde(BaseModel):
    firma: str | None = None


class Ansprechpartner(BaseModel):
    anrede: str | None = None
    name: str | None = None


class Anlage(BaseModel):
    typ: str | None = None
    nummer: str | None = None
    baujahr: int | None = None


class Anliegen(BaseModel):
    kategorie: Kategorie
    beschreibung: str


class Wunschzeitraum(BaseModel):
    von: str | None = None
    bis: str | None = None
    tageszeit: Literal["vormittag", "nachmittag", "egal"] = "egal"


class Extraktion(BaseModel):
    kunde: Kunde = Kunde()
    ansprechpartner: Ansprechpartner = Ansprechpartner()
    anlage: Anlage = Anlage()
    anliegen: list[Anliegen] = []
    dringlichkeit: Literal["niedrig", "mittel", "hoch", "stillstand"] = "mittel"
    wunschzeitraum: Wunschzeitraum = Wunschzeitraum()
    zustaendigkeit: Literal["service", "vertrieb"] = "service"
    unklarheiten: list[str] = []


class ExtraktionsFehler(Exception):
    pass


SCHEMA_TEXT = """{
  "kunde": {"firma": "Platzhalter wie [FIRMA_1] oder null"},
  "ansprechpartner": {"anrede": "Herr|Frau|null", "name": "Platzhalter wie [NAME_1] oder null"},
  "anlage": {"typ": "string|null", "nummer": "Anlagen- oder Seriennummer wörtlich|null", "baujahr": "int|null"},
  "anliegen": [{"kategorie": "ersatzteil|wartung|stoerung|angebot|reklamation|sonstiges", "beschreibung": "kurz, deutsch, Fehlercodes und Teilebezeichnungen wörtlich"}],
  "dringlichkeit": "niedrig|mittel|hoch|stillstand",
  "wunschzeitraum": {"von": "YYYY-MM-DD|null", "bis": "YYYY-MM-DD|null", "tageszeit": "vormittag|nachmittag|egal"},
  "zustaendigkeit": "service|vertrieb",
  "unklarheiten": ["string"]
}"""


def baue_prompt(heute: date) -> str:
    return (
        "Du bist die Serviceannahme eines Herstellers von Vakuumanlagen für Metallurgie und "
        "Wärmebehandlung. Du bekommst eine Kunden-E-Mail, in der personenbezogene Daten und "
        "Firmennamen durch Platzhalter ersetzt sind, z. B. [NAME_1], [FIRMA_1], [TELEFON_1]. "
        "Übernimm Platzhalter wörtlich, erfinde keine Werte dahinter. Anlagennummern, "
        "Seriennummern, Fehlercodes und Teilebezeichnungen sind keine Platzhalter, übernimm sie "
        "wörtlich, auch wenn sie ungewöhnlich aussehen.\n"
        f"Heute ist {heute.isoformat()} ({WOCHENTAGE[heute.weekday()]}). Relative Angaben wie "
        "'nächste Woche' oder 'KW 40' rechnest du auf Kalenderdaten um.\n"
        "Antworte ausschließlich mit einem JSON-Objekt nach diesem Schema:\n" + SCHEMA_TEXT + "\n"
        "Regeln: Jedes eigenständige Anliegen ist ein Listeneintrag. Steht die Produktion jetzt "
        "still, sitzt eine Charge im Ofen fest oder läuft die Anlage gar nicht mehr, ist "
        "dringlichkeit 'stillstand'. Eine geplante Wartung ist kein Stillstand, auch wenn die "
        "Linie dafür einmal steht oder der Kunde sie so terminiert, dass sie nur einmal steht. "
        "Steht eine Nummer wie VK-5000-0231 oder R 03/118 im Text, gehört sie in anlage.nummer, "
        "nie nur in anlage.typ; anlage.typ ist der Maschinentyp oder das Modell "
        "(zum Beispiel Vakuumhärteofen oder VIM 30). "
        "In ansprechpartner.name steht nur der Personenname, also nur ein Platzhalter der Form "
        "[NAME_x], nie ein [FIRMA_x]. "
        "Geht es um eine neue Anlage, einen Kauf oder ein Angebot für eine Neuanlage, "
        "ist zustaendigkeit 'vertrieb'; Angebote für Wartung, Retrofit oder Ersatzteile bleiben "
        "'service'. Bei weitergeleiteten Mails gilt die eigentliche Kundenanfrage in den Zitaten. "
        "Fehlt eine Information, die du für den Einsatz brauchst (Anlagennummer, konkretes "
        "Anliegen, Zeitraum, angekündigter aber fehlender Anhang), schreibe sie in unklarheiten. "
        "Keine Erklärungen außerhalb des JSON."
    )


def parse_antwort(content: str) -> Extraktion:
    text = content.strip()
    if "```" in text:
        text = text.split("```json")[-1] if "```json" in text else text.split("```")[1]
        text = text.split("```")[0]
    try:
        daten = json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtraktionsFehler(f"Antwort ist kein JSON: {e}") from e
    try:
        return Extraktion.model_validate(daten)
    except ValidationError as e:
        raise ExtraktionsFehler(f"Antwort passt nicht zum Schema: {e.errors()[0]['msg']} bei {e.errors()[0]['loc']}") from e


def extrahiere(client, pseudonym_text: str, heute: date) -> Extraktion:
    return parse_antwort(client.frage_json(baue_prompt(heute), pseudonym_text))
