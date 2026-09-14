# Kundenanfragen-Assistent für einen Workwear-Versender – Design

Stand: 14.09.2026. Repo `kundenanfragen-assistent`, Basis: Kopie des
Serviceanfragen-Assistenten (Branch cloud-deployment, acac544) ohne Historie.

## Ziel

Eine Demo für die Rolle „AI Integration Specialist": Kundenmails eines
Berufsbekleidungs-Versenders werden pseudonymisiert, von einem Modell
strukturiert ausgelesen, mit Daten aus ERP, CRM und MES angereichert, nach
festen Regeln priorisiert und zugewiesen, mit einem Antwortentwurf versehen und
als Ticket ins CRM geschrieben. Der Fokus liegt auf der Integration: klare
Schnittstellenverträge, Fehlertoleranz, Idempotenz, austauschbares Modell mit
gemessener Qualität, reproduzierbarer Cloud-Weg ohne laufende Kosten.

Der Versender heißt „Berufskleidung Nord GmbH" (erfunden). Kunden sind
erfundene Handwerksbetriebe. Kein realer Firmenname, insbesondere nicht der des
Zielunternehmens, kommt im Repo vor.

## Nicht-Ziele

- Keine Mailanbindung, kein Login, keine Datenbank (JSON-Dateien wie bisher).
- Kein echtes ERP/CRM/MES; die drei Systeme sind Mocks mit realistischen
  Verträgen.
- Kein Ausrollen, kein `terraform apply`, kein Langdock-Zugang des Arbeitgebers.

## Übernommen aus dem Vorgänger (unverändert oder nur umbenannt)

- `app/anonymisierung.py` (Pseudonymisierung: EMAIL, FIRMA, TELEFON, ADRESSE,
  ORT, NAME) samt Tests. Kennungen (Kunden-, Bestell-, Rechnungs-,
  Veredelungs-, Artikelnummern) bleiben sichtbar, wie vorher Anlagennummern.
- `app/llm_client.py` (OpenAI-kompatibel), `app/speicher.py`, Live-Schalter
  `LIVE_MODELLAUFRUFE`, Dockerfile, Compose, CI, Terraform, render/fly, Ruff.
- Test „kein Originalwert erreicht das Modell".

## Fachliche Entscheidungen

### Kennungen (nie pseudonymisiert, vom Telefon-Muster nicht erfasst)

| Kennung | Format | Beispielbereich |
|---|---|---|
| Kundennummer | `K-1xxxx` | K-10234 … K-11045 |
| Bestellnummer | `B-2026-xxxxx` | B-2026-04120 … B-2026-04761 |
| Rechnungsnummer | `R-2026-xxxxx` | R-2026-07688, R-2026-07731 |
| Veredelungsauftrag | `V-2026-xxx` | V-2026-118 … V-2026-142 |
| Artikelnummer | `A-4xxx` | A-4101 … A-4801 |
| Sendungsnummer | `SN-` + 8 Zeichen alphanumerisch | SN-7F3K9Q2L |
| Maschine | `STK-0x`, `DRK-0x` | STK-01 |

Keine Kennung beginnt mit `0` oder `+`, damit das Telefon-Muster sie nicht
frisst. Ein Test belegt das für jede Kennungsart.

### Kategorien, Zuständigkeit, Dringlichkeit

Kategorien (Modell): `bestellstatus`, `ruecksendung`, `reklamation`,
`veredelung`, `angebot`, `rechnung`, `verfuegbarkeit`, `sonstiges`.

Zuständigkeit wird **nicht** vom Modell bestimmt, sondern aus den Kategorien
abgeleitet, in dieser Rangfolge (die erste zutreffende gewinnt):
`reklamation` → kundenservice; `veredelung` → veredelung; `angebot` →
vertrieb; `rechnung` → buchhaltung; alles andere → kundenservice.

