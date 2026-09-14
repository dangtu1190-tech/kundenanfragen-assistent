# Werkstatt-Terminassistent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine lokale Demo, die Werkstatt-Anfragen per E-Mail pseudonymisiert, per Sprachmodell in JSON extrahiert, gegen einen Kapazitätskalender einen Termin vorschlägt und einen Antwortentwurf zur Freigabe zeigt.

**Architecture:** Reine Python-Rechenkerne (Anonymisierung, Kalender, Antwort, Extraktions-Schema) ohne Netz und ohne FastAPI, darüber eine Pipeline, ein CLI und ein dünner FastAPI-Server. Die Oberfläche ist eine HTML-Datei unter `docs/`, die gegen den Server ODER statisch gegen JSON-Dateien läuft (GitHub Pages). Das Modell wird über einen OpenAI-kompatiblen Client angesprochen, Basis-URL je Anbieter (Langdock EU oder Ollama).

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pydantic v2, openai (SDK, nur als HTTP-Client), pytest, Vanilla JS.

**Spec:** `planung/specs/2026-09-09-werkstatt-terminassistent-design.md`

## Global Constraints

- Sprache in Code, Kommentaren, UI und Commits: Deutsch. Bezeichner deutsch (wie im Spec).
- Keine echten Personen, Kennzeichen, Telefonnummern: alle Testdaten sind erfunden.
- Das Modell bekommt AUSSCHLIESSLICH den pseudonymisierten Text. Kein Aufruf darf `roh_text` senden.
- Kein API-Schlüssel im Repo. `.env` ist gitignored, `.env.example` enthält nur Platzhalter.
- Basisdatum der Demo: `2026-09-14` (Montag). Alle Datumsrechnungen nehmen `heute` als Parameter, nie `date.today()` im Rechenkern.
- Dateien unter 300 Zeilen halten.
- Arbeitsverzeichnis für alle Befehle: `<Projektordner>`. Python: `python` (3.12).
- Commits enden mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## Dateistruktur

| Datei | Verantwortung |
|---|---|
| `app/__init__.py` | Paketmarker |
| `app/anonymisierung.py` | Platzhalter setzen und zurücksetzen, reiner Rechenkern |
| `app/kalender.py` | Kalender laden/speichern, freien Halbtag finden, belegen |
| `app/extraktion.py` | Pydantic-Schema, Prompt, Antwort parsen, `extrahiere()` |
| `app/llm_client.py` | Konfiguration aus Umgebung, OpenAI-kompatibler Client, Fake für Tests |
| `app/antwort.py` | Antwortentwurf aus Vorlage |
| `app/speicher.py` | JSON-Dateien lesen/schreiben (mails, ergebnisse) |
| `app/pipeline.py` | `verarbeite()` – die vier Schritte, liefert Ergebnis-dict |
| `app/cli.py` | alle Mails verarbeiten, Ergebnisse schreiben, Pages-Kopie |
| `app/main.py` | FastAPI-Routen |
| `data/mails.json`, `data/kalender.json`, `data/ergebnisse.json` | Daten |
| `docs/index.html` | Oberfläche, auch GitHub-Pages-Seite |
| `docs/data/` | Kopie von mails.json + ergebnisse.json für Pages |
| `tests/` | pytest |

---

### Task 1: Projektgerüst und Anonymisierung

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`, `app/__init__.py`, `tests/__init__.py`
- Create: `app/anonymisierung.py`
- Test: `tests/test_anonymisierung.py`

**Interfaces:**
- Produces:
  - `anonymisiere(text: str, absender_name: str | None = None) -> tuple[str, list[dict]]` – gibt pseudonymisierten Text und Tabelle `[{"typ": "NAME", "platzhalter": "[NAME_1]", "original": "Max Muster"}, ...]` zurück.
  - `zuruecksetzen(obj, tabelle: list[dict])` – ersetzt Platzhalter in `str`, rekursiv in `dict`/`list`; andere Typen unverändert.
  - `PLATZHALTER_MUSTER` – kompiliertes Regex, das jeden Platzhalter `[TYP_n]` erkennt.

- [ ] **Step 1: Gerüst anlegen**

`requirements.txt`:
```
fastapi==0.115.*
uvicorn==0.30.*
pydantic>=2.6,<3
openai>=1.40,<3
pytest>=8
httpx>=0.27
```

`.gitignore`:
```
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

`.env.example`:
```
# Anbieter: langdock oder ollama
LLM_PROVIDER=langdock
# Langdock EU-Endpunkt (OpenAI-kompatibel). Für Ollama: http://localhost:11434/v1
LLM_BASE_URL=https://api.langdock.com/openai/eu/v1
# Modellname. Langdock z. B. gpt-5.1, Ollama z. B. qwen2.5:7b
LLM_MODEL=gpt-5.1
# Schlüssel. Bei Ollama beliebiger Wert.
LLM_API_KEY=
```

`pytest.ini`:
```
[pytest]
testpaths = tests
pythonpath = .
```

`app/__init__.py` und `tests/__init__.py`: leer.

Run: `python -m pip install -r requirements.txt -q` (nur fehlende Pakete werden geholt; fastapi, openai, pytest, httpx sind bereits vorhanden).

- [ ] **Step 2: Failing Tests schreiben**

`tests/test_anonymisierung.py`:
```python
from app.anonymisierung import anonymisiere, zuruecksetzen, PLATZHALTER_MUSTER


def test_email_wird_ersetzt():
    text, tab = anonymisiere("Bitte antworten an max.muster@example.org, danke.")
    assert "max.muster@example.org" not in text
    assert "[EMAIL_1]" in text
    assert tab == [{"typ": "EMAIL", "platzhalter": "[EMAIL_1]", "original": "max.muster@example.org"}]


def test_telefon_varianten():
    text, tab = anonymisiere("Tel 0176 12345678 oder 06021/123456 oder +49 171 2345678 oder 0 60 21 / 12 34 56")
    originale = [t["original"] for t in tab if t["typ"] == "TELEFON"]
    assert len(originale) == 4
    for o in originale:
        assert o not in text
    assert "[TELEFON_4]" in text


def test_telefon_frisst_keine_daten_uhrzeiten_kilometer():
    text, tab = anonymisiere("Am 14.09.2026 um 08:30 Uhr, 85.000 km, Baujahr 2019, seit 2021.")
    assert tab == []
    assert "14.09.2026" in text and "08:30" in text and "85.000 km" in text


def test_kennzeichen_varianten():
    text, tab = anonymisiere("Kennzeichen MKK-AB 1234, AB CD 567, HU-X 99E, F-TR2020, ab-cd 1234")
    originale = [t["original"] for t in tab if t["typ"] == "KENNZEICHEN"]
    assert len(originale) == 5
    for o in originale:
        assert o not in text


def test_fahrzeugmodelle_bleiben():
    text, tab = anonymisiere("VW T6.1, Toyota RAV4, BMW X5, VW ID.4, Audi A4, HU/AU fällig")
    assert [t for t in tab if t["typ"] == "KENNZEICHEN"] == []
    assert "VW T6.1" in text and "RAV4" in text


def test_adresse_und_ort():
    text, tab = anonymisiere("Musterstraße 12a\n63739 Aschaffenburg\nAm Alten Weg 3, 63607 Wächtersbach")
    typen = [t["typ"] for t in tab]
    assert typen.count("ADRESSE") == 2
    assert typen.count("ORT") == 2
    assert "Musterstraße" not in text and "63739" not in text and "Wächtersbach" not in text


def test_name_aus_absender_auch_einzeln_und_kleingeschrieben():
    text, tab = anonymisiere("hallo, hier ist max muster. Muster nochmal, und Max auch.", absender_name="Max Muster")
    assert "[NAME_1]" in text
    assert "Muster" not in text and "Max" not in text and "max muster" not in text
    assert tab[0] == {"typ": "NAME", "platzhalter": "[NAME_1]", "original": "Max Muster"}


def test_name_aus_anrede_und_signatur():
    text, tab = anonymisiere(
        "Sehr geehrter Herr Schmidt,\nmeine Frau Sabine Krämer bringt den Wagen.\n\nViele Grüße\nPeter Krämer\nHauptstraße 5"
    )
    namen = {t["original"] for t in tab if t["typ"] == "NAME"}
    assert namen == {"Schmidt", "Sabine Krämer", "Peter Krämer"}
    assert "Krämer" not in text and "Sabine" not in text and "Schmidt" not in text


def test_signatur_firma_ist_kein_name():
    text, tab = anonymisiere("Danke.\n\nMit freundlichen Grüßen\nAutohaus Beispiel GmbH")
    assert [t for t in tab if t["typ"] == "NAME"] == []


def test_gleicher_wert_gleicher_platzhalter():
    text, tab = anonymisiere("Ruf 0176 12345678 an. Nochmal: 0176 12345678.")
    assert text.count("[TELEFON_1]") == 2
    assert len(tab) == 1


def test_platzhalter_werden_nicht_erneut_ersetzt():
    text, tab = anonymisiere("Herr Weber, Tel 0176 12345678, Kennzeichen AB-CD 1234")
    text2, tab2 = anonymisiere(text)
    assert text2 == text
    assert tab2 == []


def test_zuruecksetzen_rekursiv():
    text, tab = anonymisiere("Herr Weber, Tel 0176 12345678", absender_name="Karl Weber")
    obj = {"kunde": {"name": "[NAME_1]"}, "liste": ["[TELEFON_1]", 3, None], "text": text}
    zurueck = zuruecksetzen(obj, tab)
    assert zurueck["kunde"]["name"] == "Karl Weber"
    assert zurueck["liste"] == ["0176 12345678", 3, None]
    assert "[" not in zurueck["text"]


def test_platzhalter_muster():
    assert PLATZHALTER_MUSTER.fullmatch("[KENNZEICHEN_12]")
    assert not PLATZHALTER_MUSTER.fullmatch("[name_1]")
```

- [ ] **Step 3: Tests laufen lassen, Fehlschlag prüfen**

Run: `python -m pytest tests/test_anonymisierung.py -q`
Expected: ImportError / ModuleNotFoundError für `app.anonymisierung`.

- [ ] **Step 4: Implementierung**

