# Serviceanfragen-Domäne Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Demo vom Autohaus-Szenario auf Serviceanfragen eines Sonderanlagenbauers umstellen: neues Schema, neue Pseudonymisierungs-Felder (Firma statt Kennzeichen), Technikerkalender, Ersatzteilhinweise, 15 neue Testmails, Oberfläche und README; Kern (Pipeline, Client, Speicher, Testaufbau) unverändert.

**Architecture:** Gleiche Module wie bisher. `anonymisierung.py` tauscht das Kennzeichen-Muster gegen ein Firmen-Muster, `extraktion.py` trägt das neue Schema, `kalender.py` wird zum Technikerkalender, neu `ersatzteile.py`, `antwort.py` folgt dem Schema, `pipeline.py` bekommt eine Zeile für Ersatzteilhinweise, `main.py` nutzt `termin["techniker"]` statt `halbtag`. Oberfläche nur in den Feldnamen angepasst.

**Tech Stack:** unverändert (Python 3.12, FastAPI, pydantic v2, openai-SDK, pytest, Vanilla JS).

**Spec:** `planung/specs/2026-09-10-serviceanfragen-domaene-design.md`

## Global Constraints

- Sprache Deutsch (Code, Kommentare, UI, Commits). Commits enden mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Kein API-Schlüssel im Repo. `data/*.json` werden nur in den dafür vorgesehenen Tasks geändert; `data/ergebnisse.json` und `docs/data/*` erst im Echtlauf (Task 7).
- Das Modell bekommt ausschließlich `pseudonym_text`. Anlagen-/Seriennummern und Fehlercodes werden NICHT ersetzt.
- Basisdatum 2026-09-14 (Montag). Rechenkerne nehmen `heute` als Parameter.
- Dateien unter 300 Zeilen. Arbeitsverzeichnis `<Projektordner>`, Branch `serviceanfragen`. Python `python`. Vor jedem Commit `python -m pytest -q` grün (Echtlauf-Test skippt ohne Schlüssel) und `git status --short` ohne `__pycache__`.
- Vorhandene Testmodule, die das alte Schema testen, werden im jeweiligen Task angepasst, nie „vorübergehend" gelöscht.

---

## Dateistruktur

| Datei | Änderung |
|---|---|
| `app/anonymisierung.py` | KENNZEICHEN raus, FIRMA rein, `absender_firma`-Parameter |
| `app/extraktion.py` | neues Schema, neuer Prompt |
| `app/kalender.py` | Technikerkalender |
| `app/ersatzteile.py` (neu) | Verfügbarkeitshinweise |
| `app/antwort.py` | neue Vorlage |
| `app/pipeline.py` | `absender_firma` durchreichen, `ersatzteile` ins Ergebnis |
| `app/main.py` | Titel, `NeueMail.absender_firma`, Termin-Schlüssel `techniker` |
| `data/mails.json`, `data/kalender.json`, `data/ersatzteile.json` | neue Daten |
| `docs/index.html`, `README.md`, `docs/GESPRAECH.md` | Domäne |
| `tests/*` | angepasst |

---

### Task 1: Pseudonymisierung: Firma statt Kennzeichen

**Files:**
- Modify: `app/anonymisierung.py`
- Modify: `tests/test_anonymisierung.py`, `tests/test_anonymisierung_grenzen.py`

**Interfaces:**
- Produces: `anonymisiere(text: str, absender_name: str | None = None, absender_firma: str | None = None) -> tuple[str, list[dict]]`; Platzhaltertypen `EMAIL, FIRMA, TELEFON, ADRESSE, ORT, NAME`; `PLATZHALTER_MUSTER` erkennt genau diese sechs. `zuruecksetzen` unverändert.

- [ ] **Step 1: Tests umschreiben**

In `tests/test_anonymisierung.py` die beiden Kennzeichen-Tests (`test_kennzeichen_varianten`, `test_fahrzeugmodelle_bleiben`) ersetzen durch:

```python
def test_firma_ueber_rechtsform():
    text, tab = anonymisiere("Wir sind die Hartmann Wärmebehandlung GmbH. Die Roth & Söhne Metallguss GmbH & Co. KG "
                             "und die Nordlicht Turbinentechnik AG kennen Sie.")
    firmen = [t["original"] for t in tab if t["typ"] == "FIRMA"]
    assert firmen == ["Hartmann Wärmebehandlung GmbH", "Roth & Söhne Metallguss GmbH & Co. KG",
                      "Nordlicht Turbinentechnik AG"]
    assert "Hartmann" not in text and "Söhne" not in text and "Nordlicht" not in text
    assert text.startswith("Wir sind die [FIRMA_1]. Die [FIRMA_2] und die [FIRMA_3] kennen Sie.")


def test_absenderfirma_auch_kurzform():
    text, tab = anonymisiere("hier ist die präzisionsteile menzel ag, wir von Präzisionsteile brauchen Hilfe.",
                             absender_firma="Präzisionsteile Menzel AG")
    assert tab[0] == {"typ": "FIRMA", "platzhalter": "[FIRMA_1]", "original": "Präzisionsteile Menzel AG"}
    assert "menzel" not in text.lower() and "Präzisionsteile" not in text
    assert text.count("[FIRMA_1]") == 2


def test_anlagen_und_seriennummern_bleiben():
    text, tab = anonymisiere("Anlage VIM 30, SN VIM-3000-0917, Fehlercode F-217, alte Nummer R 03/118, Halle 3, "
                             "Vakuum 5x10-3 mbar, Baujahr 2003.")
    assert tab == []
    assert "VIM-3000-0917" in text and "F-217" in text and "R 03/118" in text and "Halle 3" in text


def test_rechtsform_allein_ist_keine_firma():
    text, tab = anonymisiere("Die GmbH als Rechtsform. Eine AG auch.")
    assert [t for t in tab if t["typ"] == "FIRMA"] == []
```

`test_platzhalter_werden_nicht_erneut_ersetzt` verwendet „Kennzeichen AB-CD 1234": Text in `"Herr Weber, Tel 0176 12345678, Firma Weber Stahl GmbH"` ändern, Erwartung bleibt (zweiter Lauf ändert nichts). `test_platzhalter_muster`: `assert PLATZHALTER_MUSTER.fullmatch("[FIRMA_12]")` und `assert not PLATZHALTER_MUSTER.fullmatch("[KENNZEICHEN_1]")`.

In `tests/test_anonymisierung_grenzen.py` die Kennzeichen-Tests (`test_einstellige_kennzeichen…`, `test_fahrzeugmodelle…` bzw. wie dort benannt) entfernen und ersetzen durch:

