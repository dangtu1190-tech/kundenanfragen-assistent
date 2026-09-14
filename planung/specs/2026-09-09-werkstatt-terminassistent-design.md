# Werkstatt-Terminassistent – Design

Stand 09.09.2026. Eigenprojekt, Demo mit erfundenen Testdaten. Zweck: zeigen,
dass die Serviceannahme per E-Mail in einem Autohaus automatisierbar ist, ohne
dass personenbezogene Daten an ein Sprachmodell gehen.

## Ziel und Nicht-Ziel

Ziel: Eine E-Mail wird zu strukturierten Feldern, einem Terminvorschlag und
einem Antwortentwurf, den ein Mitarbeiter freigibt. Kernstück ist die
Anonymisierungsschicht, deren Wirkung im UI sichtbar ist.

Nicht im Umfang: echte Mailanbindung, Authentifizierung, Server-Deployment,
Datenbank. Datenhaltung ist eine JSON-Datei. Läuft lokal.

## Zeigbarkeit (drei Wege)

1. **Browser-Demo ohne Installation** über GitHub Pages: die Oberfläche liest
   die vorberechneten Ergebnisse aller 15 Mails aus einer JSON-Datei. Kein
   Modellaufruf, kein Schlüssel. Freigabe-Knöpfe wirken dort nur sichtbar,
   mit Hinweis "statischer Modus".
2. **Quellcode mit README** auf GitHub: drei Befehle zum lokalen Start mit
   eigenem Langdock- oder Ollama-Zugang, dann echte Pipeline.
3. **Live im Gespräch**: neue Mail im UI eintippen, Pipeline läuft sichtbar.

Kein Screencast (Entscheidung des Autors).

## Struktur

```
werkstatt-terminassistent/
  app/
    anonymisierung.py   Platzhalter setzen und zurücksetzen (reiner Rechenkern)
    extraktion.py       Prompt bauen, Modell aufrufen, JSON prüfen (Pydantic)
    kalender.py         Kapazitätskalender laden, freien Slot finden
    antwort.py          Antwortentwurf aus Feldern + Termin (Vorlage, kein Modell)
    pipeline.py         vier Schritte hintereinander, liefert Ergebnisobjekt
    llm_client.py       ein OpenAI-kompatibler Client, Basis-URL je Anbieter
    main.py             FastAPI: Mails, Verarbeitung, Ergebnisse, Freigabe
    cli.py              alle Mails verarbeiten, Ergebnisse schreiben
  data/
    mails.json          15 erfundene Mails
    kalender.json       Kapazität je Werktag und Halbtag
    ergebnisse.json     Ergebnisse je Mail (einzige Datenhaltung)
  docs/index.html       Oberfläche (dient auch als GitHub-Pages-Seite)
  docs/data/            Kopie von mails.json und ergebnisse.json für Pages
  tests/
  README.md, .env.example, requirements.txt, run.bat, run.sh
```

Die Oberfläche liegt unter `docs/`, weil GitHub Pages diesen Ordner ohne
Build ausliefern kann. Der FastAPI-Server liefert dieselbe Datei aus.

## Datenfluss je Mail

Rohtext → Anonymisierung (liefert pseudonymisierten Text + Platzhaltertabelle)
→ Modell bekommt NUR den pseudonymisierten Text, antwortet mit JSON →
Pydantic-Validierung → Platzhalter im JSON zurückersetzen → Kalenderabgleich →
Antwortentwurf aus Vorlage → Ergebnis speichern.

Ergebnisobjekt (Felder): mail_id, roh_text, pseudonym_text, platzhalter
(Liste aus typ, platzhalter, original), extraktion (validiertes JSON oder
null), extraktion_fehler (Text oder null), termin (Datum, Halbtag, Hinweis)
oder null, antwort_entwurf, status (offen / freigegeben / abgelehnt /
pruefung_noetig), anbieter, modell, dauer_ms, zeitpunkt.

## Anonymisierung

Deterministisch, ohne Modell. Reihenfolge (jeweils Regex, bereits ersetzte
Stellen werden nicht erneut angefasst):