`app/anonymisierung.py`:
```python
"""Pseudonymisierung vor dem Modellaufruf: Platzhalter setzen und zurücksetzen.

Reiner Rechenkern, deterministisch, ohne Modell. Reihenfolge der Muster:
E-Mail, Kennzeichen, Telefon, Adresse, PLZ+Ort, Namen. Bereits gesetzte
Platzhalter werden nie erneut angefasst (Text wird an ihnen zerlegt).
Bekannte Grenze: Namen im Fließtext ohne Anrede/Absender/Signatur bleiben.
"""
import re

PLATZHALTER_MUSTER = re.compile(r"\[(EMAIL|KENNZEICHEN|TELEFON|ADRESSE|ORT|NAME)_(\d+)\]")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Groß: 1-3 Buchstaben, Trenner, 1-2 Buchstaben; klein nur mit Bindestrich (sonst
# träfe "und am 21"); dann optional Trenner, 2-4 Ziffern, optional E/H
_KENNZEICHEN = re.compile(
    r"\b(?:[A-ZÄÖÜ]{1,3}[- ][A-ZÄÖÜ]{1,2}|[a-zäöü]{1,3}-[a-zäöü]{1,2})[- ]?\d{2,4}[EH]?\b"
)
_TELEFON = re.compile(r"(?<![\d.])(?:\+49|0)[\s\-/()]*\d(?:[\d\s\-/()]{4,}\d)")
# "Musterstraße 12a", "Am Alten Weg 3", "Am Bahndamm 7": Vorworte mit Großbuchstaben,
# Kern darf leer sein, damit "Weg"/"Platz" als eigenes Wort trifft
_ADRESSE = re.compile(
    r"\b(?:[A-ZÄÖÜ][\wäöüß]*[- ])*[A-ZÄÖÜ]?[\wäöüß]*"
    r"(?:[Ss]traße|[Ss]trasse|[Ss]tr\.|[Ww]eg|[Pp]latz|[Aa]llee|[Gg]asse|[Rr]ing|[Dd]amm|[Uu]fer)"
    r"\s+\d+\s?[a-z]?\b"
)
_ORT = re.compile(r"\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+(?:[- ][A-ZÄÖÜ][a-zäöüß]+)*")
_ANREDE = re.compile(r"\b(?:Herrn?|Frau|Hr\.|Fr\.)\s+([A-ZÄÖÜ][\wäöüß\-]+(?:\s+[A-ZÄÖÜ][\wäöüß\-]+)?)")
_HALLO = re.compile(r"^\s*(?:Hallo|Hi|Servus|Moin|Guten Tag)\s+([A-ZÄÖÜ][\wäöüß\-]+)\s*[,!]?\s*$", re.MULTILINE)
_GRUSS = re.compile(
    r"^\s*(?:Viele|Liebe|Beste|Schöne|Herzliche|Freundliche)?\s*(?:Grüße|Gruß|Grüsse|LG|MfG|VG|"
    r"Mit freundlichen Grüßen|Mit freundlichem Gruß|Servus|Ciao|Danke und Gruß|Best regards|Kind regards|Regards)"
    r"[\s,!.]*$",
    re.IGNORECASE,
)
_NAMENSZEILE = re.compile(r"^[A-ZÄÖÜ][\wäöüß\-.]*(?:\s+[A-ZÄÖÜ][\wäöüß\-.]*){0,2}$")
_KEIN_NAME = {"team", "werkstatt", "zusammen", "autohaus", "service", "gmbh", "ag", "kg", "ohg", "alle", "leute"}


def _ersetze(text: str, muster: re.Pattern, typ: str, tabelle: list, zuordnung: dict,
             fest: str | None = None) -> str:
    """Wendet `muster` nur auf Textstücke zwischen bestehenden Platzhaltern an.

    `fest`: ein bereits vergebener Platzhalter, der für jeden Treffer gesetzt
    wird (Namen: Groß-/Kleinschreibung darf keinen neuen Eintrag erzeugen).
    """
    stuecke = PLATZHALTER_MUSTER.split(text)
    # split mit Gruppen liefert [text, typ, nr, text, typ, nr, ...]
    ergebnis = []
    for i in range(0, len(stuecke), 3):
        stueck = stuecke[i]

        def _neu(m):
            if fest:
                return fest
            original = m.group(0)
            if typ == "TELEFON" and sum(c.isdigit() for c in original) < 7:
                return original
            return _platzhalter(typ, original, tabelle, zuordnung)

        ergebnis.append(muster.sub(_neu, stueck))
        if i + 2 < len(stuecke):
            ergebnis.append(f"[{stuecke[i + 1]}_{stuecke[i + 2]}]")
    return "".join(ergebnis)


def _platzhalter(typ: str, original: str, tabelle: list, zuordnung: dict) -> str:
    schluessel = (typ, original.strip())
    if schluessel not in zuordnung:
        nr = sum(1 for t in tabelle if t["typ"] == typ) + 1
        zuordnung[schluessel] = f"[{typ}_{nr}]"
        tabelle.append({"typ": typ, "platzhalter": zuordnung[schluessel], "original": original.strip()})
    return zuordnung[schluessel]


def _namenskandidaten(text: str, absender_name: str | None) -> list[str]:
    kandidaten = []
    if absender_name and absender_name.strip():
        kandidaten.append(absender_name.strip())
    kandidaten += _ANREDE.findall(text)
    kandidaten += [n for n in _HALLO.findall(text) if n.lower() not in _KEIN_NAME]
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        if _GRUSS.match(zeile):
            for folge in zeilen[i + 1:]:
                if folge.strip():
                    folge = folge.strip()
                    woerter = folge.lower().replace(",", " ").split()
                    if _NAMENSZEILE.match(folge) and not any(w in _KEIN_NAME for w in woerter) \
                            and not PLATZHALTER_MUSTER.search(folge):
                        kandidaten.append(folge)
                    break
    gesehen, eindeutig = set(), []
    for k in kandidaten:
        if k.lower() not in gesehen:
            gesehen.add(k.lower())
            eindeutig.append(k)
    return eindeutig


def _teile(name: str) -> list[str]:
    return [t for t in name.split() if len(t) >= 3 and t.lower() not in _KEIN_NAME]


def _ersetze_namen(text: str, kandidaten: list[str], tabelle: list, zuordnung: dict) -> str:
    """Drei Durchgänge: erst alle Namen registrieren (längste zuerst, damit
    'Weber' aus 'Karl Weber' denselben Platzhalter bekommt), dann volle Namen
    ersetzen (Groß-/Kleinschreibung egal), dann Namensteile (exakt)."""
    kandidaten = sorted(kandidaten, key=len, reverse=True)
    for name in kandidaten:
        platz = _platzhalter("NAME", name, tabelle, zuordnung)
        for teil in _teile(name):
            zuordnung.setdefault(("NAME", teil), platz)
    for name in kandidaten:
        platz = zuordnung[("NAME", name)]
        text = _ersetze(text, re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE),
                        "NAME", tabelle, zuordnung, fest=platz)
    teile = sorted({t for n in kandidaten for t in _teile(n)}, key=len, reverse=True)
    for teil in teile:
        text = _ersetze(text, re.compile(r"\b" + re.escape(teil) + r"\b"),
                        "NAME", tabelle, zuordnung, fest=zuordnung[("NAME", teil)])
    return text


def anonymisiere(text: str, absender_name: str | None = None) -> tuple[str, list[dict]]:
    """Liefert (pseudonymisierter Text, Platzhaltertabelle)."""
    tabelle: list[dict] = []
    zuordnung: dict = {}
    text = _ersetze(text, _EMAIL, "EMAIL", tabelle, zuordnung)
    text = _ersetze(text, _KENNZEICHEN, "KENNZEICHEN", tabelle, zuordnung)
    text = _ersetze(text, _TELEFON, "TELEFON", tabelle, zuordnung)
    text = _ersetze(text, _ADRESSE, "ADRESSE", tabelle, zuordnung)
    text = _ersetze(text, _ORT, "ORT", tabelle, zuordnung)
    text = _ersetze_namen(text, _namenskandidaten(text, absender_name), tabelle, zuordnung)
    return text, tabelle


def zuruecksetzen(obj, tabelle: list[dict]):
    """Ersetzt Platzhalter durch Originale; rekursiv über dict und list."""
    if isinstance(obj, str):
        for eintrag in tabelle:
            obj = obj.replace(eintrag["platzhalter"], eintrag["original"])
        return obj
    if isinstance(obj, dict):
        return {k: zuruecksetzen(v, tabelle) for k, v in obj.items()}
    if isinstance(obj, list):
        return [zuruecksetzen(v, tabelle) for v in obj]
    return obj
```

Hinweis zur Namensersetzung: `_ersetze_namen` registriert erst alle Namen und ihre Teile, dann ersetzt es mit `fest=` dem schon vergebenen Platzhalter. So bekommt „max muster" (klein) denselben Platzhalter wie „Max Muster" und erzeugt keinen zweiten Tabelleneintrag; `test_name_aus_absender_auch_einzeln_und_kleingeschrieben` sichert das.

- [ ] **Step 5: Tests laufen lassen**

Run: `python -m pytest tests/test_anonymisierung.py -q`
Expected: alle PASS. Falls ein Regex-Test scheitert: Regex anpassen, nicht den Test aufweichen. Erlaubte Ausnahme: Wenn `test_kennzeichen_varianten` an `AB CD 567` scheitert, weil `_TELEFON` vorher zugreift, Reihenfolge Kennzeichen vor Telefon prüfen (steht so in `anonymisiere`).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(anonymisierung): Platzhalter setzen und zuruecksetzen mit Tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Kalender

**Files:**
- Create: `app/kalender.py`, `data/kalender.json`
- Test: `tests/test_kalender.py`

**Interfaces:**
- Produces:
  - `lade_kalender(pfad: str | Path) -> dict`, `speichere_kalender(kalender: dict, pfad)`
  - `finde_termin(kalender: dict, extraktion: dict, heute: date) -> dict | None` – `{"datum": "YYYY-MM-DD", "halbtag": "vormittag"|"nachmittag", "hinweis": str}`; `None` wenn `zustaendigkeit == "verkauf"` oder kein Halbtag frei.
  - `belege(kalender: dict, datum: str, halbtag: str) -> bool` – erhöht `belegt`, False wenn voll/unbekannt.
  - `erzeuge_kalender(basisdatum: date, wochen: int = 3) -> dict` – Werktage, `kapazitaet` 4 je Halbtag, `belegt` 0.