Dringlichkeit: das Modell liefert `niedrig|mittel|hoch`. Der Code überschreibt
auf `hoch`, wenn `frist` innerhalb von drei Werktagen ab Basisdatum liegt oder
die Kategorie `reklamation` ist, und notiert den Grund in
`dringlichkeit_grund`. Basisdatum 2026-09-14 (Montag) in `data/konfig.json`.

### Extraktionsschema (tolerant gegenüber lokalen Modellen)

```
kunde:           {firma: str|null, kundennummer: str|null}
ansprechpartner: {anrede: str|null, name: str|null}      # anrede nur "Herr"/"Frau", sonst null
bezug:           {bestellnummer, rechnungsnummer, veredelungsauftrag: str|null}
artikel:         [{artikelnummer, bezeichnung, groesse, farbe: str|null, menge: int|null}]
anliegen:        [{kategorie: Kategorie, beschreibung: str}]
dringlichkeit:   niedrig|mittel|hoch                      # ungültig oder null → mittel
frist:           YYYY-MM-DD|null                           # ungültig → null
unklarheiten:    [str]
```

Lehren aus dem Ollama-Vergleich vom 14.09.2026: keine realistisch aussehenden
Beispielwerte im Prompt (qwen2.5:14b setzte die Beispiel-Anlagennummer als
echten Wert ein), keine `a|b|c`-Schreibweise für Aufzählungen im Schematext
(wurde wörtlich kopiert), Enums mit Vorvalidierung statt harter Literale
(gpt-oss:20b lieferte `null` statt Standardwert). Ungültige Enum-Werte fallen
auf den Standard zurück, statt die ganze Antwort zu verwerfen; das wird
protokolliert (`extraktion_hinweise`).

### Systemlandschaft (Mocks)

Ein Python-Paket `systeme/` mit einer FastAPI-App, die drei Teil-Apps unter
`/erp`, `/crm`, `/mes` einhängt; jede hat eigene OpenAPI-Doku
(`/erp/docs` usw.). Start: `uvicorn systeme.main:app --port 8050`. Daten in
`systeme/daten/*.json`; Tickets werden in `systeme/daten/tickets.json`
geschrieben (Pfad per Umgebungsvariable `SYSTEME_DATEN` überschreibbar).

**ERP** (`/erp`)
- `GET /kunden/{kundennummer}` → Kunde (kundennummer, firma, ort, kundenseit, zahlungsziel_tage)
- `GET /kunden/{kundennummer}/bestellungen` → letzte Bestellungen (neueste zuerst)
- `GET /bestellungen/{bestellnummer}` → Bestellung (bestellnummer, kundennummer, status `offen|kommissionierung|versendet|teilgeliefert|zugestellt`, bestelldatum, liefertermin, sendungsnummer|null, positionen [{artikelnummer, bezeichnung, groesse, farbe, menge, status}])
- `GET /artikel/{artikelnummer}` → Artikel (artikelnummer, bezeichnung, varianten [{groesse, farbe, bestand, nachfolger|null}])
- `GET /rechnungen/{rechnungsnummer}` → Rechnung (rechnungsnummer, kundennummer, bestellnummer, betrag, faellig, status `offen|bezahlt`, kostenstelle|null)
- Unbekannt → 404 `{"detail": "... unbekannt"}`

**CRM** (`/crm`)
- `GET /kontakte?email=` → Kontakt (kontakt_id, name, email, kundennummer, firma) oder 404
- `POST /tickets` Body `{externe_referenz, kundennummer|null, kontakt_email, betreff, kategorien[], prioritaet, zustaendigkeit, zusammenfassung}` → 201 mit Ticket; existiert `externe_referenz` schon → 200 mit dem vorhandenen Ticket (idempotent, kein Duplikat)
- `GET /tickets/{ticket_id}`, `PATCH /tickets/{ticket_id}` Body `{status: offen|beantwortet|verworfen}`
- Ticket-IDs `T-2026-0001` fortlaufend.