1. E-Mail-Adressen → `[EMAIL_n]`
2. Telefonnummern (deutsche Formate: +49, 0…, Leerzeichen, `/`, `-`,
   Klammern; mindestens 6 Ziffern) → `[TELEFON_n]`
3. Kennzeichen (`AB-CD 1234`, `AB CD1234`, `AB-C-12E`, `AB-CD 123H`) →
   `[KENNZEICHEN_n]`
4. Adressen: Straße/Weg/Platz/Allee/Gasse/Ring + Hausnummer → `[ADRESSE_n]`;
   PLZ + Ort (5 Ziffern + Wort mit Großbuchstabe) → `[ORT_n]`
5. Namen → `[NAME_n]`: aus dem Absenderfeld (Vorname Nachname), aus
   `Herr|Frau|Hr.|Fr. X [Y]`, aus der Zeile nach einer Grußformel
   (Viele Grüße, Mit freundlichen Grüßen, Gruß, LG, MfG, Beste Grüße,
   Schöne Grüße, Servus, Grüße) und aus der Anrede "Hallo X" wenn X kein
   Wort der Ausschlussliste ist (Team, Werkstatt, zusammen, Autohaus).
   Einmal gefundene Namen werden im gesamten Text ersetzt, auch Vor- oder
   Nachname allein, Groß-/Kleinschreibung unempfindlich.

Gleicher Originalwert → gleicher Platzhalter. Rückersetzung
(`zuruecksetzen(text, tabelle)`) ersetzt alle Platzhalter in Text oder
JSON-Strings, rekursiv über dict/list.

Bekannte Grenze (steht im README): Namen im Fließtext ohne Anrede und ohne
Signatur werden nicht erkannt. Fahrzeugmodelle und Orte ohne PLZ bleiben
sichtbar.

## Extraktion

Prompt (deutsch) mit festem JSON-Schema:

```
kunde: {anrede, name}                     name enthält Platzhalter
fahrzeug: {marke, modell, baujahr|null, kilometerstand|null}
kennzeichen: string|null                  Platzhalter oder null
anliegen: [{kategorie, beschreibung}]     kategorie ∈ wartung, reparatur,
                                          reifen, hu_au, karosserie,
                                          verkauf, sonstiges
dringlichkeit: niedrig|mittel|hoch|sicherheitsrelevant
wunschzeitraum: {von: YYYY-MM-DD|null, bis: YYYY-MM-DD|null,
                 tageszeit: vormittag|nachmittag|egal}
zustaendigkeit: werkstatt|verkauf
unklarheiten: [string]
```

Heutiges Datum steht im Prompt (Basisdatum der Demo: 2026-09-14, Montag,
damit die Ergebnisse stabil bleiben). Temperatur 0, JSON-Antwort per
`response_format={"type": "json_object"}`; wenn der Anbieter das nicht kann,
Fallback auf Klammer-Extraktion. Ungültiges JSON oder Validierungsfehler →
`extraktion=null`, `extraktion_fehler` gesetzt, Status `pruefung_noetig`,
kein Absturz.

## Modellzugriff

`llm_client.py`: `openai.OpenAI(api_key, base_url)`. Konfiguration über
Umgebungsvariablen:

| Variable | langdock | ollama |
|---|---|---|
| LLM_PROVIDER | langdock | ollama |
| LLM_BASE_URL | https://api.langdock.com/openai/eu/v1 | http://localhost:11434/v1 |
| LLM_MODEL | gpt-5.1 | z. B. qwen2.5:7b |
| LLM_API_KEY | Langdock-Schlüssel | beliebig (Ollama ignoriert ihn) |

Der Ollama-Pfad ist gebaut, aber bis zur Prüfung durch den Autor ungetestet;
das steht so im README.

Tests ersetzen den Client durch einen Fake, der ein festes JSON liefert.
Ein Echtlauf-Test läuft nur, wenn `LLM_API_KEY` gesetzt ist.

## Kalender

`kalender.json`: je Werktag ab Basisdatum zwei Halbtage (vormittag,
nachmittag) mit `kapazitaet` und `belegt`. Zwei Tage voll, ein Tag halb voll.