- [ ] **Step 1: Failing Tests**

`tests/test_kalender.py`:
```python
from datetime import date
from app.kalender import erzeuge_kalender, finde_termin, belege

HEUTE = date(2026, 9, 14)


def _kal():
    kal = erzeuge_kalender(HEUTE, wochen=3)
    for tag in kal["tage"]:
        if tag["datum"] in ("2026-09-16", "2026-09-17"):
            for h in tag["halbtage"].values():
                h["belegt"] = h["kapazitaet"]
        if tag["datum"] == "2026-09-15":
            tag["halbtage"]["vormittag"]["belegt"] = tag["halbtage"]["vormittag"]["kapazitaet"]
    return kal


def _ex(**kw):
    basis = {"zustaendigkeit": "werkstatt", "dringlichkeit": "mittel",
             "wunschzeitraum": {"von": None, "bis": None, "tageszeit": "egal"}}
    basis.update(kw)
    return basis


def test_nur_werktage():
    kal = erzeuge_kalender(HEUTE, wochen=1)
    assert [t["datum"] for t in kal["tage"]] == ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
    assert kal["basisdatum"] == "2026-09-14"


def test_ohne_wunsch_ab_naechstem_werktag():
    t = finde_termin(_kal(), _ex(), HEUTE)
    assert t == {"datum": "2026-09-15", "halbtag": "nachmittag", "hinweis": ""}


def test_wunschzeitraum_und_tageszeit():
    t = finde_termin(_kal(), _ex(wunschzeitraum={"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "vormittag"}), HEUTE)
    assert t["datum"] == "2026-09-21" and t["halbtag"] == "vormittag" and t["hinweis"] == ""


def test_wunschzeitraum_ausgebucht_naechster_danach():
    t = finde_termin(_kal(), _ex(wunschzeitraum={"von": "2026-09-16", "bis": "2026-09-17", "tageszeit": "egal"}), HEUTE)
    assert t["datum"] == "2026-09-18"
    assert "außerhalb" in t["hinweis"]


def test_sicherheitsrelevant_zieht_vor():
    t = finde_termin(_kal(), _ex(dringlichkeit="sicherheitsrelevant",
                                 wunschzeitraum={"von": "2026-09-28", "bis": "2026-09-30", "tageszeit": "egal"}), HEUTE)
    assert t["datum"] == "2026-09-14"
    assert "vorgezogen" in t["hinweis"]


def test_verkauf_kein_termin():
    assert finde_termin(_kal(), _ex(zustaendigkeit="verkauf"), HEUTE) is None


def test_belegen():
    kal = _kal()
    assert belege(kal, "2026-09-18", "vormittag") is True
    assert kal["tage"][4]["halbtage"]["vormittag"]["belegt"] == 1
    assert belege(kal, "2026-09-16", "vormittag") is False
    assert belege(kal, "2099-01-01", "vormittag") is False
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest tests/test_kalender.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`app/kalender.py`:
```python
"""Kapazitätskalender: Werktage mit zwei Halbtagen, freien Halbtag finden, belegen.

Regeln (Spec): Verkauf -> kein Termin. Sicherheitsrelevant -> nächster freier
Halbtag ab heute, Hinweis "vorgezogen". Sonst erster freier Halbtag im
Wunschzeitraum passend zur Tageszeit; nichts frei -> erster freier Halbtag
nach dem Zeitraum mit Hinweis. Ohne Wunsch: ab heute + 1 Werktag.
Der Vorschlag reserviert nichts; erst `belege()` erhöht `belegt`.
"""
import json
from datetime import date, timedelta
from pathlib import Path

HALBTAGE = ("vormittag", "nachmittag")
KAPAZITAET = 4


def erzeuge_kalender(basisdatum: date, wochen: int = 3) -> dict:
    tage = []
    tag = basisdatum
    while tag < basisdatum + timedelta(weeks=wochen):
        if tag.weekday() < 5:
            tage.append({"datum": tag.isoformat(),
                         "halbtage": {h: {"kapazitaet": KAPAZITAET, "belegt": 0} for h in HALBTAGE}})
        tag += timedelta(days=1)
    return {"basisdatum": basisdatum.isoformat(), "tage": tage}


def lade_kalender(pfad) -> dict:
    return json.loads(Path(pfad).read_text(encoding="utf-8"))


def speichere_kalender(kalender: dict, pfad) -> None:
    Path(pfad).write_text(json.dumps(kalender, ensure_ascii=False, indent=2), encoding="utf-8")


def _frei(tag: dict, halbtag: str) -> bool:
    h = tag["halbtage"][halbtag]
    return h["belegt"] < h["kapazitaet"]


def _erster_freier(kalender: dict, von: date, bis: date | None, tageszeit: str) -> tuple[str, str] | None:
    halbtage = HALBTAGE if tageszeit not in HALBTAGE else (tageszeit,)
    for tag in kalender["tage"]:
        d = date.fromisoformat(tag["datum"])
        if d < von or (bis and d > bis):
            continue
        for h in halbtage:
            if _frei(tag, h):
                return tag["datum"], h
    return None


def _datum(wert) -> date | None:
    try:
        return date.fromisoformat(wert) if wert else None
    except ValueError:
        return None


def finde_termin(kalender: dict, extraktion: dict, heute: date) -> dict | None:
    if extraktion.get("zustaendigkeit") == "verkauf":
        return None
    wunsch = extraktion.get("wunschzeitraum") or {}
    tageszeit = wunsch.get("tageszeit") or "egal"

    if extraktion.get("dringlichkeit") == "sicherheitsrelevant":
        treffer = _erster_freier(kalender, heute, None, "egal")
        return {"datum": treffer[0], "halbtag": treffer[1],
                "hinweis": "Sicherheitsrelevant, Termin vorgezogen."} if treffer else None

    von, bis = _datum(wunsch.get("von")), _datum(wunsch.get("bis"))
    if von is None:
        von = heute + timedelta(days=1)
        while von.weekday() >= 5:
            von += timedelta(days=1)
    if von < heute:
        von = heute
    treffer = _erster_freier(kalender, von, bis, tageszeit)
    if treffer:
        return {"datum": treffer[0], "halbtag": treffer[1], "hinweis": ""}
    ab = (bis or von) + timedelta(days=1)
    treffer = _erster_freier(kalender, ab, None, tageszeit)
    if treffer:
        return {"datum": treffer[0], "halbtag": treffer[1],
                "hinweis": "Im Wunschzeitraum ist nichts frei, Vorschlag liegt außerhalb."}
    return None


def belege(kalender: dict, datum: str, halbtag: str) -> bool:
    for tag in kalender["tage"]:
        if tag["datum"] == datum and halbtag in tag["halbtage"]:
            if not _frei(tag, halbtag):
                return False
            tag["halbtage"][halbtag]["belegt"] += 1
            return True
    return False
```

`data/kalender.json` erzeugen (einmalig, per Python-Einzeiler, nicht als Skriptdatei):
```bash
python -c "
from datetime import date
from app.kalender import erzeuge_kalender, speichere_kalender
k = erzeuge_kalender(date(2026, 9, 14), wochen=3)
for t in k['tage']:
    if t['datum'] in ('2026-09-16', '2026-09-17'):
        for h in t['halbtage'].values(): h['belegt'] = h['kapazitaet']
    if t['datum'] == '2026-09-15':
        t['halbtage']['vormittag']['belegt'] = 4
speichere_kalender(k, 'data/kalender.json')
print(len(k['tage']), 'Tage')
"
```
Expected: `15 Tage`.

- [ ] **Step 4: Tests**

Run: `python -m pytest tests/test_kalender.py -q` → alle PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(kalender): Kapazitaetskalender mit Terminsuche und Belegung

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Modell-Client und Extraktion

**Files:**
- Create: `app/llm_client.py`, `app/extraktion.py`
- Test: `tests/test_extraktion.py`

**Interfaces:**
- Produces:
  - `llm_client.Konfig` (dataclass: `provider, base_url, model, api_key`), `lade_konfig() -> Konfig` (liest Umgebung, lädt vorher `.env` falls vorhanden, Defaults je Provider), `LLMClient(konfig).frage_json(system: str, user: str) -> str`, `FakeClient(antwort: str | dict)` mit derselben Methode und Attribut `aufrufe: list[str]` (jeder gesendete User-Text).
  - `extraktion.Extraktion` (Pydantic), `baue_prompt(heute: date) -> str` (System-Prompt), `parse_antwort(content: str) -> Extraktion` (wirft `ExtraktionsFehler`), `extrahiere(client, pseudonym_text: str, heute: date) -> Extraktion`.

- [ ] **Step 1: Failing Tests**

`tests/test_extraktion.py`:
```python
import json
import os
from datetime import date

import pytest

from app.extraktion import Extraktion, ExtraktionsFehler, baue_prompt, extrahiere, parse_antwort
from app.llm_client import FakeClient, lade_konfig

GUELTIG = {
    "kunde": {"anrede": "Herr", "name": "[NAME_1]"},
    "fahrzeug": {"marke": "Toyota", "modell": "Corolla", "baujahr": 2019, "kilometerstand": 85000},
    "kennzeichen": "[KENNZEICHEN_1]",
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Inspektion"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "vormittag"},
    "zustaendigkeit": "werkstatt",
    "unklarheiten": [],
}


def test_parse_gueltig():
    e = parse_antwort(json.dumps(GUELTIG))
    assert isinstance(e, Extraktion)
    assert e.anliegen[0].kategorie == "wartung"


def test_parse_mit_codeblock():
    e = parse_antwort("```json\n" + json.dumps(GUELTIG) + "\n```")
    assert e.kennzeichen == "[KENNZEICHEN_1]"


def test_parse_ungueltiges_json():
    with pytest.raises(ExtraktionsFehler):
        parse_antwort("das ist kein json")


def test_parse_falsche_kategorie():
    kaputt = dict(GUELTIG, anliegen=[{"kategorie": "motor", "beschreibung": "x"}])
    with pytest.raises(ExtraktionsFehler):
        parse_antwort(json.dumps(kaputt))