```python
def test_firma_frisst_keine_folgeworte():
    text, tab = anonymisiere("Die Kolb Zahnradfabrik GmbH meldet: Halle 3 steht. Bitte Rückruf.")
    assert text == "Die [FIRMA_1] meldet: Halle 3 steht. Bitte Rückruf."


def test_firma_in_signatur_und_email_domain():
    text, tab = anonymisiere("Gruß\nAndrea Wittmann\nElektro Wittmann GmbH\na.wittmann@elektro-wittmann.example\n06051 881720",
                             absender_name="Andrea Wittmann", absender_firma="Elektro Wittmann GmbH")
    assert "Wittmann" not in text and "elektro-wittmann" not in text
    typen = [t["typ"] for t in tab]
    assert "FIRMA" in typen and "NAME" in typen and "EMAIL" in typen and "TELEFON" in typen
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest tests/test_anonymisierung.py tests/test_anonymisierung_grenzen.py -q` → die neuen Tests scheitern (FIRMA unbekannt, `absender_firma` unbekanntes Argument).

- [ ] **Step 3: Implementierung**

In `app/anonymisierung.py`:

1. Docstring: „Reihenfolge der Muster: E-Mail, Firma, Telefon, Adresse, PLZ+Ort, Namen. Anlagen-/Seriennummern und Fehlercodes werden bewusst nicht ersetzt (keine personenbezogenen Daten, das Modell braucht sie)."
2. `PLATZHALTER_MUSTER = re.compile(r"\[(EMAIL|FIRMA|TELEFON|ADRESSE|ORT|NAME)_(\d+)\]")`
3. `_KENNZEICHEN` und seine Verwendung in `anonymisiere` entfernen. Neu:

```python
_RECHTSFORM = r"(?:GmbH\s*&\s*Co\.\s*KGaA|GmbH\s*&\s*Co\.\s*KG|GmbH|AG|KGaA|KG|SE|OHG|e\.K\.|Ltd\.?|Inc\.?|S\.p\.A\.|S\.A\.|B\.V\.)"
# bis zu vier grossgeschriebene Woerter oder "&" vor der Rechtsform; mindestens ein Wort
_FIRMA = re.compile(
    r"\b(?:(?:[A-ZÄÖÜ][\wäöüß.\-]*|&)\s+){0,4}[A-ZÄÖÜ][\wäöüß.\-]*\s+" + _RECHTSFORM + r"(?![\wäöüß])"
)
_RECHTSFORM_WOERTER = {"gmbh", "ag", "kg", "kgaa", "se", "ohg", "co", "co.", "&", "e.k.", "ltd", "ltd.", "inc", "inc.",
                       "s.p.a.", "s.a.", "b.v.", "und"}
```

4. Neue Funktion und Erweiterung von `anonymisiere`:

```python
def _ersetze_firma(text: str, absender_firma: str | None, tabelle: list, zuordnung: dict) -> str:
    """Firmen: erst die Absenderfirma (voll, Gross/Klein egal, plus Kurzform = erstes Wort),
    dann alle Namen mit Rechtsform-Endung im Text."""
    if absender_firma and absender_firma.strip():
        firma = absender_firma.strip()
        platz = _platzhalter("FIRMA", firma, tabelle, zuordnung)
        text = _ersetze(text, re.compile(r"(?<!\w)" + re.escape(firma) + r"(?!\w)", re.IGNORECASE),
                        "FIRMA", tabelle, zuordnung, fest=platz)
        kurz = firma.split()[0]
        if len(kurz) >= 4 and kurz.lower() not in _RECHTSFORM_WOERTER:
            text = _ersetze(text, re.compile(r"(?<!\w)" + re.escape(kurz) + r"(?!\w)", re.IGNORECASE),
                            "FIRMA", tabelle, zuordnung, fest=platz)
    return _ersetze(text, _FIRMA, "FIRMA", tabelle, zuordnung)


def anonymisiere(text: str, absender_name: str | None = None, absender_firma: str | None = None) -> tuple[str, list[dict]]:
    """Liefert (pseudonymisierter Text, Platzhaltertabelle)."""
    tabelle: list[dict] = []
    zuordnung: dict = {}
    text = _ersetze(text, _EMAIL, "EMAIL", tabelle, zuordnung)
    text = _ersetze_firma(text, absender_firma, tabelle, zuordnung)
    text = _ersetze(text, _TELEFON, "TELEFON", tabelle, zuordnung)
    text = _ersetze(text, _ADRESSE, "ADRESSE", tabelle, zuordnung)
    text = _ersetze(text, _ORT, "ORT", tabelle, zuordnung)
    text = _ersetze_namen(text, _namenskandidaten(text, absender_name), tabelle, zuordnung)
    return text, tabelle
```