**MES** (`/mes`)
- `GET /veredelungsauftraege/{nr}` → (auftrag, bestellnummer, kundennummer, art `stick|druck`, motiv, status `entwurf|freigabe_offen|eingeplant|in_produktion|fertig`, maschine|null, geplantes_ende|null, hinweis|null)
- `GET /maschinen` → Zustandsliste (maschine, typ, zustand `laeuft|stillstand|stoerung`, meldung|null, seit); das ist der OT-Bezug: Maschinenzustände, die eine Aussage „Ihr Auftrag ist eingeplant" relativieren können.
- `GET /maschinen/{maschine}`

### Adapterschicht (`app/integration/`)

- `erp.py`, `crm.py`, `mes.py`: dünne Clients auf `httpx.Client`; Timeout 3 s,
  ein Wiederholungsversuch bei Verbindungsfehler, 404 → `None`, andere Fehler
  → `SystemNichtErreichbar(system, grund)`.
- `verbindung.py`: baut den `httpx.Client`. Ohne `SYSTEME_BASE_URL` läuft die
  Systemlandschaft **im Prozess** über `httpx.ASGITransport(app=systeme.main.app)`;
  mit `SYSTEME_BASE_URL` (Compose: `http://systeme:8050`, Azure-Sidecar:
  `http://localhost:8050`) über HTTP. Gleicher Code, andere Transportschicht.
- `fake.py`: In-Memory-Fakes mit derselben Schnittstelle für Tests.
- Ausfall eines Systems bricht die Verarbeitung nicht ab: der Schritt wird
  übersprungen, `integrationsfehler` im Ergebnis benennt System und Grund, der
  Antwortentwurf fällt auf eine Formulierung ohne Systemdaten zurück, Status
  wird `pruefung_noetig`.

### Pipeline

```
Mail
 1. Pseudonymisierung        (Regex, lokal)
 2. Extraktion               (Modell, sieht nur Platzhalter)
 3. Rücksetzen               (Platzhalter → Originale, lokal)
 4. Anreicherung             (CRM-Kontakt per Absenderadresse → Kundennummer;
                              ERP-Kunde, -Bestellung, -Rechnung, -Artikel;
                              MES-Auftrag und Maschinenzustand; Plausibilität)
 5. Regeln                   (Zuständigkeit, Dringlichkeit, Grund)
 6. Antwortentwurf           (Vorlage je Kategorie, mit Systemdaten)
 7. CRM-Ticket               (idempotent über externe_referenz = mail_id)
```

Plausibilität in Schritt 4: unbekannte Bestell-/Rechnungs-/Veredelungsnummer →
Eintrag in `unklarheiten` und `hinweise`; Bestellung gehört einem anderen
Kunden → Hinweis; Liefertermin nach genannter Frist → Hinweis; Maschine des
Veredelungsauftrags in `stoerung` → Hinweis „geplantes Ende gefährdet".

Ergebnisfelder: `mail_id, roh_text, pseudonym_text, platzhalter, extraktion,
extraktion_fehler, extraktion_hinweise, systemdaten {kontakt, kunde, bestellung,
letzte_bestellungen, rechnung, artikel, veredelung, maschine}, hinweise,
integrationsfehler, zustaendigkeit, dringlichkeit, dringlichkeit_grund,
antwort_entwurf, ticket {ticket_id, status} | null, status, anbieter, modell,
dauer_ms, zeitpunkt`.

Freigabe/Ablehnung im Server setzt den CRM-Ticketstatus (`beantwortet` /
`verworfen`, zurück auf `offen`).

### Modellvergleich (`python -m app.vergleich`)

Läuft Pseudonymisierung, Extraktion und Regeln für alle Mails je Modell (Liste
per `--modelle`), ohne Ticket und ohne Systemzugriff, und vergleicht gegen
handgeschriebene Soll-Werte in `data/erwartet.json` (Kategorien als Menge,
Zuständigkeit, Dringlichkeit, Bestellnummer, Kundennummer, Frist). Schreibt
`data/vergleich.json` und `docs/modellvergleich.md` (Tabelle: Modell,
Treffer je Feld, Schemafehler, mittlere Dauer). Die Tabelle wird ins README
übernommen. Referenz sind Soll-Werte, nicht ein anderes Modell.