def test_parse_toleriert_fehlende_optionale_felder():
    knapp = {"kunde": {"anrede": None, "name": None}, "fahrzeug": {"marke": None, "modell": None},
             "kennzeichen": None, "anliegen": [], "dringlichkeit": "niedrig",
             "wunschzeitraum": {"von": None, "bis": None, "tageszeit": "egal"},
             "zustaendigkeit": "werkstatt", "unklarheiten": ["kein Anliegen erkennbar"]}
    e = parse_antwort(json.dumps(knapp))
    assert e.fahrzeug.baujahr is None


def test_prompt_enthaelt_datum_und_platzhalterregel():
    p = baue_prompt(date(2026, 9, 14))
    assert "2026-09-14" in p and "[NAME_1]" in p and "sicherheitsrelevant" in p


def test_extrahiere_sendet_nur_uebergebenen_text():
    fake = FakeClient(GUELTIG)
    e = extrahiere(fake, "Text mit [NAME_1]", date(2026, 9, 14))
    assert e.kunde.name == "[NAME_1]"
    assert fake.aufrufe == ["Text mit [NAME_1]"]


def test_konfig_defaults_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    k = lade_konfig(env_datei=None)
    assert k.base_url == "http://localhost:11434/v1"
    assert k.api_key == "ollama"


def test_konfig_defaults_langdock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "x")
    k = lade_konfig(env_datei=None)
    assert k.provider == "langdock" and "langdock.com" in k.base_url and k.model == "gpt-5.1"
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest tests/test_extraktion.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementierung Client**

`app/llm_client.py`:
```python
"""Ein OpenAI-kompatibler Client, Basis-URL je Anbieter (Langdock EU oder Ollama).

Konfiguration über Umgebungsvariablen LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL,
LLM_API_KEY; eine .env im Projektordner wird vorher eingelesen (ohne
Überschreiben gesetzter Variablen). FakeClient dient den Tests.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULTS = {
    "langdock": {"base_url": "https://api.langdock.com/openai/eu/v1", "model": "gpt-5.1"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b", "api_key": "ollama"},
}


@dataclass
class Konfig:
    provider: str
    base_url: str
    model: str
    api_key: str

    @property
    def schluessel_gesetzt(self) -> bool:
        return bool(self.api_key) and self.api_key != "ollama"


def _lies_env_datei(pfad: Path) -> None:
    if not pfad or not pfad.is_file():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        k, v = zeile.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def lade_konfig(env_datei: Path | str | None = Path(__file__).resolve().parent.parent / ".env") -> Konfig:
    if env_datei:
        _lies_env_datei(Path(env_datei))
    provider = os.getenv("LLM_PROVIDER", "langdock").lower()
    d = DEFAULTS.get(provider, DEFAULTS["langdock"])
    return Konfig(
        provider=provider,
        base_url=os.getenv("LLM_BASE_URL", d["base_url"]),
        model=os.getenv("LLM_MODEL", d["model"]),
        api_key=os.getenv("LLM_API_KEY", d.get("api_key", "")),
    )


class LLMClient:
    def __init__(self, konfig: Konfig):
        from openai import OpenAI  # Import hier, damit Tests ohne Netz kein SDK brauchen
        self.konfig = konfig
        self._client = OpenAI(api_key=konfig.api_key or "leer", base_url=konfig.base_url)

    def frage_json(self, system: str, user: str) -> str:
        nachrichten = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            antwort = self._client.chat.completions.create(
                model=self.konfig.model, messages=nachrichten, temperature=0,
                response_format={"type": "json_object"},
            )
        except Exception as e:  # Anbieter ohne response_format: ohne Zwang erneut
            if "response_format" not in str(e) and "json_object" not in str(e):
                raise
            antwort = self._client.chat.completions.create(
                model=self.konfig.model, messages=nachrichten, temperature=0,
            )
        return antwort.choices[0].message.content or ""


class FakeClient:
    """Liefert eine feste Antwort; merkt sich jeden gesendeten User-Text."""

    def __init__(self, antwort):
        self.antwort = json.dumps(antwort, ensure_ascii=False) if isinstance(antwort, dict) else antwort
        self.aufrufe: list[str] = []
        self.konfig = Konfig("fake", "", "fake", "")

    def frage_json(self, system: str, user: str) -> str:
        self.aufrufe.append(user)
        return self.antwort
```

- [ ] **Step 4: Implementierung Extraktion**

`app/extraktion.py`:
```python
"""Extraktion der Anfrage nach JSON: Schema (Pydantic), Prompt, Antwort parsen.

Das Modell sieht nur den pseudonymisierten Text; Platzhalter wie [NAME_1]
müssen wörtlich übernommen werden. Ungültige Antworten werfen
ExtraktionsFehler, nie einen rohen Absturz.
"""
import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, ValidationError

Kategorie = Literal["wartung", "reparatur", "reifen", "hu_au", "karosserie", "verkauf", "sonstiges"]


class Kunde(BaseModel):
    anrede: str | None = None
    name: str | None = None


class Fahrzeug(BaseModel):
    marke: str | None = None
    modell: str | None = None
    baujahr: int | None = None
    kilometerstand: int | None = None


class Anliegen(BaseModel):
    kategorie: Kategorie
    beschreibung: str


class Wunschzeitraum(BaseModel):
    von: str | None = None
    bis: str | None = None
    tageszeit: Literal["vormittag", "nachmittag", "egal"] = "egal"


class Extraktion(BaseModel):
    kunde: Kunde = Kunde()
    fahrzeug: Fahrzeug = Fahrzeug()
    kennzeichen: str | None = None
    anliegen: list[Anliegen] = []
    dringlichkeit: Literal["niedrig", "mittel", "hoch", "sicherheitsrelevant"] = "mittel"
    wunschzeitraum: Wunschzeitraum = Wunschzeitraum()
    zustaendigkeit: Literal["werkstatt", "verkauf"] = "werkstatt"
    unklarheiten: list[str] = []


class ExtraktionsFehler(Exception):
    pass


SCHEMA_TEXT = """{
  "kunde": {"anrede": "Herr|Frau|null", "name": "Platzhalter wie [NAME_1] oder null"},
  "fahrzeug": {"marke": "string|null", "modell": "string|null", "baujahr": "int|null", "kilometerstand": "int|null"},
  "kennzeichen": "Platzhalter wie [KENNZEICHEN_1] oder null",
  "anliegen": [{"kategorie": "wartung|reparatur|reifen|hu_au|karosserie|verkauf|sonstiges", "beschreibung": "kurz, deutsch"}],
  "dringlichkeit": "niedrig|mittel|hoch|sicherheitsrelevant",
  "wunschzeitraum": {"von": "YYYY-MM-DD|null", "bis": "YYYY-MM-DD|null", "tageszeit": "vormittag|nachmittag|egal"},
  "zustaendigkeit": "werkstatt|verkauf",
  "unklarheiten": ["string"]
}"""


def baue_prompt(heute: date) -> str:
    return (
        "Du bist die Serviceannahme eines Autohauses. Du bekommst eine Kunden-E-Mail, in der "
        "personenbezogene Daten durch Platzhalter ersetzt sind, z. B. [NAME_1], [KENNZEICHEN_1], "
        "[TELEFON_1]. Übernimm Platzhalter wörtlich, erfinde keine Werte dahinter.\n"
        f"Heute ist {heute.isoformat()} ({heute.strftime('%A')}). Relative Angaben wie "
        "'nächste Woche' oder 'Mittwoch' rechnest du auf Kalenderdaten um.\n"
        "Antworte ausschließlich mit einem JSON-Objekt nach diesem Schema:\n" + SCHEMA_TEXT + "\n"
        "Regeln: Jedes eigenständige Anliegen ist ein Listeneintrag. Bremsen, Lenkung, Reifen mit "
        "Druckverlust, Motorwarnleuchte rot oder Rauch sind 'sicherheitsrelevant'. Geht es um Kauf, "
        "Probefahrt, Leasing oder Angebot für ein Fahrzeug, ist zustaendigkeit 'verkauf'. "
        "Fehlt eine Information, die du für den Termin brauchst (Kennzeichen, konkretes Anliegen, "
        "Zeitraum), schreibe sie in unklarheiten. Keine Erklärungen außerhalb des JSON."
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
```

- [ ] **Step 5: Tests**

Run: `python -m pytest tests/test_extraktion.py -q` → alle PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(extraktion): Schema, Prompt und OpenAI-kompatibler Client mit Fake

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Antwortentwurf

**Files:**
- Create: `app/antwort.py`
- Test: `tests/test_antwort.py`

**Interfaces:**
- Produces: `baue_antwort(extraktion: dict, termin: dict | None, betreff: str) -> str` – `extraktion` ist das ZURÜCKERSETZTE dict (Originalnamen), `termin` wie aus `finde_termin`.
- Consumes: Kategorienamen aus Task 3, Terminform aus Task 2.

- [ ] **Step 1: Failing Tests**

`tests/test_antwort.py`:
```python
from app.antwort import baue_antwort

EX = {
    "kunde": {"anrede": "Frau", "name": "Sabine Krämer"},
    "fahrzeug": {"marke": "Toyota", "modell": "Corolla", "baujahr": None, "kilometerstand": None},
    "kennzeichen": "MKK-AB 1234",
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Inspektion"},
                 {"kategorie": "hu_au", "beschreibung": "HU/AU fällig"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "vormittag"},
    "zustaendigkeit": "werkstatt",
    "unklarheiten": [],
}


def test_entwurf_mit_termin():
    t = baue_antwort(EX, {"datum": "2026-09-21", "halbtag": "vormittag", "hinweis": ""}, "Inspektion")
    assert t.startswith("Sehr geehrte Frau Krämer,")
    assert "Inspektion" in t and "HU/AU fällig" in t
    assert "Montag, 21.09.2026" in t and "Vormittag" in t
    assert "MKK-AB 1234" in t
    assert "[" not in t
    assert t.rstrip().endswith("Ihr Serviceteam")


def test_entwurf_hinweis_und_unklarheit():
    ex = dict(EX, unklarheiten=["Kennzeichen fehlt"], kennzeichen=None)
    t = baue_antwort(ex, {"datum": "2026-09-18", "halbtag": "nachmittag",
                          "hinweis": "Im Wunschzeitraum ist nichts frei, Vorschlag liegt außerhalb."}, "x")
    assert "nichts frei" in t
    assert "Kennzeichen fehlt" in t


def test_entwurf_verkauf_weiterleitung():
    ex = dict(EX, zustaendigkeit="verkauf", anliegen=[{"kategorie": "verkauf", "beschreibung": "Probefahrt"}])
    t = baue_antwort(ex, None, "Probefahrt")
    assert "Verkauf" in t and "weitergeleitet" in t
    assert "Termin" not in t.split("weitergeleitet")[0]


def test_entwurf_ohne_namen_und_ohne_termin():
    ex = dict(EX, kunde={"anrede": None, "name": None})
    t = baue_antwort(ex, None, "x")
    assert t.startswith("Guten Tag,")
    assert "melden uns" in t
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest tests/test_antwort.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`app/antwort.py`:
```python
"""Antwortentwurf aus einer deutschen Vorlage. Kein Modell: der Text bleibt vorhersagbar."""
from datetime import date

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
KATEGORIE_TEXT = {
    "wartung": "Wartung", "reparatur": "Reparatur", "reifen": "Reifen", "hu_au": "HU/AU",
    "karosserie": "Karosserie", "verkauf": "Verkauf", "sonstiges": "Sonstiges",
}