Hinweis: `_platzhalter` strippt das Original; der Firmen-Treffer aus dem Regex enthält ggf. ein Leerzeichen vor der Rechtsform, das bleibt Teil des Originals (gewollt: „Nordlicht Turbinentechnik AG"). Falls `test_firma_ueber_rechtsform` an „Roth & Söhne …" scheitert, prüfen, ob `&` als eigenes Token vor `Söhne` erlaubt ist (ist es durch die Alternative `|&`). `_KEIN_NAME` um `"firma"` ergänzen, damit eine Signaturzeile „Firma" nicht als Name gilt. Die Namenszeilen-Erkennung darf eine Zeile mit Rechtsform nicht als Namen nehmen: in `_namenskandidaten` beim Signatur-Kandidaten zusätzlich `and not _RECHTSFORM_ZEILE.search(folge)` mit `_RECHTSFORM_ZEILE = re.compile(r"\b" + _RECHTSFORM + r"(?![\wäöüß])")`.

- [ ] **Step 4: Tests**

Run: `python -m pytest tests/test_anonymisierung.py tests/test_anonymisierung_grenzen.py -q` → alle grün. Dann `python -m pytest -q`: `test_pipeline.py`/`test_main.py`/`test_echtlauf.py` dürfen an alten Daten scheitern (werden in Task 5 angepasst) — im Report benennen, welche.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(anonymisierung): Firmennamen statt Kennzeichen, Anlagennummern bleiben sichtbar

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Extraktionsschema und Prompt

**Files:**
- Modify: `app/extraktion.py`
- Modify: `tests/test_extraktion.py`

**Interfaces:**
- Produces: `Extraktion` mit `kunde.firma`, `ansprechpartner.{anrede,name}`, `anlage.{typ,nummer,baujahr}`, `anliegen[].kategorie` aus `ersatzteil|wartung|stoerung|angebot|reklamation|sonstiges`, `dringlichkeit` aus `niedrig|mittel|hoch|stillstand`, `zustaendigkeit` aus `service|vertrieb`; `baue_prompt(heute)`, `parse_antwort`, `extrahiere` unverändert in Signatur.

- [ ] **Step 1: Tests**

`tests/test_extraktion.py`: `GUELTIG` ersetzen durch

```python
GUELTIG = {
    "kunde": {"firma": "[FIRMA_1]"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "anlage": {"typ": "VIM 30", "nummer": "VIM-3000-0917", "baujahr": 2017},
    "anliegen": [{"kategorie": "stoerung", "beschreibung": "Fehlercode F-217, Anlage steht"}],
    "dringlichkeit": "stillstand",
    "wunschzeitraum": {"von": "2026-09-14", "bis": None, "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": [],
}
```

`test_parse_gueltig`: `assert e.anliegen[0].kategorie == "stoerung"`. `test_parse_mit_codeblock`: `assert e.anlage.nummer == "VIM-3000-0917"`. `test_parse_falsche_kategorie`: Kategorie `"reifen"` → ExtraktionsFehler. `test_parse_toleriert_fehlende_optionale_felder`: knappes Objekt mit `"kunde": {"firma": None}, "ansprechpartner": {"anrede": None, "name": None}, "anlage": {"typ": None, "nummer": None}` und `assert e.anlage.baujahr is None`. `test_prompt_enthaelt_datum_und_platzhalterregel`: zusätzlich `assert "[FIRMA_1]" in p and "stillstand" in p and "Seriennummer" in p and "Autohaus" not in p`. Übrige Tests unverändert (Client/Konfig).

- [ ] **Step 2: Fehlschlag prüfen** — `python -m pytest tests/test_extraktion.py -q`.

- [ ] **Step 3: Implementierung**

`app/extraktion.py` Modelle und Prompt ersetzen:

```python
Kategorie = Literal["ersatzteil", "wartung", "stoerung", "angebot", "reklamation", "sonstiges"]


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
        "Regeln: Jedes eigenständige Anliegen ist ein Listeneintrag. Steht die Produktion, sitzt "
        "eine Charge im Ofen fest oder läuft die Anlage gar nicht mehr, ist dringlichkeit "
        "'stillstand'. Geht es um eine neue Anlage, einen Kauf oder ein Angebot für eine Neuanlage, "
        "ist zustaendigkeit 'vertrieb'; Angebote für Wartung, Retrofit oder Ersatzteile bleiben "
        "'service'. Bei weitergeleiteten Mails gilt die eigentliche Kundenanfrage in den Zitaten. "
        "Fehlt eine Information, die du für den Einsatz brauchst (Anlagennummer, konkretes "
        "Anliegen, Zeitraum, angekündigter aber fehlender Anhang), schreibe sie in unklarheiten. "
        "Keine Erklärungen außerhalb des JSON."
    )
```

Docstring des Moduls: Platzhalter-Beispiele `[NAME_1]`, `[FIRMA_1]`.

- [ ] **Step 4: Tests** — `python -m pytest tests/test_extraktion.py -q` grün.

- [ ] **Step 5: Commit** — `feat(extraktion): Schema fuer Serviceanfragen im Anlagenbau`.

---

### Task 3: Technikerkalender und Ersatzteile

**Files:**
- Modify: `app/kalender.py`; Create: `app/ersatzteile.py`, `data/ersatzteile.json`; Replace: `data/kalender.json`
- Modify: `tests/test_kalender.py`; Create: `tests/test_ersatzteile.py`

**Interfaces:**
- Produces: `erzeuge_kalender(basisdatum, wochen=3) -> dict` (mit `techniker`-Liste und `tage[].belegt: list[str]`), `lade_kalender`, `speichere_kalender`, `qualifikation_fuer(extraktion: dict) -> str`, `finde_termin(kalender, extraktion, heute) -> dict | None` mit `{datum, techniker, qualifikation, hinweis}`, `belege(kalender, datum, techniker) -> bool`, `gebe_frei(kalender, datum, techniker) -> bool`.
- `ersatzteile.lade_katalog(pfad=None) -> list[dict]`, `ersatzteile.hinweise(extraktion: dict, katalog: list[dict] | None = None) -> list[dict]` mit `[{teil, status}]` je Anliegen der Kategorie `ersatzteil`.

- [ ] **Step 1: Tests**

`tests/test_kalender.py` komplett ersetzen:

```python
from datetime import date
from app.kalender import belege, erzeuge_kalender, finde_termin, gebe_frei, qualifikation_fuer

HEUTE = date(2026, 9, 14)


def _kal():
    kal = erzeuge_kalender(HEUTE, wochen=3)
    # T1 (elektrik, steuerung) die ganze erste Woche unterwegs, T3 (steuerung) am 16./17.09.
    for tag in kal["tage"]:
        if tag["datum"] <= "2026-09-18":
            tag["belegt"].append("T1")
        if tag["datum"] in ("2026-09-16", "2026-09-17"):
            tag["belegt"].append("T3")
    return kal


def _ex(**kw):
    basis = {"zustaendigkeit": "service", "dringlichkeit": "mittel",
             "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"}],
             "wunschzeitraum": {"von": None, "bis": None, "tageszeit": "egal"}}
    basis.update(kw)
    return basis


def test_kalender_struktur():
    kal = erzeuge_kalender(HEUTE, wochen=1)
    assert [t["datum"] for t in kal["tage"]] == ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
    assert {t["kuerzel"] for t in kal["techniker"]} == {"T1", "T2", "T3", "T4", "T5"}
    assert all(t["belegt"] == [] for t in kal["tage"])


def test_qualifikation_aus_anliegen():
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode F-217 am Bedienfeld"}])) == "steuerung"
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Vakuum wird nicht erreicht, Pumpe laut"}])) == "vakuumtechnik"
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Heizung fällt aus, Sicherung fliegt"}])) == "elektrik"
    assert qualifikation_fuer(_ex()) == "mechanik"


def test_ohne_wunsch_ab_morgen_mit_passendem_techniker():
    t = finde_termin(_kal(), _ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode E12 Steuerung"}]), HEUTE)
    # T1 ist die ganze Woche belegt, T3 hat Steuerung und ist am 15.09. frei
    assert t == {"datum": "2026-09-15", "techniker": "T3", "qualifikation": "steuerung", "hinweis": ""}


def test_wunschzeitraum_ausgebucht_naechster_danach():
    ex = _ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode E12 Steuerung"}],
             wunschzeitraum={"von": "2026-09-16", "bis": "2026-09-17", "tageszeit": "egal"})
    t = finde_termin(_kal(), ex, HEUTE)
    assert t["datum"] == "2026-09-18" and t["techniker"] == "T3"
    assert "außerhalb" in t["hinweis"]


def test_stillstand_zieht_vor():
    ex = _ex(dringlichkeit="stillstand", anliegen=[{"kategorie": "stoerung", "beschreibung": "Heizung tot, Anlage steht"}],
             wunschzeitraum={"von": "2026-09-28", "bis": "2026-09-30", "tageszeit": "egal"})
    t = finde_termin(_kal(), ex, HEUTE)
    assert t["datum"] == "2026-09-14" and t["qualifikation"] == "elektrik" and t["techniker"] == "T4"
    assert "vorgezogen" in t["hinweis"]


def test_vertrieb_und_nur_ersatzteil_kein_termin():
    assert finde_termin(_kal(), _ex(zustaendigkeit="vertrieb"), HEUTE) is None
    assert finde_termin(_kal(), _ex(anliegen=[{"kategorie": "ersatzteil", "beschreibung": "Heizelement"}]), HEUTE) is None


def test_belegen_und_freigeben():
    kal = _kal()
    assert belege(kal, "2026-09-15", "T3") is True
    assert "T3" in [t for t in kal["tage"] if t["datum"] == "2026-09-15"][0]["belegt"]
    assert belege(kal, "2026-09-15", "T3") is False   # schon belegt
    assert belege(kal, "2099-01-01", "T3") is False
    assert gebe_frei(kal, "2026-09-15", "T3") is True
    assert gebe_frei(kal, "2026-09-15", "T3") is False
```

`tests/test_ersatzteile.py`:

```python
from app.ersatzteile import hinweise

KATALOG = [
    {"begriffe": ["heizelement", "heizstab"], "teil": "Heizelement Graphit", "status": "ab Lager"},
    {"begriffe": ["vorpumpe", "vakuumpumpe"], "teil": "Vorvakuumpumpe", "status": "Lieferzeit ca. 3 Wochen"},
]


def test_treffer_und_fallback():
    ex = {"anliegen": [
        {"kategorie": "ersatzteil", "beschreibung": "zwei Heizelemente für den Ofen"},
        {"kategorie": "ersatzteil", "beschreibung": "Dichtung für die Tür"},
        {"kategorie": "wartung", "beschreibung": "Jahreswartung"},
    ]}
    h = hinweise(ex, KATALOG)
    assert h == [{"teil": "Heizelement Graphit", "status": "ab Lager"},
                 {"teil": "Dichtung für die Tür", "status": "Verfügbarkeit wird geprüft"}]


def test_ohne_ersatzteil_leer():
    assert hinweise({"anliegen": [{"kategorie": "wartung", "beschreibung": "x"}]}, KATALOG) == []
    assert hinweise({}, KATALOG) == []
```

- [ ] **Step 2: Fehlschlag prüfen** — beide Testdateien.

- [ ] **Step 3: Implementierung**

`app/kalender.py` komplett:

```python
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
_VAKUUM = re.compile(r"vakuum|pumpe|leck|druck|mbar", re.I)
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
```

`app/ersatzteile.py`:

```python
"""Ersatzteil-Verfügbarkeit aus einer kleinen Katalogdatei. Kein Modell, reine Begriffssuche."""
import json
from pathlib import Path

KATALOG_PFAD = Path(__file__).resolve().parent.parent / "data" / "ersatzteile.json"
FALLBACK = "Verfügbarkeit wird geprüft"


def lade_katalog(pfad=None) -> list[dict]:
    p = Path(pfad) if pfad else KATALOG_PFAD
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else []


def hinweise(extraktion: dict, katalog: list[dict] | None = None) -> list[dict]:
    katalog = lade_katalog() if katalog is None else katalog
    ergebnis = []
    for a in extraktion.get("anliegen") or []:
        if a.get("kategorie") != "ersatzteil":
            continue
        beschreibung = (a.get("beschreibung") or "").lower()
        treffer = next((k for k in katalog if any(b in beschreibung for b in k["begriffe"])), None)
        if treffer:
            ergebnis.append({"teil": treffer["teil"], "status": treffer["status"]})
        else:
            ergebnis.append({"teil": a.get("beschreibung") or "Ersatzteil", "status": FALLBACK})
    return ergebnis
```

`data/ersatzteile.json`:

```json
[
  {"begriffe": ["heizelement", "heizstab", "heizleiter"], "teil": "Heizelement Graphit", "status": "ab Lager"},
  {"begriffe": ["thermoelement"], "teil": "Thermoelement Typ S", "status": "ab Lager"},
  {"begriffe": ["vorpumpe", "vakuumpumpe", "drehschieber"], "teil": "Vorvakuumpumpe", "status": "Lieferzeit ca. 3 Wochen"},
  {"begriffe": ["dichtung", "o-ring", "türdichtung"], "teil": "Dichtungssatz Kammertür", "status": "ab Lager"},
  {"begriffe": ["platine", "steuerungsbaugruppe", "sps-modul", "netzteil"], "teil": "Steuerungsbaugruppe", "status": "Lieferzeit ca. 6 Wochen"},
  {"begriffe": ["schauglas", "sichtfenster"], "teil": "Schauglas mit Dichtung", "status": "ab Lager"}
]
```

`data/kalender.json` per Einzeiler erzeugen (nicht als Skript ablegen):

```bash
python -c "
from datetime import date
from app.kalender import erzeuge_kalender, speichere_kalender
k = erzeuge_kalender(date(2026, 9, 14), wochen=3)
for t in k['tage']:
    if t['datum'] <= '2026-09-18': t['belegt'].append('T1')
    if t['datum'] in ('2026-09-16', '2026-09-17'): t['belegt'].append('T3')
    if '2026-09-21' <= t['datum'] <= '2026-09-25': t['belegt'].append('T5')
    if t['datum'] in ('2026-09-15', '2026-09-22', '2026-09-29'): t['belegt'].append('T2')
speichere_kalender(k, 'data/kalender.json'); print(len(k['tage']), 'Tage')
"
```

- [ ] **Step 4: Tests** — `python -m pytest tests/test_kalender.py tests/test_ersatzteile.py -q` grün.

- [ ] **Step 5: Commit** — `feat(kalender): Technikerkalender nach Qualifikation, Ersatzteilhinweise`.

---

### Task 4: Antwortentwurf

**Files:** Modify `app/antwort.py`, `tests/test_antwort.py`.

**Interfaces:**
- Produces: `baue_antwort(ex: dict, termin: dict | None, betreff: str, ersatzteile: list[dict] | None = None) -> str`.

- [ ] **Step 1: Tests** — `tests/test_antwort.py` komplett ersetzen:

```python
from app.antwort import baue_antwort

EX = {
    "kunde": {"firma": "Hartmann Wärmebehandlung GmbH"},
    "ansprechpartner": {"anrede": "Herr", "name": "Frank Lindemann"},
    "anlage": {"typ": "VKUQ 50", "nummer": "VK-5000-0231", "baujahr": 2015},
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"},
                 {"kategorie": "ersatzteil", "beschreibung": "zwei Heizelemente"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": [],
}
TERMIN = {"datum": "2026-09-21", "techniker": "T4", "qualifikation": "mechanik", "hinweis": ""}
TEILE = [{"teil": "Heizelement Graphit", "status": "ab Lager"}]


def test_entwurf_mit_einsatz_und_ersatzteil():
    t = baue_antwort(EX, TERMIN, "Wartung", TEILE)
    assert t.startswith("Sehr geehrter Herr Lindemann,")
    assert "„Wartung“" in t
    assert "Für Ihre Anlage VKUQ 50 (VK-5000-0231) haben wir notiert:" in t
    assert "- Wartung: Jahreswartung" in t and "- Ersatzteil: zwei Heizelemente" in t
    assert "Servicetechnikers (Mechanik) am Montag, 21.09.2026" in t
    assert "Ersatzteil Heizelement Graphit: ab Lager" in t
    assert "[" not in t and t.rstrip().endswith("Ihr Serviceteam")


def test_entwurf_hinweis_und_unklarheit():
    ex = dict(EX, unklarheiten=["Anlagennummer fehlt"], anlage={"typ": None, "nummer": None, "baujahr": None})
    t = baue_antwort(ex, dict(TERMIN, hinweis="Im Wunschzeitraum ist kein passender Techniker frei, Vorschlag liegt außerhalb."), "x")
    assert "Für Ihre Anlage haben wir notiert:" in t
    assert "kein passender Techniker frei" in t and "Anlagennummer fehlt" in t


def test_entwurf_vertrieb_weiterleitung():
    ex = dict(EX, zustaendigkeit="vertrieb", anliegen=[{"kategorie": "angebot", "beschreibung": "zweiter Lötofen"}])
    t = baue_antwort(ex, None, "Neuanlage")
    assert "Vertrieb" in t and "weitergeleitet" in t and "- Angebot: zweiter Lötofen" in t
    assert "Einsatz" not in t.split("weitergeleitet")[0]


def test_entwurf_nur_ersatzteil_ohne_termin():
    ex = dict(EX, anliegen=[{"kategorie": "ersatzteil", "beschreibung": "Dichtung"}])
    t = baue_antwort(ex, None, "", [{"teil": "Dichtungssatz Kammertür", "status": "ab Lager"}])
    assert "vielen Dank für Ihre Anfrage." in t
    assert "Ersatzteil Dichtungssatz Kammertür: ab Lager" in t
    assert "Terminvorschlag" not in t and "melden uns" not in t
    assert "Angebot" in t  # Hinweis, dass ein Angebot folgt


def test_entwurf_ohne_namen_ohne_termin():
    ex = dict(EX, ansprechpartner={"anrede": None, "name": None}, anliegen=[{"kategorie": "stoerung", "beschreibung": "x"}])
    t = baue_antwort(ex, None, "x")
    assert t.startswith("Guten Tag,") and "melden uns" in t
```

- [ ] **Step 2: Fehlschlag prüfen.**

- [ ] **Step 3: Implementierung** — `app/antwort.py` komplett:

```python
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
```

- [ ] **Step 4: Tests** grün. **Step 5: Commit** — `feat(antwort): Vorlage fuer Serviceeinsatz und Ersatzteilhinweise`.

---

### Task 5: Testmails, Pipeline, Server

**Files:**
- Replace: `data/mails.json`; Modify: `app/pipeline.py`, `app/main.py`, `tests/test_pipeline.py`, `tests/test_main.py`, `tests/test_echtlauf.py`

**Interfaces:**
- Consumes: Task 1 `anonymisiere(text, absender_name, absender_firma)`; Task 3 `finde_termin`, `belege(kal, datum, techniker)`, `gebe_frei`, `ersatzteile.hinweise`; Task 4 `baue_antwort(ex, termin, betreff, ersatzteile)`.
- Produces: Ergebnisobjekt mit zusätzlichem Feld `ersatzteile: list[dict]`; `NeueMail.absender_firma: str = ""`.

- [ ] **Step 1: `data/mails.json`** exakt so anlegen (Write-Tool, UTF-8):

```json
[
  {"id": "m01", "absender_name": "Frank Lindemann", "absender_firma": "Hartmann Wärmebehandlung GmbH", "absender_email": "f.lindemann@hartmann-wb.example", "betreff": "Wartung Ofen Halle 3", "empfangen": "2026-09-11T07:52:00",
   "text": "Guten Morgen,\n\nder Ofen in Halle 3 ist mit der Jahreswartung dran, die Wartungsanzeige leuchtet seit letzter Woche. Die Nummer vom Typenschild habe ich gerade nicht zur Hand, es ist der große Vakuumhärteofen, den Sie 2019 bei uns aufgestellt haben. Nächste Woche würde passen, wir haben da wenig Chargen.\n\nViele Grüße\nFrank Lindemann\nInstandhaltung\nHartmann Wärmebehandlung GmbH\nAm Gewerbepark 12\n36381 Schlüchtern\nTel. 06661 / 90 12 34"},
  {"id": "m02", "absender_name": "Sabine Roth", "absender_firma": "Roth & Söhne Metallguss GmbH & Co. KG", "absender_email": "roth@roth-metallguss.example", "betreff": "DRINGEND: VIM 30 steht, Fehler F-217", "empfangen": "2026-09-11T09:14:00",
   "text": "Hallo,\n\nunsere VIM 30 (SN VIM-3000-0917) ist heute um 8:40 Uhr mit Fehlercode F-217 am Bedienfeld stehen geblieben. Der Rezeptlauf lässt sich nicht fortsetzen, die Charge sitzt im Ofen. Wir haben die Anlage nicht neu gestartet, weil wir nicht wissen, ob das der Charge schadet. Bitte rufen Sie mich so schnell wie möglich an, die Produktion steht.\n\nSabine Roth\nWerksleitung\nRoth & Söhne Metallguss GmbH & Co. KG\n0171 555 20 44"},
  {"id": "m03", "absender_name": "Michael Berger", "absender_firma": "Berger Zerspanung GmbH", "absender_email": "einkauf@berger-zerspanung.example", "betreff": "Angebot Wartungsvertrag", "empfangen": "2026-09-11T10:30:00",
   "text": "Sehr geehrte Damen und Herren,\n\nwir betreiben seit 2003 einen Vakuumhärteofen von Ihnen, auf dem Typenschild steht als Nummer R 03/118. Die Anlage läuft noch gut, wir möchten aber einen Wartungsvertrag abschließen. Bitte senden Sie mir ein Angebot für eine jährliche Wartung inklusive Vakuumprüfung.\n\nMit freundlichen Grüßen\nMichael Berger\nEinkauf\nBerger Zerspanung GmbH"},
  {"id": "m04", "absender_name": "Katja Menzel", "absender_firma": "Präzisionsteile Menzel AG", "absender_email": "k.menzel@menzel-praezision.example", "betreff": "Mehrere Punkte zu Anlage VK-5000-0231", "empfangen": "2026-09-11T13:05:00",
   "text": "Hallo Herr Weber,\n\nzu unserer VKUQ 50, Anlagennummer VK-5000-0231, habe ich drei Punkte:\n1. Wir brauchen zwei neue Heizelemente, bei der letzten Charge sind zwei durchgebrannt. Bitte Preis und Lieferzeit.\n2. Die Jahreswartung ist im Oktober fällig, gern in der ersten Oktoberwoche.\n3. Unsere Geschäftsführung möchte ein Angebot für ein Retrofit der Steuerung, die alte Bedienoberfläche versteht keiner mehr.\n\nDanke und Gruß\nKatja Menzel\nEinkauf Technik\nPräzisionsteile Menzel AG\nIndustriestraße 8\n63741 Aschaffenburg"},
  {"id": "m05", "absender_name": "Thorsten Vogel", "absender_firma": "AeroForm Luftfahrttechnik GmbH", "absender_email": "t.vogel@aeroform.example", "betreff": "Anfrage zweiter Vakuumlötofen", "empfangen": "2026-09-12T08:20:00",
   "text": "Sehr geehrte Damen und Herren,\n\nwir planen für 2027 einen zweiten Vakuumlötofen für Wärmetauscher aus Aluminium, Nutzraum etwa 1200 x 800 x 800 mm, Chargengewicht bis 400 kg. Bitte senden Sie uns Unterlagen und ein Richtpreisangebot. Ein Termin für eine Besichtigung Ihrer Referenzanlage wäre ebenfalls interessant.\n\nMit freundlichen Grüßen\nThorsten Vogel\nLeiter Produktionstechnik\nAeroForm Luftfahrttechnik GmbH\nFlugplatzstraße 21\n63329 Egelsbach\nTelefon 06103 / 44 55 66"},
  {"id": "m06", "absender_name": "Petra Schulz", "absender_firma": "Kolb Zahnradfabrik GmbH", "absender_email": "p.schulz@kolb-zahnrad.example", "betreff": "WG: WG: Thermoelement Ofen 2", "empfangen": "2026-09-12T09:45:00",
   "text": "Hallo Serviceteam,\n\nbitte kümmern Sie sich darum, siehe unten. Bestellung läuft über mich.\n\nGruß\nPetra Schulz\nEinkauf\nKolb Zahnradfabrik GmbH\n\n> Von: Bernd Kolb\n> Petra, bitte an den Hersteller weiterleiten, ich komme nicht dazu.\n>\n> > Von: Instandhaltung\n> > Bernd, das Thermoelement an Ofen 2 (SN VK-2200-0144) zeigt seit Dienstag 30 Grad zu wenig, wir fahren im Moment nach dem Referenzfühler.\n> > Brauchen ein neues Thermoelement Typ S und jemanden, der es kalibriert.\n> >\n> > > Von: Schichtführer\n> > > Ofen 2 Temperatur passt nicht, bitte prüfen."},
  {"id": "m07", "absender_name": "Daniel Price", "absender_firma": "Northgate Aerospace Ltd.", "absender_email": "d.price@northgate-aero.example", "betreff": "Vacuum leak VIM 22, line down", "empfangen": "2026-09-12T11:10:00",
   "text": "Hello,\n\nour VIM 22 furnace, serial VIM-2200-0417, cannot reach the working vacuum since this morning. We stop at about 5x10-2 mbar, the pump runs constantly. The heat treatment line is down and we have two batches waiting. Please advise whether a technician can come this week, and whether we should check the door seal ourselves in the meantime.\n\nBest regards\nDaniel Price\nMaintenance Manager\nNorthgate Aerospace Ltd.\nPhone +44 1234 567890"},
  {"id": "m08", "absender_name": "Jürgen Aurich", "absender_firma": "Schmiedewerk Aurich GmbH", "absender_email": "aurich@schmiedewerk-aurich.example", "betreff": "Ofen riecht komisch", "empfangen": "2026-09-12T14:30:00",
   "text": "Hallo,\n\nseit ein paar Tagen riecht es beim Öffnen unseres Härteofens komisch, so verbrannt. Und die letzte Charge war nicht durchgehärtet, die Härteprüfung ist unten durchgefallen. Ich weiß nicht, ob das zusammenhängt. Kann sich das mal jemand anschauen?\n\nGruß\nJürgen Aurich\nSchmiedewerk Aurich GmbH\n06021 / 33 44 55"},
  {"id": "m09", "absender_name": "Andrea Wittmann", "absender_firma": "Wittmann Feinmechanik GmbH", "absender_email": "a.wittmann@wittmann-fm.example", "betreff": "Türdichtung, Foto vom Typenschild anbei", "empfangen": "2026-09-13T08:05:00",
   "text": "Guten Tag,\n\ndie Türdichtung an unserem Vakuumofen ist spröde und wir verlieren Vakuum. Bitte schicken Sie uns ein Angebot für eine neue Dichtung. Das Foto vom Typenschild mit der Anlagennummer hänge ich an, damit Sie die richtige Ausführung finden.\n\nMit freundlichen Grüßen\nAndrea Wittmann\nWittmann Feinmechanik GmbH\nAm Bahndamm 7\n63571 Gelnhausen\nTelefon 06051 / 88 17 20"},
  {"id": "m10", "absender_name": "R. Hoffmann", "absender_firma": "Härterei Hoffmann KG", "absender_email": "r.hoffmann@haerterei-hoffmann.example", "betreff": "Ofen 2 steht", "empfangen": "2026-09-13T09:22:00",
   "text": "Ofen 2 steht. Vorpumpe läuft nicht an, Sicherung ok. SN VSP-1800-0221. Rückruf 0160 77 88 99 0."},
  {"id": "m11", "absender_name": "Claudia Nordmann", "absender_firma": "Nordlicht Turbinentechnik AG", "absender_email": "c.nordmann@nordlicht-turbinen.example", "betreff": "Temperaturschwankungen nach Ihrem Serviceeinsatz", "empfangen": "2026-09-13T10:40:00",
   "text": "Sehr geehrter Herr Braun,\n\nnach dem Serviceeinsatz Ihrer Kollegen am 2. September an unserer VIM 40 (Anlage VIM-4000-0088) schwankt die Temperatur in der Haltephase um bis zu 15 Grad, vorher waren es 3. Wir haben die Aufzeichnungen der letzten fünf Chargen. Ich erwarte, dass das im Rahmen des Einsatzes nachgebessert wird, und bitte um einen Termin in der Woche vom 21. September.\n\nMit freundlichen Grüßen\nClaudia Nordmann\nWerksleiterin\nNordlicht Turbinentechnik AG"},
  {"id": "m12", "absender_name": "Stefan Bergmann", "absender_firma": "Bergmann Automotive Systems AG", "absender_email": "s.bergmann@bergmann-as.example", "betreff": "Turnuswartung KW 40, zwei Anlagen", "empfangen": "2026-09-13T11:15:00",
   "text": "Hallo,\n\nfür unsere beiden Anlagen VK-5000-0198 und VK-5000-0199 steht die halbjährliche Wartung an. Bitte beide in der KW 40 an einem Tag, vormittags, damit die Linie nur einmal steht. Den Wartungsvertrag haben wir, die Nummer ist WV-2024-117.\n\nBeste Grüße\nStefan Bergmann\nInstandhaltungsleitung\nBergmann Automotive Systems AG\nMotorenstraße 3\n60437 Frankfurt am Main\nTel. 069 / 12 34 56 78"},
  {"id": "m13", "absender_name": "Klaus Weber", "absender_firma": "Gussteile Weber KG", "absender_email": "k.weber@gussteile-weber.example", "betreff": "Heizung ausgefallen, Produktion steht", "empfangen": "2026-09-13T13:00:00",
   "text": "Hallo,\n\nan unserem Vakuumofen VK-3600-0304 fällt seit heute früh die Heizung aus, nach etwa zehn Minuten Aufheizen fliegt die Sicherung im Schaltschrank. Wir haben es dreimal probiert. Die Produktion steht, wir haben Liefertermine diese Woche. Bitte so schnell wie möglich jemanden schicken.\n\nKlaus Weber\nGussteile Weber KG\n0170 22 33 44 5"},
  {"id": "m14", "absender_name": "Lena Lindqvist", "absender_firma": "Lindqvist Härterei GmbH", "absender_email": "l.lindqvist@lindqvist-haerterei.example", "betreff": "Umzug einer Anlage an neuen Standort", "empfangen": "2026-09-13T15:20:00",
   "text": "Guten Tag,\n\nwir ziehen im Dezember mit der Produktion nach Hanau um und möchten unseren Vakuumofen VK-2200-0301 mitnehmen. Bitte machen Sie uns ein Angebot für Demontage, Transportbegleitung und Wiederinbetriebnahme am neuen Standort. Der genaue Termin steht noch nicht fest, irgendwann in der zweiten Dezemberhälfte.\n\nFreundliche Grüße\nLena Lindqvist\nGeschäftsführung\nLindqvist Härterei GmbH"},
  {"id": "m15", "absender_name": "Markus Sauer", "absender_firma": "Metallwerk Sauer GmbH", "absender_email": "m.sauer@metallwerk-sauer.example", "betreff": "Ersatzteil 4711-0815-22 und Frage zur Wartung", "empfangen": "2026-09-13T16:45:00",
   "text": "Hallo,\n\nwir brauchen die Steuerungsplatine mit der Teilenummer 4711-0815-22 für unsere VK-3600-0177, die alte hat einen Wackelkontakt, die Anlage läuft aber noch. Wie ist die Lieferzeit? Und wann war eigentlich die letzte Wartung bei uns, ich finde den Bericht nicht.\n\nGruß\nMarkus Sauer\nMetallwerk Sauer GmbH\nHüttenweg 14\n63505 Langenselbold\nTel 06184 / 90 80 70"}
]
```

- [ ] **Step 2: Tests**

`tests/test_pipeline.py`: `ANTWORT` durch ein Objekt im neuen Schema ersetzen:

```python
ANTWORT = {
    "kunde": {"firma": "[FIRMA_1]"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "anlage": {"typ": "Vakuumhärteofen", "nummer": None, "baujahr": 2019},
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": ["Anlagennummer fehlt"],
}
```

`test_modell_sieht_keine_originale`: zusätzlich `assert mail["absender_firma"] not in gesendet`. `test_ergebnis_felder_und_rueckersetzung`: Erwartungen `erg["extraktion"]["ansprechpartner"]["name"] == "Frank Lindemann"`, `erg["extraktion"]["kunde"]["firma"] == "Hartmann Wärmebehandlung GmbH"`, `erg["termin"] == {"datum": "2026-09-21", "techniker": "T4", "qualifikation": "mechanik", "hinweis": ""}` (T2 ist am 22.09. belegt, aber am 21.09. frei — prüfe: T2 hat mechanik und ist am 21.09. frei, also `techniker == "T2"`; die Reihenfolge der Technikerliste entscheidet: T2 steht vor T4 → **"T2"**), `erg["ersatzteile"] == []`, `"Frank Lindemann" not in erg["pseudonym_text"]`, `"Hartmann" not in erg["pseudonym_text"]`. `test_ungueltige_modellantwort…`: `"Frank Lindemann" not in …`. `_woerter` und `test_kein_original_erreicht_das_modell`: Rechtsform-Kürzel ausnehmen:

```python
_GENERISCH = {"gmbh", "ag", "kg", "kgaa", "se", "ohg", "co.", "co", "&", "ltd.", "ltd", "inc.", "und", "e.k."}


def _woerter(wert: str) -> set[str]:
    return {t for t in wert.split() if len(t) >= 3 and t.lower() not in _GENERISCH}
```

und `verboten` um `mail["absender_firma"]` sowie `_woerter(mail["absender_firma"])` erweitern. Neuer Test:

```python
def test_anlagennummern_erreichen_das_modell():
    """Bewusst: Anlagen-/Seriennummern und Fehlercodes sind keine Platzhalter."""
    kal = lade_kalender("data/kalender.json")
    erwartet = {"m02": ["VIM-3000-0917", "F-217"], "m03": ["R 03/118"], "m10": ["VSP-1800-0221"], "m15": ["4711-0815-22"]}
    for mail in lade_mails():
        if mail["id"] in erwartet:
            fake = FakeClient(ANTWORT)
            verarbeite(mail, fake, kal, HEUTE)
            for wert in erwartet[mail["id"]]:
                assert wert in fake.aufrufe[0], (mail["id"], wert)
```

`tests/test_main.py`: `ANTWORT` wie oben; `test_verarbeiten_und_freigeben`: `r["extraktion"]["ansprechpartner"]["name"] == "Frank Lindemann"`; Kalenderprüfung: `tag = [t for t in kal["tage"] if t["datum"] == "2026-09-21"][0]; assert "T2" in tag["belegt"]`; `test_freigabe_zyklus…`: `assert "T2" not in tag["belegt"]` nach dem Zyklus, danach `in`; `test_neu_verarbeiten_gibt_…`: analog mit `"T2"`; `test_freigabe_bei_vollem_halbtag…` umbenennen in `test_freigabe_bei_belegtem_techniker_wird_abgelehnt`: im tmp-Kalender am 21.09. `"T2"` und `"T4"` in `belegt` eintragen, dann verarbeiten (Termin fällt auf 22.09.? — nein: Vorschlag wird bei der Verarbeitung berechnet; Reihenfolge: erst verarbeiten, dann im Kalender den vorgeschlagenen Techniker am vorgeschlagenen Datum belegen, dann POST freigegeben → 409 mit "Techniker ist an dem Tag inzwischen belegt"), Status bleibt offen. `test_neue_mail_anlegen`: JSON um `"absender_firma": "Testfirma GmbH"` ergänzen und `assert "Testfirma" not in e["pseudonym_text"]`.

`tests/test_echtlauf.py`: Mail `m04`, Erwartungen: `status == "offen"`, `len(anliegen) >= 3`, `anlage.nummer == "VK-5000-0231"`, `kunde.firma == "Präzisionsteile Menzel AG"`, `zustaendigkeit == "service"`.

- [ ] **Step 3: Fehlschlag prüfen** — `python -m pytest tests/test_pipeline.py tests/test_main.py -q`.

- [ ] **Step 4: Implementierung**

`app/pipeline.py`: Import `from app.ersatzteile import hinweise as ersatzteil_hinweise`; Aufruf `anonymisiere(mail["text"], mail.get("absender_name"), mail.get("absender_firma"))`; Ergebnisfeld `"ersatzteile": []` hinter `"termin": None`; im else-Zweig:

```python
        ergebnis["termin"] = finde_termin(kalender, extraktion, heute)
        ergebnis["extraktion"] = zuruecksetzen(extraktion, tabelle)
        ergebnis["ersatzteile"] = ersatzteil_hinweise(ergebnis["extraktion"])
        ergebnis["antwort_entwurf"] = baue_antwort(ergebnis["extraktion"], ergebnis["termin"],
                                                   mail.get("betreff", ""), ergebnis["ersatzteile"])
```

`app/main.py`: Titel `FastAPI(title="Serviceanfragen-Assistent")`, Docstring; `NeueMail` bekommt `absender_firma: str = ""`; `_gib_alten_termin_frei` und `status_setzen` verwenden `termin["techniker"]` statt `termin["halbtag"]`; 409-Text: `"Techniker ist an dem Tag inzwischen belegt, Termin kann nicht freigegeben werden"`; Kommentar entsprechend. `/api/mails` liefert zusätzlich `"absender_firma": m.get("absender_firma", "")`.

- [ ] **Step 5: Tests** — `python -m pytest -q` komplett grün (Echtlauf skippt).

- [ ] **Step 6: Commit** — `feat(pipeline): Serviceanfragen-Testmails, Ersatzteilhinweise, Technikertermine im Server`.

---

### Task 6: Oberfläche, README, Gesprächsleitfaden

**Files:** Modify `docs/index.html`, `README.md`, `docs/GESPRAECH.md`, `app/cli.py` (nur Docstring falls „Werkstatt" vorkommt).

- [ ] **Step 1: `docs/index.html`**
  - `<title>` und `<h1>`: „Serviceanfragen-Assistent – Demo". Untertitel bleibt.
  - Formular „Neue Mail": nach dem Absender-Feld `<label>Firma</label><input type="text" id="f-firma">`; im Senden-Handler `absender_firma: document.getElementById("f-firma").value` mitschicken.
  - Mailliste: unter dem Betreff nichts Neues; im `.name` bleibt der Absendername.
  - `renderExtraktion`: Zeilen `Kunde` (Firma), `Ansprechpartner` (Anrede + Name), `Anlage` (typ · nummer · Baujahr), `Anliegen`, `Dringlichkeit`, `Wunschzeitraum`, `Zuständigkeit`, `Unklarheiten`. Alle Werte über `esc()`.
  - Rechte Spalte: `<h2>Einsatzvorschlag</h2>`; `zeigeRechts`: bei Termin `"<p><strong>" + esc(datum) + "</strong>, Techniker " + esc(techniker) + " (" + esc(qualifikation) + ")" + Hinweis`; bei `zustaendigkeit === "vertrieb"` „kein Einsatz (Vertrieb)"; sonst „kein Einsatz". Darunter, wenn `ergebnis.ersatzteile` nicht leer: `<h3>Ersatzteile</h3><ul>` mit `teil: status`.
  - Keine externen Ressourcen, Escaping wie bisher. Prüfen: `python -c` auf Vorkommen von „Werkstatt", „Kennzeichen", „Fahrzeug" in der Datei → 0 (außer der Wortstamm in „Werkstattanfragen" darf nicht vorkommen).

- [ ] **Step 2: `README.md`** neu schreiben, Abschnitte in dieser Reihenfolge (deutsch, erste Person, sachlich, keine Gedankenstriche, keine Semikola):
  1. Was das ist: Serviceanfragen eines Anlagenbauers (Wartung, Störung, Ersatzteil, Reklamation, Angebot) per Mail strukturiert erfassen, Einsatz eines Servicetechnikers vorschlagen, Antwortentwurf zur Freigabe. Eigenprojekt, erfundene Testdaten, entstanden für Bewerbungen.
  2. Demo im Browser: `https://dangtu1190-tech.github.io/serviceanfragen-assistent/`, statischer Modus.
  3. Kernstück Pseudonymisierung: Tabelle mit EMAIL, FIRMA, TELEFON, ADRESSE, ORT, NAME und Beispielen aus den neuen Mails. **Neuer Unterabschnitt „Warum diese Felder und keine anderen":** Anlagen- und Seriennummern, Fehlercodes und Anlagentypen werden bewusst nicht ersetzt, weil sie keine personenbezogenen Daten sind und das Modell sie für die Zuordnung braucht. Firmennamen werden ersetzt, nicht aus Datenschutzgründen, sondern weil sie Geschäftsgeheimnisse berühren (wer welche Anlage betreibt und welche Störungen hat). Die Auswahl der Felder ist eine Entscheidung je Anwendungsfall, keine Pauschalregel. Grenzen wie bisher (Namen im Fließtext, Kleinschreibung, gemeinsamer Nachname, Orte ohne PLZ, „am Main") plus neu: Firmen ohne Rechtsform im Namen werden nur erkannt, wenn sie als Absenderfirma bekannt sind.
  4. Pipeline (vier Schritte), Technikerkalender (Qualifikationen, Stillstand-Regel), Ersatzteilhinweise.
  5. Lokal starten (wie bisher).
  6. Modellzugriff (Tabelle wie bisher), Satz zum ungeprüften Ollama-Pfad wörtlich beibehalten.
  7. Testdaten: 15 Mails mit den Störfällen aus der Spec (Liste).
  8. Tests.
  9. GitHub Pages.
  10. Bewusst nicht enthalten.
  11. „Wie ich das in einem Betrieb umsetzen würde" (Text aus dem aktuellen README übernehmen, Beispiel Autohaus darf als eines von zwei Beispielen bleiben).