Regeln:
- zustaendigkeit = verkauf → kein Termin, Antwort ist eine Weiterleitung.
- dringlichkeit = sicherheitsrelevant → nächster freier Halbtag ab heute,
  Hinweis "vorgezogen".
- sonst: erster freier Halbtag im Wunschzeitraum, passend zur Tageszeit;
  kein Treffer → erster freier Halbtag nach dem Zeitraum, Hinweis
  "außerhalb des Wunschzeitraums".
- Wunschzeitraum leer → ab heute + 1 Werktag.

Vorschlag reserviert nichts. Erst "freigeben" im UI erhöht `belegt`.

## Antwortentwurf

Deutsche Vorlage, kein Modell. Anrede aus `kunde`, Aufzählung der Anliegen,
Terminvorschlag mit Datum und Halbtag, Bitte um Bestätigung, bei
Unklarheiten eine Rückfrage, bei Verkauf Weiterleitungstext. Signatur
"Ihr Serviceteam". Platzhalter sind zurückersetzt, der Text ist editierbar.

## API (FastAPI)

- `GET /api/mails` – Liste (id, absender, betreff, status)
- `GET /api/mails/{id}` – Mail + Ergebnis
- `POST /api/mails/{id}/verarbeiten` – Pipeline laufen lassen
- `POST /api/mails` – neue Mail anlegen (Live-Vorführung)
- `POST /api/mails/{id}/status` – freigeben / ablehnen, Entwurf speichern
- `GET /api/status` – Anbieter, Modell, Schlüssel gesetzt ja/nein
- `/` liefert `docs/index.html`

## Oberfläche

Drei Spalten. Links Posteingang mit Status-Badge und Knopf "Alle
verarbeiten". Mitte oben zwei Textfelder nebeneinander: "So sieht es der
Mitarbeiter" (Original) und "Das bekam das Modell" (pseudonymisiert), mit
farbig markierten Platzhaltern; darunter die extrahierten Felder als
Tabelle und die Platzhaltertabelle. Rechts der Antwortentwurf (editierbar),
Terminvorschlag, Knöpfe Freigeben / Ablehnen / Neu verarbeiten. Kopfzeile
zeigt Anbieter und Modell oder "statischer Modus".

Statischer Modus: `fetch('/api/status')` schlägt fehl → Daten aus
`data/mails.json` und `data/ergebnisse.json` laden, Schreibaktionen zeigen
einen Hinweis.

## Testdaten

15 Mails, alle erfunden (Namen, Kennzeichen, Telefonnummern, Adressen
plausibel, aber frei). Enthalten mindestens: eine im Dialekt (bairisch oder
hessisch), eine ohne Kennzeichen, eine mit drei Anliegen, eine für den
Verkauf, eine sicherheitsrelevante (Bremsen), eine mit Wunschzeitraum in
ausgebuchten Tagen, eine sehr kurze, eine mit Signatur samt Adresse und
Telefon, eine auf Englisch, eine mit Kilometerstand und Baujahr.

## Tests

- `test_anonymisierung.py`: jede Kategorie, Mehrfachvorkommen, Rückersetzung,
  Idempotenz, keine Ziffer eines Kennzeichens bleibt übrig.
- `test_kalender.py`: Wunschzeitraum, ausgebucht, sicherheitsrelevant, Verkauf.
- `test_antwort.py`: Entwurf enthält Anliegen, Termin, keinen Platzhalter.
- `test_extraktion.py`: Schema-Validierung, ungültiges JSON → Fehlerpfad.
- `test_pipeline.py`: alle 15 Mails mit Fake-Modell; Prüfung, dass der Text
  an das Modell keine der bekannten Originalwerte enthält.
- `test_echtlauf.py`: nur mit Schlüssel.

## Reihenfolge

1. Anonymisierung, Kalender, Antwort, Extraktion mit Fake (TDD).
2. Pipeline + CLI, Echtlauf gegen Langdock, Ergebnisse speichern.
3. FastAPI + Oberfläche.
4. Statischer Modus, Pages-Ordner, README, run-Skripte.