def _anrede(kunde: dict) -> str:
    name = (kunde or {}).get("name")
    anrede = (kunde or {}).get("anrede")
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


def _fahrzeug_text(ex: dict) -> str:
    f = ex.get("fahrzeug") or {}
    teile = [f.get("marke"), f.get("modell")]
    text = " ".join(t for t in teile if t)
    if ex.get("kennzeichen"):
        text = f"{text} ({ex['kennzeichen']})" if text else ex["kennzeichen"]
    return text or "Ihr Fahrzeug"


def baue_antwort(ex: dict, termin: dict | None, betreff: str) -> str:
    zeilen = [_anrede(ex.get("kunde")), "", "vielen Dank für Ihre Anfrage."]
    if ex.get("zustaendigkeit") == "verkauf":
        zeilen += ["", "Ihr Anliegen betrifft unseren Verkauf. Ich habe Ihre Nachricht an die "
                   "Kolleginnen und Kollegen dort weitergeleitet; sie melden sich in Kürze bei Ihnen."]
    else:
        anliegen = ex.get("anliegen") or []
        if anliegen:
            zeilen += ["", f"Für {_fahrzeug_text(ex)} haben wir folgende Punkte notiert:"]
            zeilen += [f"- {KATEGORIE_TEXT.get(a['kategorie'], a['kategorie'])}: {a['beschreibung']}" for a in anliegen]
        if termin:
            halbtag = "Vormittag" if termin["halbtag"] == "vormittag" else "Nachmittag"
            zeilen += ["", f"Wir schlagen Ihnen einen Termin am {_datum_text(termin['datum'])} am {halbtag} vor."]
            if termin.get("hinweis"):
                zeilen.append(termin["hinweis"])
            zeilen.append("Bitte bestätigen Sie den Termin kurz per Antwort auf diese E-Mail.")
        else:
            zeilen += ["", "Wir melden uns mit einem Terminvorschlag, sobald die offenen Punkte geklärt sind."]
    unklar = ex.get("unklarheiten") or []
    if unklar:
        zeilen += ["", "Damit wir den Termin passend planen können, benötigen wir noch:"]
        zeilen += [f"- {u}" for u in unklar]
    zeilen += ["", "Mit freundlichen Grüßen", "Ihr Serviceteam"]
    return "\n".join(zeilen)
```

- [ ] **Step 4: Tests**

Run: `python -m pytest tests/test_antwort.py -q` → alle PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(antwort): Antwortentwurf aus Vorlage

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Testdaten, Speicher, Pipeline, CLI

**Files:**
- Create: `data/mails.json`, `app/speicher.py`, `app/pipeline.py`, `app/cli.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `anonymisiere`, `zuruecksetzen` (Task 1); `finde_termin`, `lade_kalender` (Task 2); `extrahiere`, `ExtraktionsFehler` (Task 3); `baue_antwort` (Task 4); `lade_konfig`, `LLMClient`, `FakeClient` (Task 3).
- Produces:
  - `speicher.lade_mails(pfad="data/mails.json") -> list[dict]`, `speicher.speichere_mails(mails, pfad)`, `speicher.lade_ergebnisse(pfad="data/ergebnisse.json") -> dict[str, dict]` (Schlüssel = mail_id, leeres dict wenn Datei fehlt), `speicher.speichere_ergebnisse(ergebnisse, pfad)`, `speicher.DATEN = Path("data")`.
  - `pipeline.verarbeite(mail: dict, client, kalender: dict, heute: date) -> dict` – Ergebnisobjekt laut Spec.

Mail-Objekt: `{"id": "m01", "absender_name": str, "absender_email": str, "betreff": str, "empfangen": "2026-09-11T08:12:00", "text": str}`.

- [ ] **Step 1: Testdaten schreiben**

`data/mails.json` – genau diese 15 Mails (alle Personen, Nummern, Kennzeichen erfunden):

```json
[
  {"id": "m01", "absender_name": "Katrin Vollmer", "absender_email": "k.vollmer@example.net", "betreff": "Inspektion Corolla", "empfangen": "2026-09-11T08:12:00",
   "text": "Guten Tag,\n\nmein Toyota Corolla (MKK-KV 2187) ist für die jährliche Inspektion fällig. Nächste Woche vormittags würde mir gut passen, am liebsten Montag oder Dienstag.\n\nViele Grüße\nKatrin Vollmer\n0176 4471 9920"},
  {"id": "m02", "absender_name": "Thomas Reinfeld", "absender_email": "t.reinfeld@example.com", "betreff": "Bremsen quietschen stark", "empfangen": "2026-09-11T09:40:00",
   "text": "Hallo,\n\nseit gestern quietschen die Bremsen an meinem Lexus NX (GN-TR 811) bei jedem Bremsen laut, und das Bremspedal fühlt sich weicher an als sonst. Ich fahre das Auto so ungern weiter. Können Sie sich das so schnell wie möglich ansehen?\n\nDanke und Gruß\nThomas Reinfeld"},
  {"id": "m03", "absender_name": "Heinz Gerlach", "absender_email": "gerlach.heinz@example.org", "betreff": "Mein Bus macht Geräusche", "empfangen": "2026-09-11T11:05:00",
   "text": "Ei gude,\n\nmei T6 macht seit e paar Daach so e komisch Geräusch vorne links, so e Klappern wenn isch über die Bordsteinkant fahr. Is nix Wildes, aber es nervt. Kennzeiche is HU-HG 45. Wann kann isch mal vorbeikomme? Am beste Nachmittags, morgens bin isch aufm Bau.\n\nGruß\nHeinz"},
  {"id": "m04", "absender_name": "Melanie Osterhaus", "absender_email": "melanie.osterhaus@example.net", "betreff": "Winterreifen", "empfangen": "2026-09-11T13:30:00",
   "text": "Hallo liebes Werkstatt-Team,\n\nich möchte bei meinem Toyota Yaris die Winterreifen aufziehen lassen, die Reifen liegen bei Ihnen im Einlagerungsservice. Gerne Ende September oder Anfang Oktober, Tageszeit ist mir egal.\n\nLiebe Grüße\nMelanie Osterhaus"},
  {"id": "m05", "absender_name": "Jürgen Bastian", "absender_email": "jb@example-bau.de", "betreff": "Crafter: Ölwechsel, TÜV und Klima", "empfangen": "2026-09-12T07:55:00",
   "text": "Sehr geehrte Damen und Herren,\n\nunser VW Crafter, Baujahr 2020, Kennzeichen MKK-JB 3300, hat jetzt 118.000 km drauf. Bitte folgende Punkte erledigen:\n1. Ölwechsel mit Filter\n2. HU/AU ist im Oktober fällig, bitte gleich mitmachen\n3. Die Klimaanlage kühlt kaum noch, bitte prüfen und ggf. befüllen\n\nDer Wagen kann in der Woche vom 21.09. jederzeit kommen.\n\nMit freundlichen Grüßen\nJürgen Bastian\nBastian Bau GmbH\nIndustriestraße 14\n63607 Wächtersbach\nTel. 06053 / 90 44 12"},
  {"id": "m06", "absender_name": "Nadine Kessler", "absender_email": "nadine.kessler@example.com", "betreff": "Probefahrt bZ4X", "empfangen": "2026-09-12T10:20:00",
   "text": "Hallo,\n\nich interessiere mich für den Toyota bZ4X und würde gerne eine Probefahrt machen. Außerdem hätte ich gern ein Leasingangebot für 36 Monate, ca. 15.000 km im Jahr. Mein aktuelles Auto (AB-NK 77) würde ich eventuell in Zahlung geben.\n\nBeste Grüße\nNadine Kessler\n0151 22 33 44 55"},
  {"id": "m07", "absender_name": "Ralf Steinbach", "absender_email": "r.steinbach@example.org", "betreff": "Termin Mittwoch oder Donnerstag", "empfangen": "2026-09-12T12:00:00",
   "text": "Guten Tag,\n\nich brauche für meinen Lexus ES (F-RS 1290) einen Termin für den Wechsel der Scheibenwischer und einen Check der Standheizung, bevor es kalt wird. Ich kann nur am Mittwoch 16.09. oder Donnerstag 17.09., beides ginge vormittags oder nachmittags.\n\nMfG\nRalf Steinbach"},
  {"id": "m08", "absender_name": "M. Schulz", "absender_email": "m.schulz@example.net", "betreff": "Inspektion", "empfangen": "2026-09-12T14:45:00",
   "text": "Termin für Inspektion? Toyota Aygo, HU-MS 77. Danke, M. Schulz"},
  {"id": "m09", "absender_name": "Andrea Wittmann", "absender_email": "a.wittmann@example-elektro.de", "betreff": "Caddy Flotte Wartung", "empfangen": "2026-09-13T08:05:00",
   "text": "Sehr geehrtes Serviceteam,\n\nfür unsere zwei VW Caddy (MKK-EW 501 und MKK-EW 502) steht die Wartung an. Beide Fahrzeuge sollten möglichst am selben Tag kommen, damit unsere Monteure nur einmal ausfallen. Bevorzugt in der Woche vom 28.09., vormittags.\n\nMit freundlichen Grüßen\nAndrea Wittmann\nElektro Wittmann GmbH\nAm Bahndamm 7\n63571 Gelnhausen\nTelefon 06051 / 88 17 20\nMobil 0171 6 55 43 21"},
  {"id": "m10", "absender_name": "Daniel Price", "absender_email": "daniel.price@example.com", "betreff": "Appointment RAV4", "empfangen": "2026-09-13T09:30:00",
   "text": "Hello,\n\nI need an appointment for my Toyota RAV4, license plate F-DP 2020. The tyre pressure warning light comes on every few days and the rear left tyre seems to lose air. I work from home, so any day next week is fine.\n\nBest regards\nDaniel Price"},
  {"id": "m11", "absender_name": "Sandra Möller", "absender_email": "sandra.moeller@example.org", "betreff": "Große Inspektion Hilux", "empfangen": "2026-09-13T10:10:00",
   "text": "Hallo Herr Braun,\n\nwie besprochen möchte ich für unseren Toyota Hilux, Baujahr 2019, jetzt 85.000 km, die große Inspektion machen lassen. Kennzeichen AB-SM 1919. Ich bringe ihn am liebsten Dienstag oder Mittwoch nächste Woche früh vorbei.\n\nViele Grüße\nSandra Möller"},
  {"id": "m12", "absender_name": "Peter Krämer", "absender_email": "p.kraemer@example.net", "betreff": "Beule in der Tür", "empfangen": "2026-09-13T11:25:00",
   "text": "Hallo,\n\nmeine Frau Sabine Krämer hat gestern beim Einparken die Fahrertür unseres Lexus UX an einem Poller beschädigt (AB-PK 404). Eine deutliche Beule, Lack ist ab. Wir hätten gern einen Kostenvoranschlag. Sie kann den Wagen jederzeit vorbeibringen, tagsüber ist egal.\n\nGruß\nPeter Krämer\nRosenweg 3\n63739 Aschaffenburg\n06021 / 45 67 89"},
  {"id": "m13", "absender_name": "Markus Lindner", "absender_email": "m.lindner@example.com", "betreff": "Motorleuchte rot!", "empfangen": "2026-09-13T13:00:00",
   "text": "Hallo,\n\nbei meinem VW Amarok (MKK-ML 66) leuchtet seit heute Morgen die Motorkontrollleuchte ROT und der Motor ruckelt im Leerlauf. Ich habe ihn stehen lassen. Was soll ich tun, abschleppen lassen? Brauche dringend einen Termin.\n\nMarkus Lindner\n0160 98 76 54 32"},
  {"id": "m14", "absender_name": "Ingrid Sauer", "absender_email": "ingrid.sauer@example.org", "betreff": "Frage", "empfangen": "2026-09-13T15:40:00",
   "text": "Hallo,\n\nbei meinem Auto leuchtet irgendwas gelb im Tacho, so ein Symbol. Mein Mann meint, das sei nicht schlimm, aber ich hätte gern, dass mal jemand draufschaut. Irgendwann im Oktober wäre gut. Sie können mich anrufen: 06181 / 23 45 67.\n\nIngrid Sauer"},
  {"id": "m15", "absender_name": "Stefan Roth", "absender_email": "stefan.roth@example.net", "betreff": "Rückruf Airbag?", "empfangen": "2026-09-13T16:15:00",
   "text": "Guten Tag Herr Weber,\n\nich habe gelesen, dass es für den Toyota Proace einen Rückruf wegen der Airbags geben soll. Ist mein Fahrzeug (GN-SR 2222, Baujahr 2021) betroffen? Falls ja, würde ich den Termin gern mit dem fälligen Ölwechsel verbinden. Ich bin flexibel, außer Freitag.\n\nSchöne Grüße\nStefan Roth\nstefan.roth@example.net"}
]
```