### Modellzugriff

Standard Ollama (`gpt-oss:20b`, lokal, kostenlos, RTX 5070 Ti 16 GB). Zweiter
Kandidat `qwen2.5:14b-instruct`. Reserve: jeder OpenAI-kompatible Anbieter mit
eigenem Schlüssel (`LLM_PROVIDER=openai`). Langdock kommt im Code nicht mehr vor.

### Oberfläche

`docs/index.html` (Vanilla JS, statischer Modus über `docs/data/`): Liste,
Detail mit Pseudonym-Text und Platzhaltertabelle, extrahierte Felder, neuer
Block „Systemdaten" (ERP-Bestellung mit Status und Sendungsnummer,
MES-Auftrag mit Maschine, CRM-Ticket), Hinweise und Integrationsfehler
sichtbar, Antwortentwurf, Freigeben/Ablehnen/Neu verarbeiten, Neue Mail.
Live-Schalter wie bisher.

### Betrieb

- Ein Image, zwei Kommandos: `app.main:app` (8040) und `systeme.main:app` (8050).
  Compose: zwei Dienste, `SYSTEME_BASE_URL=http://systeme:8050`.
- Terraform: die Systemlandschaft läuft als zweiter Container (Sidecar) in
  derselben Container App, App spricht `http://localhost:8050`. Nur der App-Port
  ist extern. Sonst unverändert (scale-to-zero, Key Vault, Budget).
- CI: Rauchtest zusätzlich `GET /erp/docs` der Systemlandschaft und
  `GET /api/status` mit `systeme_erreichbar: true`.
- Namen überall `kundenanfragen-assistent`, Image `ghcr.io/dangtu1190-tech/kundenanfragen-assistent`.

### Dokumentation

README neu (Domäne, Architekturbild, Pseudonymisierung mit Kennungsregel,
Integrationsentscheidungen, Modellvergleich, Lokal starten, Modellzugriff,
Testdaten, Tests, Pages, Betrieb, Bewusst nicht enthalten, „Wie ich das im
Betrieb umsetzen würde" mit realen Schnittstellen: ERP-API/IDoc, MES über
OPC UA/MQTT, Ereignisse statt Polling, Nachrichtenwarteschlange, Schema-
Registry, Beobachtbarkeit). `docs/GESPRAECH.md` als kurzer Leitfaden mit
Grenzen. Alte Planungsdokumente des Vorgängers werden entfernt.

## Tests

- Systemlandschaft: jeder Endpunkt, 404-Verhalten, Idempotenz des Tickets.
- Adapter: gegen die Systemlandschaft im Prozess; Timeout/Verbindungsfehler →
  `SystemNichtErreichbar`; 404 → `None`.
- Extraktion: tolerante Validierung (null-Enum, ungültige Frist), Prompt ohne
  Beispielwerte, Kennungen wörtlich.
- Pseudonymisierung: Kennungen bleiben stehen; erwartete Platzhaltertypen je
  Mail (aus dem Text abgelesen, nicht aus der Ausgabe).
- Pipeline: kein Originalwert erreicht das Modell (unverändert scharf);
  Anreicherung mit Fakes; Ausfall eines Systems → `pruefung_noetig`,
  Ticket bleibt idempotent; Regeln für Zuständigkeit und Dringlichkeit.
- Server: Ticketstatus folgt Freigabe/Ablehnung; Live-Schalter.
- Vergleich: mit FakeClient gegen `erwartet.json`, Tabelle wird geschrieben.
- Echtlauf: alle 15 Mails mit `gpt-oss:20b`, Ergebnisse in `data/` und
  `docs/data/`; Vergleich beider Ollama-Modelle in `docs/modellvergleich.md`.