- [ ] **Step 3: `docs/GESPRAECH.md`** auf die neuen Mails: m01 (ohne Anlagennummer: Pseudonymisierung und Unklarheit), m02 (Stillstand mit Fehlercode, Einsatz vorgezogen, Fehlercode sichtbar im Modelltext), m05 (Vertrieb), m06 (drei Zitatebenen), m07 (englisch), m09 (fehlender Anhang als Unklarheit), „Neue Mail" live, Fehlerpfad.

- [ ] **Step 4:** `python -m pytest -q` grün; `git grep -n -i "werkstatt\|kennzeichen\|fahrzeug\|autohaus" -- app docs/index.html docs/GESPRAECH.md README.md` → nur noch das README-Beispiel in Abschnitt 11 und Modulnamen-Hinweise; alles andere melden.

- [ ] **Step 5: Commit** — `docs/ui: Serviceanfragen-Assistent, Feldauswahl der Pseudonymisierung begruendet`.

---

### Task 7: Echtlauf gegen Langdock

Wie beim ersten Bau: Schlüssel nur in der Shell (`export LLM_API_KEY=...` aus der lokalen Umgebung, nie in eine Datei), `python -m pytest tests/test_echtlauf.py -q -s`, dann `python -m app.cli --neu --pages`, Sichtprüfung und Leck-Prüfung:

```bash
python -c "
import json; e=json.load(open('data/ergebnisse.json',encoding='utf-8')); m={x['id']:x for x in json.load(open('data/mails.json',encoding='utf-8'))}
for k,v in e.items():
    x=v['extraktion'] or {}
    print(k, v['status'], x.get('zustaendigkeit'), x.get('dringlichkeit'), (x.get('anlage') or {}).get('nummer'), [a['kategorie'] for a in x.get('anliegen',[])], v['termin'] and (v['termin']['datum'], v['termin']['techniker']), x.get('unklarheiten'))
lecks=[(k,p['original']) for k,v in e.items() for p in v['platzhalter'] if p['original'] in v['pseudonym_text']]
lecks+=[(k,m[k]['absender_firma']) for k,v in e.items() if m[k]['absender_firma'] in v['pseudonym_text']]
print('Lecks:', lecks)
"
```

Erwartungen: m02, m07, m10, m13 `stillstand` mit Einsatz am 14.09.; m05 `vertrieb`; m01 und m08 mit Unklarheit Anlagennummer; m09 Unklarheit fehlender Anhang; m04 drei Anliegen; m06 Anliegen aus den Zitaten (Thermoelement, Kalibrierung); m03 Nummer `R 03/118` wörtlich. Abweichungen werden im Report als Liste „Mails, bei denen die Extraktion Mühe hat" festgehalten, nicht korrigiert. Commit `feat: Echtlauf Serviceanfragen, Ergebnisse fuer die Browser-Demo`.