- [ ] **Step 2: Failing Tests**

`tests/test_pipeline.py`:
```python
import json
from datetime import date

from app.kalender import lade_kalender
from app.llm_client import FakeClient
from app.pipeline import verarbeite
from app.speicher import lade_mails

HEUTE = date(2026, 9, 14)
ANTWORT = {
    "kunde": {"anrede": "Frau", "name": "[NAME_1]"},
    "fahrzeug": {"marke": "Toyota", "modell": "Corolla", "baujahr": None, "kilometerstand": None},
    "kennzeichen": "[KENNZEICHEN_1]",
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Inspektion"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-22", "tageszeit": "vormittag"},
    "zustaendigkeit": "werkstatt",
    "unklarheiten": [],
}


def test_alle_mails_laden():
    mails = lade_mails()
    assert len(mails) == 15
    assert {m["id"] for m in mails} == {f"m{i:02d}" for i in range(1, 16)}


def test_modell_sieht_keine_originale():
    mails = lade_mails()
    kal = lade_kalender("data/kalender.json")
    for mail in mails:
        fake = FakeClient(ANTWORT)
        erg = verarbeite(mail, fake, kal, HEUTE)
        gesendet = fake.aufrufe[0]
        assert gesendet == erg["pseudonym_text"]
        assert mail["absender_email"] not in gesendet
        for eintrag in erg["platzhalter"]:
            assert eintrag["original"] not in gesendet, (mail["id"], eintrag)
        nachname = mail["absender_name"].split()[-1]
        assert nachname not in gesendet, mail["id"]


def test_ergebnis_felder_und_rueckersetzung():
    mail = lade_mails()[0]
    erg = verarbeite(mail, FakeClient(ANTWORT), lade_kalender("data/kalender.json"), HEUTE)
    assert erg["mail_id"] == "m01"
    assert erg["status"] == "offen"
    assert erg["extraktion"]["kunde"]["name"] == "Katrin Vollmer"
    assert erg["extraktion"]["kennzeichen"] == "MKK-KV 2187"
    assert erg["termin"] == {"datum": "2026-09-21", "halbtag": "vormittag", "hinweis": ""}
    assert "Katrin Vollmer" not in erg["pseudonym_text"]
    assert "[" not in erg["antwort_entwurf"]
    assert erg["anbieter"] == "fake" and erg["dauer_ms"] >= 0 and erg["zeitpunkt"]
    json.dumps(erg)  # muss serialisierbar sein


def test_ungueltige_modellantwort_wird_pruefung_noetig():
    mail = lade_mails()[0]
    erg = verarbeite(mail, FakeClient("kein json"), lade_kalender("data/kalender.json"), HEUTE)
    assert erg["status"] == "pruefung_noetig"
    assert erg["extraktion"] is None and "JSON" in erg["extraktion_fehler"]
    assert erg["termin"] is None
    assert "Katrin Vollmer" not in erg["pseudonym_text"]
```

- [ ] **Step 3: Fehlschlag prüfen**

Run: `python -m pytest tests/test_pipeline.py -q` → ModuleNotFoundError.

- [ ] **Step 4: Implementierung Speicher**

`app/speicher.py`:
```python
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
```

- [ ] **Step 5: Implementierung Pipeline**

`app/pipeline.py`:
```python
"""Die vier Schritte je Mail: pseudonymisieren, extrahieren, Termin suchen, Entwurf bauen.

Das Modell bekommt ausschließlich `pseudonym_text`. Fehler der Extraktion
führen zu Status `pruefung_noetig`, nie zu einem Absturz.
"""
import time
from datetime import date, datetime

from app.anonymisierung import anonymisiere, zuruecksetzen
from app.antwort import baue_antwort
from app.extraktion import ExtraktionsFehler, extrahiere
from app.kalender import finde_termin


def verarbeite(mail: dict, client, kalender: dict, heute: date) -> dict:
    start = time.perf_counter()
    pseudonym_text, tabelle = anonymisiere(mail["text"], mail.get("absender_name"))
    ergebnis = {
        "mail_id": mail["id"], "roh_text": mail["text"], "pseudonym_text": pseudonym_text,
        "platzhalter": tabelle, "extraktion": None, "extraktion_fehler": None,
        "termin": None, "antwort_entwurf": "", "status": "offen",
        "anbieter": client.konfig.provider, "modell": client.konfig.model,
        "dauer_ms": 0, "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        extraktion = extrahiere(client, pseudonym_text, heute).model_dump()
    except ExtraktionsFehler as e:
        ergebnis["extraktion_fehler"] = str(e)
        ergebnis["status"] = "pruefung_noetig"
    except Exception as e:  # Netz, Anbieter, Schlüssel
        ergebnis["extraktion_fehler"] = f"Modellaufruf fehlgeschlagen: {type(e).__name__}: {e}"
        ergebnis["status"] = "pruefung_noetig"
    else:
        ergebnis["termin"] = finde_termin(kalender, extraktion, heute)
        ergebnis["extraktion"] = zuruecksetzen(extraktion, tabelle)
        ergebnis["antwort_entwurf"] = baue_antwort(ergebnis["extraktion"], ergebnis["termin"], mail.get("betreff", ""))
    ergebnis["dauer_ms"] = int((time.perf_counter() - start) * 1000)
    return ergebnis
```

- [ ] **Step 6: Implementierung CLI**

`app/cli.py`:
```python
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
```

- [ ] **Step 7: Tests**

Run: `python -m pytest -q` → alle Tests aller Tasks PASS. Falls `test_modell_sieht_keine_originale` an einer Mail scheitert: Ausgabe ansehen, es ist ein Regex-Loch in Task 1 (z. B. Telefonformat `06053 / 90 44 12`). Regex in `app/anonymisierung.py` schließen und einen Fall zu `tests/test_anonymisierung.py` hinzufügen. Testdaten NICHT anpassen, um den Test grün zu bekommen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(pipeline): Testmails, Speicher, Pipeline und CLI

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Echtlauf gegen Langdock

**Files:**
- Create: `tests/test_echtlauf.py`
- Create (durch Lauf): `data/ergebnisse.json`, `docs/data/mails.json`, `docs/data/ergebnisse.json`

**Interfaces:** Consumes CLI aus Task 5.

- [ ] **Step 1: Echtlauf-Test**

`tests/test_echtlauf.py`:
```python
"""Läuft nur mit gesetztem Schlüssel. Ein Aufruf, eine Mail."""
import os
from datetime import date

import pytest

from app.kalender import lade_kalender
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite
from app.speicher import lade_mails

pytestmark = pytest.mark.skipif(not os.getenv("LLM_API_KEY"), reason="LLM_API_KEY nicht gesetzt")


def test_echtlauf_eine_mail():
    client = LLMClient(lade_konfig())
    mail = [m for m in lade_mails() if m["id"] == "m05"][0]
    erg = verarbeite(mail, client, lade_kalender("data/kalender.json"), date(2026, 9, 14))
    assert erg["status"] == "offen", erg["extraktion_fehler"]
    assert len(erg["extraktion"]["anliegen"]) >= 3
    assert erg["extraktion"]["kennzeichen"] == "MKK-JB 3300"
    assert erg["extraktion"]["fahrzeug"]["kilometerstand"] == 118000
```

- [ ] **Step 2: Schlüssel bereitstellen (nur in der Shell, nie in eine Datei)**

Bash:
```bash
export LLM_API_KEY=...   # aus der lokalen Umgebung, nie in eine Datei
echo ${#LLM_API_KEY}   # nur die Länge ausgeben, nie den Wert
```
Expected: eine Zahl > 20.

- [ ] **Step 3: Echtlauf-Test**

Run: `python -m pytest tests/test_echtlauf.py -q -s`
Expected: PASS. Bei Schemafehler: Ausgabe von `extraktion_fehler` lesen; wenn das Modell ein Feld anders benennt, den Prompt in `app/extraktion.py` präzisieren (Schema-Text), NICHT das Schema aufweichen.

- [ ] **Step 4: Alle 15 Mails verarbeiten**

Run: `python -m app.cli --neu --pages`
Expected: 15 Zeilen, jede mit Status `offen` (Ausnahme erlaubt: `pruefung_noetig` bei m14, wenn das Modell dort kein Anliegen findet – dann ist das die gewollte Demonstration des Fehlerpfads). Danach existieren `data/ergebnisse.json` und `docs/data/*.json`.

Sichtprüfung (Bash):
```bash
python -c "
import json; e=json.load(open('data/ergebnisse.json',encoding='utf-8'))
for k,v in e.items():
    x=v['extraktion'] or {}
    print(k, v['status'], x.get('zustaendigkeit'), x.get('dringlichkeit'), [a['kategorie'] for a in x.get('anliegen',[])], v['termin'] and v['termin']['datum'], x.get('unklarheiten'))
"
```
Erwartung laut Testdaten: m02 und m13 `sicherheitsrelevant` mit Termin 2026-09-14; m06 `verkauf` ohne Termin; m07 Termin 2026-09-18 mit Hinweis; m04 ohne Kennzeichen → Unklarheit; m05 drei Anliegen; m10 (englisch) Reifen, vermutlich sicherheitsrelevant. Abweichungen notieren, nicht korrigieren – sie sind Gesprächsstoff.

- [ ] **Step 5: Prüfen, dass kein Original im gesendeten Text steht**

```bash
python -c "
import json; e=json.load(open('data/ergebnisse.json',encoding='utf-8')); m={x['id']:x for x in json.load(open('data/mails.json',encoding='utf-8'))}
schlecht=[(k,p['original']) for k,v in e.items() for p in v['platzhalter'] if p['original'] in v['pseudonym_text']]
schlecht+=[(k,m[k]['absender_name'].split()[-1]) for k,v in e.items() if m[k]['absender_name'].split()[-1] in v['pseudonym_text']]
print('Lecks:', schlecht)
"
```
Expected: `Lecks: []`.

- [ ] **Step 6: Commit** (Ergebnisse gehören ins Repo, sie sind die Datenbasis der Browser-Demo)

```bash
git add -A
git commit -m "feat: Echtlauf gegen Langdock, Ergebnisse fuer die Browser-Demo

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: FastAPI-Server

**Files:**
- Create: `app/main.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: Task 5 (`speicher`, `pipeline`), Task 2 (`kalender`), Task 3 (`lade_konfig`, `LLMClient`).
- Produces: Routen laut Spec. `app.main.erzeuge_app(client_factory=None) -> FastAPI`; `client_factory()` liefert einen Client (Tests geben einen FakeClient hinein). Modulvariable `app = erzeuge_app()`.

- [ ] **Step 1: Failing Tests**

`tests/test_main.py`:
```python
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import speicher
from app.llm_client import FakeClient
from app.main import erzeuge_app

ANTWORT = {
    "kunde": {"anrede": "Frau", "name": "[NAME_1]"},
    "fahrzeug": {"marke": "Toyota", "modell": "Corolla", "baujahr": None, "kilometerstand": None},
    "kennzeichen": "[KENNZEICHEN_1]",
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Inspektion"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-22", "tageszeit": "vormittag"},
    "zustaendigkeit": "werkstatt",
    "unklarheiten": [],
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    daten = tmp_path / "data"
    daten.mkdir()
    shutil.copyfile("data/mails.json", daten / "mails.json")
    shutil.copyfile("data/kalender.json", daten / "kalender.json")
    monkeypatch.setattr(speicher, "DATEN", daten)
    app = erzeuge_app(client_factory=lambda: FakeClient(ANTWORT))
    return TestClient(app)


def test_startseite_und_status(client):
    assert client.get("/").status_code == 200
    s = client.get("/api/status").json()
    assert s["anbieter"] == "fake" and s["heute"] == "2026-09-14"


def test_mails_liste_und_detail(client):
    liste = client.get("/api/mails").json()
    assert len(liste) == 15 and liste[0]["status"] == "unverarbeitet"
    d = client.get("/api/mails/m01").json()
    assert d["mail"]["id"] == "m01" and d["ergebnis"] is None
    assert client.get("/api/mails/gibtsnicht").status_code == 404


def test_verarbeiten_und_freigeben(client):
    r = client.post("/api/mails/m01/verarbeiten").json()
    assert r["status"] == "offen" and r["extraktion"]["kunde"]["name"] == "Katrin Vollmer"
    assert client.get("/api/mails").json()[0]["status"] == "offen"
    r = client.post("/api/mails/m01/status", json={"status": "freigegeben", "antwort_entwurf": "Geändert"}).json()
    assert r["status"] == "freigegeben" and r["antwort_entwurf"] == "Geändert"
    kal = json.loads((speicher.DATEN / "kalender.json").read_text(encoding="utf-8"))
    tag = [t for t in kal["tage"] if t["datum"] == "2026-09-21"][0]
    assert tag["halbtage"]["vormittag"]["belegt"] == 1
    assert client.post("/api/mails/m01/status", json={"status": "kaputt"}).status_code == 422


def test_neue_mail_anlegen(client):
    r = client.post("/api/mails", json={"absender_name": "Test Person", "absender_email": "t@example.org",
                                        "betreff": "Test", "text": "Hallo, Test Person hier."}).json()
    assert r["id"] == "m16"
    assert len(client.get("/api/mails").json()) == 16
    e = client.post("/api/mails/m16/verarbeiten").json()
    assert "Test Person" not in e["pseudonym_text"]
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest tests/test_main.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implementierung**

`app/main.py`:
```python
"""FastAPI-Server der Demo. Start: uvicorn app.main:app --reload --port 8040"""
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import speicher
from app.kalender import belege, lade_kalender, speichere_kalender
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite

DOCS = Path(__file__).resolve().parent.parent / "docs"


class NeueMail(BaseModel):
    absender_name: str
    absender_email: str = ""
    betreff: str = ""
    text: str


class StatusAenderung(BaseModel):
    status: Literal["offen", "freigegeben", "abgelehnt"]
    antwort_entwurf: str | None = None


def _kalender_pfad() -> Path:
    return speicher.DATEN / "kalender.json"


def _heute() -> date:
    return date.fromisoformat(lade_kalender(_kalender_pfad())["basisdatum"])


def _mail(mail_id: str) -> dict:
    for m in speicher.lade_mails():
        if m["id"] == mail_id:
            return m
    raise HTTPException(404, f"Mail {mail_id} unbekannt")


def erzeuge_app(client_factory=None) -> FastAPI:
    app = FastAPI(title="Werkstatt-Terminassistent")
    konfig = lade_konfig()
    factory = client_factory or (lambda: LLMClient(konfig))

    @app.get("/")
    def start():
        return FileResponse(DOCS / "index.html")

    @app.get("/api/status")
    def status():
        client = factory()
        return {"anbieter": client.konfig.provider, "modell": client.konfig.model,
                "schluessel_gesetzt": client.konfig.schluessel_gesetzt or client.konfig.provider in ("ollama", "fake"),
                "heute": _heute().isoformat(), "modus": "server"}

    @app.get("/api/mails")
    def mails():
        ergebnisse = speicher.lade_ergebnisse()
        return [{"id": m["id"], "absender_name": m["absender_name"], "betreff": m["betreff"],
                 "empfangen": m["empfangen"],
                 "status": ergebnisse.get(m["id"], {}).get("status", "unverarbeitet")}
                for m in speicher.lade_mails()]

    @app.get("/api/mails/{mail_id}")
    def mail_detail(mail_id: str):
        return {"mail": _mail(mail_id), "ergebnis": speicher.lade_ergebnisse().get(mail_id)}

    @app.post("/api/mails/{mail_id}/verarbeiten")
    def verarbeiten(mail_id: str):
        mail = _mail(mail_id)
        ergebnis = verarbeite(mail, factory(), lade_kalender(_kalender_pfad()), _heute())
        ergebnisse = speicher.lade_ergebnisse()
        ergebnisse[mail_id] = ergebnis
        speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    @app.post("/api/mails")
    def neue_mail(neu: NeueMail):
        mails = speicher.lade_mails()
        nr = max((int(m["id"][1:]) for m in mails), default=0) + 1
        mail = {"id": f"m{nr:02d}", **neu.model_dump(),
                "empfangen": datetime.now().isoformat(timespec="seconds")}
        mails.append(mail)
        speicher.speichere_mails(mails)
        return mail

    @app.post("/api/mails/{mail_id}/status")
    def status_setzen(mail_id: str, aenderung: StatusAenderung):
        _mail(mail_id)
        ergebnisse = speicher.lade_ergebnisse()
        ergebnis = ergebnisse.get(mail_id)
        if not ergebnis:
            raise HTTPException(409, "Mail ist noch nicht verarbeitet")
        if aenderung.antwort_entwurf is not None:
            ergebnis["antwort_entwurf"] = aenderung.antwort_entwurf
        if aenderung.status == "freigegeben" and ergebnis.get("termin") and ergebnis["status"] != "freigegeben":
            kalender = lade_kalender(_kalender_pfad())
            if belege(kalender, ergebnis["termin"]["datum"], ergebnis["termin"]["halbtag"]):
                speichere_kalender(kalender, _kalender_pfad())
        ergebnis["status"] = aenderung.status
        speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    return app


app = erzeuge_app()
```

Damit `GET /` in den Tests 200 liefert, muss `docs/index.html` existieren. Für diesen Task eine minimale Datei anlegen (wird in Task 8 ersetzt):
```html
<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Werkstatt-Terminassistent</title></head><body>Platzhalter, Oberfläche folgt.</body></html>
```

- [ ] **Step 4: Tests**

Run: `python -m pytest -q` → alle PASS (Echtlauf wird ohne Schlüssel übersprungen).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(api): FastAPI-Routen fuer Mails, Verarbeitung, Freigabe

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Oberfläche

**Files:**
- Replace: `docs/index.html`

**Interfaces:** Consumes API aus Task 7; statischer Modus liest `data/mails.json` und `data/ergebnisse.json` relativ zur HTML-Datei (also `docs/data/`).

- [ ] **Step 1: Seite schreiben**

Anforderungen (Spec „Oberfläche"), alles in EINER Datei ohne externe Abhängigkeiten, CSS eingebettet, Vanilla JS:

1. Kopfzeile: Titel „Werkstatt-Terminassistent – Demo", rechts Anbieter/Modell aus `/api/status` oder Badge „statischer Modus (GitHub Pages): vorberechnete Ergebnisse, keine Modellaufrufe".
2. Drei Spalten (CSS Grid `260px 1fr 380px`, unter 1000 px Breite untereinander).
3. Links: Liste aller Mails (Absender, Betreff, Status-Badge mit Farbe: unverarbeitet grau, offen blau, pruefung_noetig orange, freigegeben grün, abgelehnt rot). Oben Knopf „Alle verarbeiten" (Server-Modus: ruft `verarbeiten` nacheinander für alle; statisch: deaktiviert) und Knopf „Neue Mail" (öffnet ein Formular mit Absender, Betreff, Text → `POST /api/mails`, danach direkt verarbeiten; statisch: Hinweis).
4. Mitte oben, zwei gleich breite Felder nebeneinander mit Überschriften **„So sieht es der Mitarbeiter"** (roh_text) und **„Das bekam das Modell"** (pseudonym_text). Im linken Feld werden die Originalwerte aus `platzhalter` gelb hinterlegt, im rechten die Platzhalter `[TYP_n]` blau hinterlegt (`<mark>`). Darunter die Platzhaltertabelle (Typ, Platzhalter, Original). Darunter die extrahierten Felder als Tabelle: Kunde, Fahrzeug, Kennzeichen, Anliegen (Liste mit Kategorie), Dringlichkeit, Wunschzeitraum, Zuständigkeit, Unklarheiten. Bei `pruefung_noetig` ein roter Kasten mit `extraktion_fehler`.
5. Rechts: Terminvorschlag (Datum, Halbtag, Hinweis) oder „kein Termin (Verkauf)" bzw. „kein Termin", darunter `<textarea>` mit dem Antwortentwurf (editierbar), Knöpfe „Freigeben", „Ablehnen", „Neu verarbeiten". Fußnote: „Dauer {dauer_ms} ms, Anbieter {anbieter}/{modell}, {zeitpunkt}".
6. Statischer Modus: `fetch('/api/status')` schlägt fehl (kein Server) → Daten aus `data/mails.json` und `data/ergebnisse.json` laden; Status kommt aus den Ergebnissen; alle Schreibknöpfe zeigen `alert('Statischer Modus: Änderungen werden nicht gespeichert.')`, Textarea bleibt editierbar.
7. Escaping: alle Texte über eine `esc()`-Funktion (`replace(/[&<>"]/g, ...)`), Markierungen erst nach dem Escaping über Ersetzung der escapten Werte einsetzen.
8. Nüchternes Layout: Systemschrift, Weiß/Hellgrau, eine Akzentfarbe (#0b4f9c), keine Verläufe, keine Icons.

Prüfen im Server-Modus:
```bash
python -m uvicorn app.main:app --port 8040 &
sleep 2
curl -s http://localhost:8040/ | head -c 300
curl -s http://localhost:8040/api/status
kill %1
```
Dann manuell im Browser `http://localhost:8040/` öffnen: Mail m12 anklicken, prüfen, dass links „Sabine Krämer", „Rosenweg 3", „63739 Aschaffenburg", „06021 / 45 67 89", „AB-PK 404" gelb und rechts die Platzhalter blau markiert sind; Antwortentwurf enthält Originalnamen.

Prüfen im statischen Modus: `python -m http.server 8041 -d docs` und `http://localhost:8041/` öffnen → Badge „statischer Modus", alle 15 Mails mit Ergebnissen sichtbar, „Freigeben" zeigt den Hinweis.

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "feat(ui): Oberflaeche mit Anonymisierungs-Vergleich, Server- und statischer Modus

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: README, Startskripte, Gesprächsleitfaden

**Files:**
- Create: `README.md`, `run.bat`, `run.sh`, `docs/GESPRAECH.md`

- [ ] **Step 1: Startskripte**

`run.bat`:
```bat
@echo off
cd /d %~dp0
if not exist .env (echo .env fehlt - bitte .env.example kopieren und LLM_API_KEY setzen & exit /b 1)
python -m pip install -r requirements.txt -q
python -m uvicorn app.main:app --port 8040
```

`run.sh`:
```bash
#!/usr/bin/env sh
cd "$(dirname "$0")"
[ -f .env ] || { echo ".env fehlt - bitte .env.example kopieren und LLM_API_KEY setzen"; exit 1; }
python -m pip install -r requirements.txt -q
python -m uvicorn app.main:app --port 8040
```

- [ ] **Step 2: README**

`README.md` mit genau diesen Abschnitten (Inhalt ausformulieren, deutsch, sachlich, erste Person):

1. **Was das ist** – zwei Sätze; Hinweis „Eigenprojekt, Demo mit erfundenen Testdaten, entstanden für eine Bewerbung".
2. **Demo im Browser ohne Installation** – Link `https://GITHUB-NUTZER.github.io/werkstatt-terminassistent/` (Platzhalter, wird vom Autor ersetzt), Erklärung „statischer Modus: vorberechnete Ergebnisse, keine Modellaufrufe".
3. **Das Kernstück: Anonymisierung vor dem Modellaufruf** – was ersetzt wird (Tabelle Typ/Beispiel/Platzhalter), wie zurückgesetzt wird, ehrliche Grenze (Namen im Fließtext ohne Anrede/Absender/Signatur; Orte ohne PLZ; Fahrzeugmodelle bleiben sichtbar, absichtlich).
4. **Pipeline** – vier Schritte in einem Satz je Schritt; Modell liefert JSON, Antworttext kommt aus einer Vorlage.
5. **Lokal starten** – `copy .env.example .env`, Schlüssel eintragen, `run.bat` (Windows) oder `sh run.sh`, Browser `http://localhost:8040`. Alle Mails per `python -m app.cli --neu` verarbeiten.
6. **Modellzugriff** – Tabelle der vier Variablen für Langdock und Ollama; Satz: „Der Ollama-Pfad ist gebaut, aber von mir noch nicht gegen eine laufende Ollama-Instanz geprüft." (Der Autor streicht den Satz, sobald er es geprüft hat.)
7. **Testdaten** – 15 erfundene Mails, welche Störfälle enthalten sind (Dialekt, ohne Kennzeichen, drei Anliegen, Verkauf statt Werkstatt, sicherheitsrelevant, ausgebuchter Wunschzeitraum, englisch, sehr kurz, Firmensignatur mit Adresse).
8. **Tests** – `python -m pytest -q`; Echtlauf nur mit `LLM_API_KEY`.
9. **GitHub Pages einschalten** – Settings → Pages → Source „Deploy from a branch", Branch `main`, Ordner `/docs`; nach jedem `python -m app.cli --pages` committen.
10. **Bewusst nicht enthalten** – Mailanbindung, Login, Deployment, Datenbank.
11. **Wie ich das im Autohaus umsetzen würde** – dieselben vier Sätze wie im Portfolio: DMS-Anbindung (Kunden-/Fahrzeugdaten aus dem Dealer-Management-System, Kennzeichen als Schlüssel), Freigabeworkflow (Entwurf in der gewohnten Oberfläche, Klick sendet, Protokoll mit Absender und Zeitpunkt), Auslastungssteuerung (Kapazität je Arbeitsplatz und Qualifikation, sicherheitsrelevante Mängel vorziehen). Klar als Ausblick markiert.

- [ ] **Step 3: Gesprächsleitfaden**

`docs/GESPRAECH.md` – „Was ich im Gespräch live zeige (5 Minuten)":
1. Seite öffnen, Mail m12 (Beule in der Tür) anklicken: links Original, rechts das, was das Modell bekam. Auf „Sabine Krämer" zeigen: Name aus der Anrede „meine Frau Sabine Krämer" erkannt, Adresse, PLZ, Telefon, Kennzeichen ersetzt.
2. Extrahierte Felder: Kategorie Karosserie, Zuständigkeit Werkstatt, Wunschzeitraum leer → Termin ab nächstem Werktag.
3. Mail m13 (Motorleuchte rot): Dringlichkeit sicherheitsrelevant, Termin heute, Hinweis „vorgezogen".
4. Mail m06 (Probefahrt): Zuständigkeit Verkauf, kein Termin, Weiterleitungstext.
5. Mail m07 (Mittwoch/Donnerstag): Wunschtage ausgebucht, Vorschlag danach mit Hinweis.
6. Mail m03 (Dialekt): Modell versteht „Nachmittags, morgens aufm Bau".
7. „Neue Mail": eine Anfrage live eintippen, verarbeiten, Ergebnis zeigen. Dabei sagen: Anbieter umschaltbar, mit Ollama bleibt alles auf dem Rechner.
8. Zum Schluss den Fehlerpfad: was passiert, wenn das Modell kein gültiges JSON liefert (Status „Prüfung nötig", kein Absturz).

- [ ] **Step 4: Abschlussprüfung**

```bash
python -m pytest -q
git status --short
grep -rn "sk-\|LANGDOCK_API_KEY=." --include=*.py --include=*.json --include=*.md --include=*.html . | grep -v ".env.example" || echo "kein Schluessel im Repo"
```
Expected: alle Tests grün, kein Schlüssel im Repo.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: README, Startskripte, Gespraechsleitfaden

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
