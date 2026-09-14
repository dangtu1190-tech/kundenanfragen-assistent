# Kundenanfragen-Assistent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Demo vom Anlagenbau auf Kundenanfragen eines Workwear-Versenders umstellen und um eine Integrationsschicht (Mock-ERP, -CRM, -MES mit OpenAPI, Adapter, Regeln, idempotentes Ticket) sowie einen Modellvergleich erweitern; Pseudonymisierung, Live-Schalter und Cloud-Weg bleiben.

**Architecture:** Neues Paket `systeme/` (FastAPI, drei Teil-Apps) neben `app/`. In `app/` ersetzen `integration/` (Adapter), `anreicherung.py`, `regeln.py` die Module `kalender.py` und `ersatzteile.py`; `extraktion.py`, `antwort.py`, `pipeline.py`, `main.py`, `cli.py` werden auf die neue Domäne umgestellt; `vergleich.py` kommt hinzu. Ohne `SYSTEME_BASE_URL` läuft die Systemlandschaft im Prozess (ASGITransport), sonst über HTTP.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2, httpx, openai-SDK (OpenAI-kompatibel, Standard Ollama), pytest, Vanilla JS, Docker, GitHub Actions, Terraform/azurerm 4.

**Spec:** `planung/specs/2026-09-14-kundenanfragen-assistent-design.md`

## Global Constraints

- Arbeitsverzeichnis `C:\Users\dtn\Desktop\Engel` (Repo `kundenanfragen-assistent`, Branch `main`, noch kein Remote). Python `python`.
- Sprache Deutsch (Code-Bezeichner, Kommentare, UI, Doku, Commits). Keine Gedankenstriche (—) in Prosa. Kein realer Firmenname; Versender „Berufskleidung Nord GmbH", Mail-Domains enden auf `.example`.
- Kein Schlüssel, kein Langdock. Standard-Modellzugriff Ollama (`http://localhost:11434/v1`, `gpt-oss:20b`, Schlüsselwert `ollama`). Tests laufen ohne Netz und ohne Ollama (FakeClient, Fakes, ASGITransport).
- Kennungen `K-1xxxx`, `B-2026-xxxxx`, `R-2026-xxxxx`, `V-2026-xxx`, `A-4xxx`, `SN-XXXXXXXX`, `STK-0x`, `DRK-0x` werden nie pseudonymisiert und beginnen nie mit `0` oder `+`. Basisdatum 2026-09-14 (Montag) in `data/konfig.json`.
- Vor jedem Commit: `python -m pytest -q` grün (Echtlauf-Tests skippen ohne `LLM_API_KEY`), Ruff (`ruff.toml`, Binary `C:\Users\dtn\AppData\Local\Temp\claude\c--Users-dtn-Desktop-Engel\9776635e-1787-4a2c-955e-323fce53f99c\scratchpad\venv\Scripts\ruff.exe check app systeme tests`) grün, `git status --short` ohne `__pycache__`, `.env`, `.terraform`.
- Dateien unter 300 Zeilen (Ausnahmen: `docs/index.html`, Datendateien). UTF-8 ohne BOM, LF. Commits enden mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Das Modell bekommt ausschließlich `pseudonym_text`. Systemdaten (Kundenname aus ERP/CRM) gehen nie ins Modell.

---

## Dateistruktur

| Datei | Änderung | Task |
|---|---|---|
| `systeme/__init__.py`, `systeme/main.py`, `systeme/erp.py`, `systeme/crm.py`, `systeme/mes.py`, `systeme/speicher.py` | neu: Mock-Systemlandschaft | 1 |
| `systeme/daten/kunden.json`, `bestellungen.json`, `artikel.json`, `rechnungen.json`, `kontakte.json`, `veredelung.json`, `maschinen.json`, `tickets.json` | neu: Stammdaten | 1 |
| `tests/test_systeme.py` | neu | 1 |
| `app/integration/__init__.py`, `verbindung.py`, `erp.py`, `crm.py`, `mes.py`, `fake.py` | neu: Adapter | 2 |
| `tests/test_integration.py` | neu | 2 |
| `data/mails.json`, `data/konfig.json`, `data/erwartet.json` | neu (alte Mails, `kalender.json`, `ersatzteile.json`, `ergebnisse.json`, `docs/data/*` gelöscht) | 3 |
| `app/extraktion.py`, `app/antwort.py`, `app/pipeline.py`, `app/main.py`, `app/cli.py`, `app/llm_client.py` | umgestellt | 3 |
| `app/kalender.py`, `app/ersatzteile.py`, `tests/test_kalender.py`, `tests/test_ersatzteile.py`, `docs/GESPRAECH.md`, `planung/specs/2026-09-09-*`, `planung/specs/2026-09-10-*`, `planung/plans/2026-09-09-*`, `planung/plans/2026-09-10-*`, `planung/plans/2026-09-11-*`, `planung/specs/2026-09-11-*` | gelöscht | 3 |
| `tests/test_extraktion.py`, `test_antwort.py`, `test_pipeline.py`, `test_main.py`, `test_echtlauf.py`, `tests/test_kennungen.py` | umgestellt / neu | 3 |
| `app/anreicherung.py`, `app/regeln.py`, `tests/test_anreicherung.py`, `tests/test_regeln.py` | neu; `antwort.py`, `pipeline.py`, `main.py` erweitert | 4 |
| `app/vergleich.py`, `tests/test_vergleich.py`, `docs/modellvergleich.md` | neu | 5 |
| `docs/index.html` | umgestellt | 6 |
| `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/ci.yml`, `infra/azure/*`, `render.yaml`, `fly.toml`, `.env.example`, `run.bat`, `run.sh` | angepasst | 7 |
| `data/ergebnisse.json`, `docs/data/*`, `data/vergleich.json`, `docs/modellvergleich.md` | Echtlauf | 8 |
| `README.md`, `docs/GESPRAECH.md` | neu | 9 |

---

## Stammdaten (verbindlich für Task 1 und Task 3)

**Kunden (ERP `kunden.json`)** – Felder `kundennummer, firma, ort, kundenseit, zahlungsziel_tage`

| Kundennummer | Firma | Ort | kundenseit | Zahlungsziel |
|---|---|---|---|---|
| K-10234 | Dachdeckerei Brandt GmbH | 23552 Lübeck | 2019-03-12 | 30 |
| K-10311 | Elektro Kessler & Sohn GmbH & Co. KG | 34117 Kassel | 2017-08-01 | 30 |
| K-10402 | SHK Mertens GmbH | 28195 Bremen | 2021-01-20 | 14 |
| K-10577 | Gartenbau Wille | 26122 Oldenburg | 2023-04-03 | 14 |
| K-10620 | Malerbetrieb Yilmaz GmbH | 30159 Hannover | 2020-06-15 | 30 |
| K-10688 | Metallbau Reuter AG | 24103 Kiel | 2016-11-02 | 30 |
| K-10715 | Tiefbau Hansen & Petersen GmbH | 24937 Flensburg | 2018-02-27 | 30 |
| K-10802 | Zimmerei Lorenz GmbH | 49074 Osnabrück | 2022-09-09 | 14 |
| K-10930 | Gebäudereinigung Sauber & Co. GmbH | 20095 Hamburg | 2015-05-05 | 30 |
| K-11045 | Kfz-Werkstatt Adler GmbH | 18055 Rostock | 2024-02-14 | 14 |

**Kontakte (CRM `kontakte.json`)** – Felder `kontakt_id, name, email, kundennummer, firma`

| ID | Name | E-Mail | Kunde |
|---|---|---|---|
| C-501 | Jens Brandt | j.brandt@dachdeckerei-brandt.example | K-10234 |
| C-502 | Martina Kessler | m.kessler@elektro-kessler.example | K-10311 |
| C-503 | Torben Mertens | t.mertens@shk-mertens.example | K-10402 |
| C-504 | Anke Wille | info@gartenbau-wille.example | K-10577 |
| C-505 | Cem Yilmaz | c.yilmaz@maler-yilmaz.example | K-10620 |
| C-506 | Sabine Reuter | s.reuter@metallbau-reuter.example | K-10688 |
| C-507 | Ole Hansen | o.hansen@hansen-petersen.example | K-10715 |
| C-508 | Frank Lorenz | f.lorenz@zimmerei-lorenz.example | K-10802 |
| C-509 | Petra Nowak | p.nowak@sauber-co.example | K-10930 |
| C-510 | Daniel Adler | d.adler@kfz-adler.example | K-11045 |

**Artikel (ERP `artikel.json`)** – `artikelnummer, bezeichnung, varianten[{groesse, farbe, bestand, nachfolger}]`

| Artikel | Bezeichnung | Varianten (Auszug, Bestand) |
|---|---|---|
| A-4101 | Bundhose Basic | anthrazit 48…60 je 120; schwarz 48…60 je 80 |
| A-4102 | Bundhose Stretch | anthrazit 48…60 je 60 |
| A-4210 | Softshelljacke | navy S…L je 40, navy XL 0 (nachfolger A-4211), navy XXL 15 |
| A-4211 | Softshelljacke Pro | navy S…XXL je 50 |
| A-4305 | Warnschutzjacke Klasse 3 | gelb M…XXL je 70; orange M…XXL je 30 |
| A-4410 | Sicherheitsschuh S3 | schwarz 39…48 je 25 |
| A-4520 | Poloshirt | navy S…3XL je 200; grün S…3XL je 90 |
| A-4530 | T-Shirt | weiß S…3XL je 300; schwarz S…3XL je 250 |
| A-4610 | Regenjacke | gelb S…XXL je 35 |
| A-4801 | Knieschutz-Polster | Einheitsgröße 400 |

**Bestellungen (ERP `bestellungen.json`)** – `bestellnummer, kundennummer, status, bestelldatum, liefertermin, sendungsnummer, positionen[{artikelnummer, bezeichnung, groesse, farbe, menge, status}]`

| Bestellung | Kunde | Status | bestellt | Liefertermin | Sendung | Positionen |
|---|---|---|---|---|---|---|
| B-2026-04120 | K-10802 | zugestellt | 2026-06-24 | 2026-06-30 | SN-3H8KD2PA | 3× A-4101 anthrazit 52; 3× A-4210 navy L; 3× A-4410 schwarz 43; 6× A-4520 navy L |
| B-2026-04555 | K-10234 | zugestellt | 2026-07-30 | 2026-08-04 | SN-9Q2LM7XC | 10× A-4801 |
| B-2026-04590 | K-10620 | zugestellt | 2026-08-12 | 2026-08-20 | SN-5TZ4WB8N | 12× A-4530 weiß L (bedruckt, Veredelung V-2026-118) |
| B-2026-04688 | K-10311 | zugestellt | 2026-09-02 | 2026-09-08 | SN-2KP8RD4V | 4× A-4101 anthrazit 52; 4× A-4520 navy L |
| B-2026-04699 | K-10930 | zugestellt | 2026-09-03 | 2026-09-09 | SN-7C4NQ1HE | 6× A-4610 gelb M; 6× A-4610 gelb L |
| B-2026-04702 | K-10402 | teilgeliefert | 2026-09-04 | 2026-09-10 | SN-8VD3JS6R | 2× A-4410 schwarz 43 (geliefert); 2× A-4210 navy XL (offen) |
| B-2026-04711 | K-10234 | versendet | 2026-09-09 | 2026-09-15 | SN-7F3K9Q2L | 6× A-4305 gelb L; 6× A-4305 gelb XL; 6× A-4101 anthrazit 54 |
| B-2026-04733 | K-10688 | kommissionierung | 2026-09-08 | 2026-09-18 | null | 8× A-4210 navy L (bestickt, V-2026-131); 8× A-4101 schwarz 50 |
| B-2026-04750 | K-10715 | offen | 2026-09-12 | 2026-09-19 | null | 10× A-4305 orange L; 10× A-4101 anthrazit 54; 10× A-4410 schwarz 44 |
| B-2026-04760 | K-11045 | offen | 2026-09-12 | 2026-09-24 | null | 6× A-4520 grün M (bestickt, V-2026-140) |
| B-2026-04761 | K-11045 | zugestellt | 2026-09-05 | 2026-09-11 | SN-4RX2ME9T | 4× A-4305 gelb L |

**Rechnungen (ERP `rechnungen.json`)**: R-2026-07688 (K-10311, B-2026-04688, 612,40, fällig 2026-10-08, offen, kostenstelle null); R-2026-07731 (K-10930, B-2026-04699, 1284,50, fällig 2026-10-09, offen, kostenstelle null).

**Veredelungsaufträge (MES `veredelung.json`)** – `auftrag, bestellnummer, kundennummer, art, motiv, status, maschine, geplantes_ende, hinweis`

| Auftrag | Bestellung | Kunde | Art | Motiv | Status | Maschine | Ende | Hinweis |
|---|---|---|---|---|---|---|---|---|
| V-2026-118 | B-2026-04590 | K-10620 | druck | Logo Malerbetrieb Yilmaz, Brust links | fertig | DRK-01 | 2026-08-18 | null |
| V-2026-131 | B-2026-04733 | K-10688 | stick | Logo Metallbau Reuter, Brust links, 3 Farben | in_produktion | STK-01 | 2026-09-16 | null |
| V-2026-140 | B-2026-04760 | K-11045 | stick | Logo Kfz-Werkstatt Adler | freigabe_offen | null | null | Stickdatei fehlt |
| V-2026-142 | B-2026-04750 | K-10715 | druck | Firmenname Rücken | eingeplant | DRK-02 | 2026-09-17 | null |

**Maschinen (MES `maschinen.json`)**: STK-01 Stickmaschine 12-Kopf, laeuft, seit 2026-09-14T06:05; STK-02 Stickmaschine 6-Kopf, stoerung, „Fadenbruch Kopf 4", seit 2026-09-14T06:40; DRK-01 Transferdruck, laeuft, seit 2026-09-14T06:00; DRK-02 Textildirektdruck, stillstand, „Rüsten", seit 2026-09-14T07:15.

**tickets.json**: `[]`.

## Testmails (verbindlich für Task 3, `data/mails.json`)

Felder wie bisher: `id, absender_name, absender_firma, absender_email, betreff, empfangen, text`. Texte in natürlichem Deutsch (m08 Englisch), mit Signatur (Name, Firma, Straße, PLZ Ort, Telefon), außer wo „ohne Signatur" steht. Telefonnummern im Format `0451 / 88 12 34` (beginnen mit 0, werden pseudonymisiert). Straßen erfunden.

| ID | Absender (Firma, E-Mail aus Kontakte) | Betreff | Inhalt (Pflichtelemente) | Soll (erwartet.json) |
|---|---|---|---|---|
| m01 | Jens Brandt, Dachdeckerei Brandt GmbH | Warnschutzjacken Bestellung B-2026-04711 | Wo bleibt B-2026-04711? Autobahnbaustelle beginnt Donnerstag 18.09., ohne Jacken kein Zutritt. Kundennummer K-10234 genannt. | kategorien [bestellstatus], zust kundenservice, dringl hoch, frist 2026-09-18, bestellnummer B-2026-04711, kundennummer K-10234 |
| m02 | Martina Kessler, Elektro Kessler & Sohn GmbH & Co. KG | Größentausch Bundhosen | 4 Bundhosen A-4101 Gr. 52 aus B-2026-04688 zu klein, Tausch gegen 54, Etiketten dran, ungetragen. | [ruecksendung], kundenservice, mittel, frist null, B-2026-04688, null |
| m03 | Cem Yilmaz, Malerbetrieb Yilmaz GmbH | Reklamation bedruckte T-Shirts | Druck löst sich nach drei Wäschen an mehreren Shirts aus B-2026-04590, Fotos „im Anhang" (kein Anhang), erwartet Ersatz. | [reklamation], kundenservice, hoch, null, B-2026-04590, null; unklarheit: Fotos fehlen |
| m04 | Sabine Reuter, Metallbau Reuter AG | Stickerei Auftrag V-2026-131 | Ist die Stickerei für V-2026-131 (Bestellung B-2026-04733) durch? Jacken werden zur Messe am 22.09. gebraucht. | [veredelung], veredelung, mittel, 2026-09-22, B-2026-04733, null; veredelungsauftrag V-2026-131 |
| m05 | Frank Lorenz, Zimmerei Lorenz GmbH | Ausstattung neue Mitarbeiter | 5 neue Leute ab Oktober, Grundpaket wie letzte Bestellung (Hosen, Softshell, Schuhe, Polos), Logo wie gehabt, bitte Angebot. Kundennummer K-10802. | [angebot], vertrieb, niedrig, null, null, K-10802 |
| m06 | Petra Nowak, Gebäudereinigung Sauber & Co. GmbH | Rechnung R-2026-07731 | Kopie der Rechnung R-2026-07731 mit Kostenstelle „HH-Reinigung-12" erbeten, Frage nach Zahlungsziel. | [rechnung], buchhaltung, niedrig, null, null, null; rechnungsnummer R-2026-07731 |
| m07 | Torben Mertens, SHK Mertens GmbH | Teillieferung B-2026-04702 | Schuhe da, Softshelljacken navy XL fehlen; noch lieferbar oder Nachfolger? | [bestellstatus, verfuegbarkeit], kundenservice, mittel, null, B-2026-04702, null; artikel A-4210 navy XL |
| m08 | Ole Hansen, Tiefbau Hansen & Petersen GmbH | Order B-2026-04750 delivery date | Englisch: crew starts Monday 21 September, need everything by Friday 18 September, please confirm. | [bestellstatus], kundenservice, hoch, 2026-09-18, B-2026-04750, null |
| m09 | Daniel Adler, Kfz-Werkstatt Adler GmbH | WG: Logo für Polos | Weiterleitung mit zwei Zitatebenen („> Von: Kevin Braun"): Kollege schreibt, Stickdatei sei angehängt, Adler bittet um Freigabe für V-2026-140; kein Anhang. | [veredelung], veredelung, mittel, null, null, null; veredelungsauftrag V-2026-140; unklarheit Anhang fehlt |
| m10 | Jens Brandt, Dachdeckerei Brandt GmbH | (leer) | Ohne Anrede und Signatur: „B-2026-04711 wo bleibt die Lieferung? Rückruf 0451 / 88 12 34." | [bestellstatus], kundenservice, mittel, null, B-2026-04711, null; Kunde nur über CRM-Kontakt (E-Mail) |
| m11 | Anke Wille, Gartenbau Wille | Poloshirts mit Logo | 20 Poloshirts A-4520 grün, 10× M, 10× L, Logo auf Brust drucken, Logo „schicke ich nach", Angebot erbeten. | [veredelung, angebot], veredelung, niedrig, null, null, null |
| m12 | Petra Nowak, Gebäudereinigung Sauber & Co. GmbH | Regenjacken Rücksendung und Nachbestellung | 6 Regenjacken A-4610 Gr. M aus B-2026-04699 zu klein, Rücksendung; gleichzeitig 6× Gr. L nachbestellen, lieferbar? | [ruecksendung, verfuegbarkeit], kundenservice, mittel, null, B-2026-04699, null |
| m13 | Daniel Adler, Kfz-Werkstatt Adler GmbH | Falsche Farbe geliefert | B-2026-04761: 4 Warnschutzjacken orange statt gelb geliefert, gelb wird auf dem Hof gebraucht, bitte Austausch. | [reklamation], kundenservice, hoch, null, B-2026-04761, null |
| m14 | Miguel Ferreira, TexNorte Confecções Lda | Partnership proposal | Englisch: Textilhersteller aus Portugal bietet Fertigung an, kein Kunde. Absender-E-Mail m.ferreira@texnorte.example (nicht im CRM). | [sonstiges], kundenservice, niedrig, null, null, null |
| m15 | Martina Kessler, Elektro Kessler & Sohn GmbH & Co. KG | Lieferung B-2026-4688 | Tippfehler in der Bestellnummer (B-2026-4688 statt B-2026-04688): Polos fehlen in der Lieferung, bitte prüfen. | [bestellstatus], kundenservice, mittel, null, B-2026-4688, null; ERP kennt Nummer nicht → Hinweis |

`data/erwartet.json`: `{ "m01": {"kategorien": ["bestellstatus"], "zustaendigkeit": "kundenservice", "dringlichkeit": "hoch", "frist": "2026-09-18", "bestellnummer": "B-2026-04711", "kundennummer": "K-10234"}, ... }` für alle 15 gemäß Spalte „Soll".

---

### Task 1: Mock-Systemlandschaft `systeme/`

**Files:**
- Create: `systeme/__init__.py`, `systeme/speicher.py`, `systeme/erp.py`, `systeme/crm.py`, `systeme/mes.py`, `systeme/main.py`, `systeme/daten/*.json` (acht Dateien laut Stammdaten), `tests/test_systeme.py`

**Interfaces:**
- Produces: `systeme.main.app` (FastAPI) mit Teil-Apps unter `/erp`, `/crm`, `/mes`; Endpunkte und Antwortformen laut Spec „Systemlandschaft". Task 2 spricht sie über `httpx.ASGITransport(app=systeme.main.app)` an. Umgebungsvariable `SYSTEME_DATEN` (Ordner) überschreibt den Datenpfad; `tickets.json` ist die einzige beschriebene Datei.

- [ ] **Step 1: Stammdaten anlegen**

Acht JSON-Dateien exakt nach den Tabellen oben. Größenreihen ausschreiben (Bundhosen 48, 50, 52, 54, 56, 58, 60; Textil S, M, L, XL, XXL, 3XL; Schuhe 39 bis 48). `tickets.json` enthält `[]`.

- [ ] **Step 2: Failing Tests**

`tests/test_systeme.py` mit `TestClient(systeme.main.app)` und `monkeypatch.setenv("SYSTEME_DATEN", str(tmp_path))` nach Kopie der `daten/`:

```python
def test_erp_kunde_und_bestellung(client):
    k = client.get("/erp/kunden/K-10234").json()
    assert k["firma"] == "Dachdeckerei Brandt GmbH"
    b = client.get("/erp/bestellungen/B-2026-04711").json()
    assert b["status"] == "versendet" and b["sendungsnummer"] == "SN-7F3K9Q2L"
    assert client.get("/erp/bestellungen/B-2026-4688").status_code == 404
    letzte = client.get("/erp/kunden/K-10802/bestellungen").json()
    assert letzte[0]["bestellnummer"] == "B-2026-04120"

def test_erp_artikel_und_rechnung(client):
    a = client.get("/erp/artikel/A-4210").json()
    xl = [v for v in a["varianten"] if v["groesse"] == "XL" and v["farbe"] == "navy"][0]
    assert xl["bestand"] == 0 and xl["nachfolger"] == "A-4211"
    r = client.get("/erp/rechnungen/R-2026-07731").json()
    assert r["betrag"] == 1284.5 and r["kostenstelle"] is None

def test_crm_kontakt(client):
    k = client.get("/crm/kontakte", params={"email": "j.brandt@dachdeckerei-brandt.example"}).json()
    assert k["kundennummer"] == "K-10234"
    assert client.get("/crm/kontakte", params={"email": "niemand@example.org"}).status_code == 404

def test_crm_ticket_idempotent(client):
    body = {"externe_referenz": "m01", "kundennummer": "K-10234", "kontakt_email": "j.brandt@dachdeckerei-brandt.example",
            "betreff": "Test", "kategorien": ["bestellstatus"], "prioritaet": "hoch",
            "zustaendigkeit": "kundenservice", "zusammenfassung": "Wo bleibt B-2026-04711"}
    r1 = client.post("/crm/tickets", json=body)
    r2 = client.post("/crm/tickets", json=body)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["ticket_id"] == r2.json()["ticket_id"] == "T-2026-0001"
    assert client.patch(f"/crm/tickets/T-2026-0001", json={"status": "beantwortet"}).json()["status"] == "beantwortet"
    assert client.patch(f"/crm/tickets/T-2026-0001", json={"status": "kaputt"}).status_code == 422

def test_mes(client):
    v = client.get("/mes/veredelungsauftraege/V-2026-131").json()
    assert v["status"] == "in_produktion" and v["maschine"] == "STK-01"
    m = client.get("/mes/maschinen/STK-02").json()
    assert m["zustand"] == "stoerung"
    assert len(client.get("/mes/maschinen").json()) == 4

def test_openapi_je_system(client):
    for s in ("erp", "crm", "mes"):
        assert client.get(f"/{s}/openapi.json").status_code == 200
```

- [ ] **Step 3: Implementierung**

`systeme/speicher.py`: `DATEN = Path(os.getenv("SYSTEME_DATEN") or Path(__file__).parent / "daten")` als Funktion `daten_ordner()` (zur Laufzeit lesen, damit Tests umschalten können), `lies(name)`, `schreib(name, obj)`.

`systeme/erp.py`: `app = FastAPI(title="ERP (Mock)")`, Endpunkte wie Spec, 404 mit `detail=f"Kunde {nr} unbekannt"` usw.

`systeme/crm.py`: Pydantic `TicketNeu` (Felder wie Body), `StatusAenderung(status: Literal["offen","beantwortet","verworfen"])`. `POST /tickets`: Tickets aus `tickets.json` lesen, bei vorhandener `externe_referenz` → `JSONResponse(status_code=200, content=vorhanden)`, sonst neue ID `T-2026-{n:04d}`, `status "offen"`, `angelegt` (Zeitstempel), schreiben, 201.

`systeme/mes.py`: Endpunkte wie Spec.

`systeme/main.py`:
```python
"""Mock-Systemlandschaft: ERP, CRM und MES als drei Teil-Apps mit eigener OpenAPI-Doku.
Start: uvicorn systeme.main:app --port 8050
"""
from fastapi import FastAPI
from systeme import crm, erp, mes

app = FastAPI(title="Systemlandschaft (Mocks)")
app.mount("/erp", erp.app)
app.mount("/crm", crm.app)
app.mount("/mes", mes.app)

@app.get("/")
def start():
    return {"systeme": ["/erp/docs", "/crm/docs", "/mes/docs"]}
```

- [ ] **Step 4: Tests grün, Ruff, Commit**

Run: `python -m pytest tests/test_systeme.py -q` → alle passed; `python -m pytest -q` → alle passed (Altbestand unberührt).

```bash
git add systeme tests/test_systeme.py
git commit -m "feat(systeme): Mock-Systemlandschaft ERP, CRM, MES mit OpenAPI und idempotentem Ticket

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Adapterschicht `app/integration/`

**Files:**
- Create: `app/integration/__init__.py`, `verbindung.py`, `erp.py`, `crm.py`, `mes.py`, `fake.py`, `tests/test_integration.py`

**Interfaces:**
- Consumes: `systeme.main.app`.
- Produces:
  ```python
  class SystemNichtErreichbar(Exception): system: str; grund: str
  def baue_client(base_url: str | None = None) -> httpx.Client   # None → ASGITransport auf systeme.main.app, Basis "http://systeme"
  class ERP:  kunde(nr) -> dict|None; bestellung(nr) -> dict|None; letzte_bestellungen(kundennummer) -> list[dict]; artikel(nr) -> dict|None; rechnung(nr) -> dict|None
  class CRM:  kontakt(email) -> dict|None; ticket_anlegen(daten: dict) -> dict; ticket_status(ticket_id, status) -> dict|None
  class MES:  veredelungsauftrag(nr) -> dict|None; maschine(id) -> dict|None; maschinen() -> list[dict]
  class Systeme: erp, crm, mes  (Bündel; Systeme.aus_umgebung() liest SYSTEME_BASE_URL)
  FakeERP, FakeCRM, FakeMES, FakeSysteme  (in fake.py; Konstruktor nimmt dicts; FakeSysteme.ausgefallen: set[str] lässt Aufrufe mit SystemNichtErreichbar scheitern)
  ```
  Alle Methoden: 404 → `None`/`[]`, Verbindungsfehler/Timeout/5xx → `SystemNichtErreichbar`. Ein Wiederholungsversuch bei `httpx.ConnectError`/`httpx.ReadTimeout`.

- [ ] **Step 1: Failing Tests**

```python
import httpx, pytest
from app.integration import SystemNichtErreichbar, Systeme, baue_client
from app.integration.fake import FakeSysteme

@pytest.fixture
def systeme(tmp_path, monkeypatch):
    # Kopie der Daten, damit Tickets nicht in systeme/daten landen
    ...
    return Systeme(baue_client(None))

def test_erp_lesen(systeme):
    assert systeme.erp.kunde("K-10234")["firma"] == "Dachdeckerei Brandt GmbH"
    assert systeme.erp.bestellung("B-2026-4688") is None
    assert systeme.erp.letzte_bestellungen("K-10802")[0]["bestellnummer"] == "B-2026-04120"

def test_crm_ticket_idempotent(systeme):
    daten = {"externe_referenz": "m99", "kundennummer": None, "kontakt_email": "x@example.org", "betreff": "t",
             "kategorien": ["sonstiges"], "prioritaet": "niedrig", "zustaendigkeit": "kundenservice", "zusammenfassung": "z"}
    t1 = systeme.crm.ticket_anlegen(daten); t2 = systeme.crm.ticket_anlegen(daten)
    assert t1["ticket_id"] == t2["ticket_id"]
    assert systeme.crm.ticket_status(t1["ticket_id"], "verworfen")["status"] == "verworfen"

def test_nicht_erreichbar():
    client = httpx.Client(base_url="http://127.0.0.1:9", timeout=0.2)
    s = Systeme(client)
    with pytest.raises(SystemNichtErreichbar) as e:
        s.erp.kunde("K-10234")
    assert e.value.system == "erp"

def test_fake_ausfall():
    f = FakeSysteme(); f.ausgefallen.add("mes")
    with pytest.raises(SystemNichtErreichbar):
        f.mes.maschinen()
```

- [ ] **Step 2: Implementierung** (je Datei unter 80 Zeilen; gemeinsame Hilfsfunktion `_get(client, system, pfad, params=None)` in `verbindung.py`, die 404 → None, Retry und Fehlerabbildung kapselt).

- [ ] **Step 3: Tests grün, Commit**

```bash
git add app/integration tests/test_integration.py
git commit -m "feat(integration): Adapter für ERP, CRM, MES mit Timeout, Retry, Degradation; Fakes für Tests

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Domänenwechsel Kern (Testdaten, Extraktion, Pipeline, Server, CLI)

**Files:**
- Create: `data/mails.json`, `data/konfig.json` (`{"basisdatum": "2026-09-14", "versender": "Berufskleidung Nord GmbH"}`), `data/erwartet.json`, `tests/test_kennungen.py`
- Modify: `app/extraktion.py`, `app/antwort.py`, `app/pipeline.py`, `app/main.py`, `app/cli.py`, `app/llm_client.py`, `tests/test_extraktion.py`, `tests/test_antwort.py`, `tests/test_pipeline.py`, `tests/test_main.py`, `tests/test_echtlauf.py`
- Delete: `app/kalender.py`, `app/ersatzteile.py`, `tests/test_kalender.py`, `tests/test_ersatzteile.py`, `data/kalender.json`, `data/ersatzteile.json`, `data/ergebnisse.json`, `docs/data/*.json`, `docs/GESPRAECH.md`, alle alten Dateien in `planung/specs` und `planung/plans` außer den 2026-09-14er.

**Interfaces:**
- Produces: `Extraktion`-Schema laut Spec; `verarbeite(mail, client, heute, systeme=None) -> dict` (in Task 3 ohne Anreicherung: `systemdaten={}`, `hinweise=[]`, `integrationsfehler=[]`, `ticket=None`, `zustaendigkeit`/`dringlichkeit` vorläufig direkt aus der Extraktion); `baue_antwort(ex, systemdaten, zustaendigkeit, betreff, versender) -> str`. Task 4 füllt Anreicherung, Regeln und Ticket.

- [ ] **Step 1: Alte Domäne entfernen, Daten anlegen** (Dateien laut Tabelle; Mails nach der Mail-Tabelle mit ausformulierten Texten; `erwartet.json`).

- [ ] **Step 2: `app/llm_client.py`**: `DEFAULTS = {"ollama": {...,"model": "gpt-oss:20b", "api_key": "ollama"}, "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4.1-mini"}}`, Standardanbieter `ollama`, Fallback für unbekannte Anbieter `openai`. Docstring anpassen.

- [ ] **Step 3: `app/extraktion.py`**

```python
Kategorie = Literal["bestellstatus", "ruecksendung", "reklamation", "veredelung", "angebot", "rechnung", "verfuegbarkeit", "sonstiges"]
KATEGORIEN = list(get_args(Kategorie))

class Kunde(BaseModel): firma: str | None = None; kundennummer: str | None = None
class Ansprechpartner(BaseModel):
    anrede: str | None = None; name: str | None = None
    @field_validator("anrede", mode="before")
    @classmethod
    def _nur_herr_frau(cls, v): return v if v in ("Herr", "Frau") else None
class Bezug(BaseModel): bestellnummer: str | None = None; rechnungsnummer: str | None = None; veredelungsauftrag: str | None = None
class Artikel(BaseModel): artikelnummer: str | None = None; bezeichnung: str | None = None; groesse: str | None = None; farbe: str | None = None; menge: int | None = None
class Anliegen(BaseModel):
    kategorie: Kategorie; beschreibung: str
    @field_validator("kategorie", mode="before")
    @classmethod
    def _kategorie(cls, v): return v if v in KATEGORIEN else "sonstiges"
class Extraktion(BaseModel):
    kunde: Kunde = Kunde(); ansprechpartner: Ansprechpartner = Ansprechpartner(); bezug: Bezug = Bezug()
    artikel: list[Artikel] = []; anliegen: list[Anliegen] = []
    dringlichkeit: Literal["niedrig", "mittel", "hoch"] = "mittel"
    frist: str | None = None
    unklarheiten: list[str] = []
    @field_validator("dringlichkeit", mode="before")
    @classmethod
    def _dringlichkeit(cls, v): return v if v in ("niedrig", "mittel", "hoch") else "mittel"
    @field_validator("frist", mode="before")
    @classmethod
    def _frist(cls, v):
        try: return date.fromisoformat(v).isoformat() if v else None
        except (TypeError, ValueError): return None
```

Toleranz-Protokoll: `parse_antwort` gibt `(Extraktion, hinweise: list[str])` zurück; Hinweise entstehen, wenn ein Vorvalidator einen Wert ersetzt hat (Vergleich Rohwert gegen validierten Wert für `anrede`, `kategorie`, `dringlichkeit`, `frist`). Umsetzung: vor `model_validate` die Rohwerte prüfen und Hinweise wie `"dringlichkeit 'sehr hoch' ungültig, auf 'mittel' gesetzt"` sammeln.

Schematext ohne `a|b|c` und ohne realistische Beispielnummern:

```
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
```

Prompt (`baue_prompt(heute)`): Rolle „Kundenservice eines Versenders für Berufsbekleidung und Arbeitsschutz"; Platzhalter wörtlich übernehmen, nichts dahinter erfinden; Kennungen (Kunden-, Bestell-, Rechnungs-, Veredelungs-, Artikelnummern, Sendungsnummern) sind keine Platzhalter und werden **buchstabengetreu** übernommen, auch wenn sie ungewöhnlich oder unvollständig aussehen, nie korrigiert oder ergänzt; heute-Datum mit Wochentag; relative Angaben umrechnen; Kategorienliste mit je einem Halbsatz Bedeutung (bestellstatus: Lieferstand einer bestehenden Bestellung; ruecksendung: Rückgabe oder Größentausch; reklamation: Mangel an gelieferter Ware oder Falschlieferung; veredelung: Logo, Stick, Druck, Stickdatei, Freigabe; angebot: Preisanfrage oder Ausstattung neuer Mitarbeiter; rechnung: Rechnungskopie, Kostenstelle, Zahlungsziel; verfuegbarkeit: lieferbar, Nachfolgeartikel, Bestand; sonstiges: alles andere, auch Werbung und Lieferantenangebote); jedes eigenständige Anliegen ein Eintrag; `frist` nur, wenn der Kunde einen Termin nennt, bis zu dem er die Ware oder Antwort braucht (der Tag vor dem Einsatz zählt als Frist, wenn „ab Montag" gebraucht wird, ist Freitag die Frist nur, wenn der Kunde das so sagt; sonst der genannte Tag); bei weitergeleiteten Mails gilt die eigentliche Kundenanfrage in den Zitaten; angekündigte, aber fehlende Anhänge in `unklarheiten`; keine Erklärungen außerhalb des JSON. Kein Beispielwert, der wie eine echte Kennung aussieht.

- [ ] **Step 4: `app/antwort.py`** (Task-3-Fassung, Task 4 erweitert): `baue_antwort(ex, systemdaten, zustaendigkeit, betreff, versender)`; Anrede wie bisher; Dank; Zeilen je Anliegen (`KATEGORIE_TEXT`); Zuständigkeitssatz (`vertrieb`: „Ihr Anliegen betrifft unseren Vertrieb, die Kolleginnen und Kollegen melden sich mit einem Angebot."; `buchhaltung`: „Ihre Rechnungsfrage haben wir an die Buchhaltung weitergegeben."; `veredelung`: „Unsere Veredelung prüft Ihren Auftrag."); Unklarheiten-Liste; Gruß „Mit freundlichen Grüßen\nIhr Kundenservice\n{versender}".

- [ ] **Step 5: `app/pipeline.py`**: `verarbeite(mail, client, heute, systeme=None)`; Reihenfolge Pseudonymisierung → Extraktion (`parse_antwort` liefert Hinweise) → Rücksetzen → (Anreicherung/Regeln/Ticket kommen in Task 4; hier `zustaendigkeit="kundenservice"`, `dringlichkeit=ex["dringlichkeit"]`, `dringlichkeit_grund=None`) → Antwort. Ergebnisfelder vollständig laut Spec (leere Werte für noch nicht gefüllte).

- [ ] **Step 6: `app/main.py`**: Kalender raus; `_heute()` aus `data/konfig.json`; `erzeuge_app(client_factory=None, systeme_factory=None)`; `/api/status` zusätzlich `systeme_erreichbar` (Task 4 füllt; hier `None`); Live-Schalter unverändert; Status-Endpunkt ohne Kalenderlogik.

- [ ] **Step 7: `app/cli.py`**: Kalender raus, `heute` aus konfig, `systeme` aus `Systeme.aus_umgebung()` (Task 4 nutzt es), `--pages` kopiert `mails.json`, `ergebnisse.json`.

- [ ] **Step 8: Tests**

`tests/test_kennungen.py`:
```python
import pytest
from app.anonymisierung import anonymisiere
@pytest.mark.parametrize("kennung", ["K-10234", "B-2026-04711", "R-2026-07731", "V-2026-131", "A-4305", "SN-7F3K9Q2L", "STK-01", "DRK-02", "B-2026-4688"])
def test_kennungen_bleiben_stehen(kennung):
    text, tab = anonymisiere(f"Bitte prüfen: {kennung}, danke. Rückruf 0451 / 88 12 34.")
    assert kennung in text
    assert [t["typ"] for t in tab] == ["TELEFON"]
```

`tests/test_extraktion.py`: gültige Antwort, tolerante Fälle (`dringlichkeit: null` → mittel mit Hinweis; `anrede: "Herr|Frau"` → None; `kategorie: "Bestellstatus"` (Großschreibung) → sonstiges mit Hinweis; `frist: "nächste Woche"` → None), kein JSON → Fehler, Prompt enthält keine Zeichenkette, die auf `K-1`, `B-2026`, `R-2026`, `V-2026`, `A-4` passt, Prompt enthält alle acht Kategorien.

`tests/test_pipeline.py`: `ANTWORT` neue Form; `test_modell_sieht_keine_originale` und `test_kein_original_erreicht_das_modell` unverändert scharf (Signatur `verarbeite(mail, fake, HEUTE)`); `ERWARTETE_TYPEN` je Mail neu aus den Texten abgelesen (FIRMA und NAME überall außer m10 [nur TELEFON, FIRMA aus Absenderfeld, NAME aus Absenderfeld: prüfen, was `anonymisiere` mit `absender_name` tut, das steht im Code] und m14); Test, dass Kennungen der Mails im Prompt stehen (`B-2026-04711` in `fake.aufrufe[0]` für m01 usw.).

`tests/test_main.py`: Fixture kopiert `mails.json` und `konfig.json`; Live-Schalter-Tests bleiben; Verarbeiten/Status/Neue Mail angepasst (m16 Erwartung bleibt).

`tests/test_echtlauf.py`: Mail m01 gegen echtes Modell; erwartet Kategorie `bestellstatus`, Bestellnummer `B-2026-04711`, Firma `Dachdeckerei Brandt GmbH`.

- [ ] **Step 9: Alles grün, Commit**

```bash
git add -A
git commit -m "feat: Domänenwechsel auf Kundenanfragen eines Workwear-Versenders (Schema, Prompt, Testmails, Server, CLI)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Anreicherung, Regeln, Antwort mit Systemdaten, CRM-Ticket

**Files:**
- Create: `app/anreicherung.py`, `app/regeln.py`, `tests/test_anreicherung.py`, `tests/test_regeln.py`
- Modify: `app/antwort.py`, `app/pipeline.py`, `app/main.py`, `app/cli.py`, `tests/test_pipeline.py`, `tests/test_main.py`, `tests/test_antwort.py`

**Interfaces:**
- Consumes: `Systeme`/`FakeSysteme` aus Task 2, `Extraktion` aus Task 3.
- Produces:
  ```python
  # regeln.py
  RANGFOLGE = ["reklamation", "veredelung", "angebot", "rechnung"]
  ZUSTAENDIGKEIT = {"reklamation": "kundenservice", "veredelung": "veredelung", "angebot": "vertrieb", "rechnung": "buchhaltung"}
  def zustaendigkeit(kategorien: list[str]) -> str
  def werktage_bis(heute: date, frist: date) -> int          # Mo–Fr, heute zählt nicht
  def dringlichkeit(ex: dict, heute: date) -> tuple[str, str | None]   # (wert, grund)
  # anreicherung.py
  def anreichere(ex: dict, mail: dict, systeme, heute: date) -> tuple[dict, list[str], list[str], list[str]]
      # → (systemdaten, hinweise, integrationsfehler, neue_unklarheiten)
  def lege_ticket_an(ergebnis: dict, mail: dict, systeme) -> dict | None   # idempotent über externe_referenz=mail_id
  ```

- [ ] **Step 1: Failing Tests `tests/test_regeln.py`**

```python
from datetime import date
from app.regeln import dringlichkeit, werktage_bis, zustaendigkeit
HEUTE = date(2026, 9, 14)
def test_zustaendigkeit_rangfolge():
    assert zustaendigkeit(["bestellstatus"]) == "kundenservice"
    assert zustaendigkeit(["veredelung", "angebot"]) == "veredelung"
    assert zustaendigkeit(["angebot"]) == "vertrieb"
    assert zustaendigkeit(["rechnung", "bestellstatus"]) == "buchhaltung"
    assert zustaendigkeit(["reklamation", "veredelung"]) == "kundenservice"
    assert zustaendigkeit([]) == "kundenservice"
def test_werktage():
    assert werktage_bis(HEUTE, date(2026, 9, 18)) == 4
    assert werktage_bis(HEUTE, date(2026, 9, 22)) == 6
    assert werktage_bis(HEUTE, date(2026, 9, 14)) == 0
def test_dringlichkeit_regeln():
    assert dringlichkeit({"dringlichkeit": "mittel", "frist": "2026-09-17", "anliegen": []}, HEUTE) == ("hoch", "Frist 2026-09-17 liegt innerhalb von 3 Werktagen")
    assert dringlichkeit({"dringlichkeit": "mittel", "frist": "2026-09-18", "anliegen": []}, HEUTE) == ("mittel", None)
    assert dringlichkeit({"dringlichkeit": "niedrig", "frist": None, "anliegen": [{"kategorie": "reklamation", "beschreibung": ""}]}, HEUTE) == ("hoch", "Reklamation")
    assert dringlichkeit({"dringlichkeit": "hoch", "frist": None, "anliegen": []}, HEUTE) == ("hoch", None)
```

Achtung m01: Frist 2026-09-18 sind 4 Werktage ab dem 14.09., also **nicht** innerhalb von 3. Das Soll `hoch` für m01 und m08 kommt aus der Modell-Dringlichkeit (Baustelle ohne Zutritt, Kolonne wartet), nicht aus der Fristregel. Die Fristregel greift bei 3 Werktagen oder weniger.

- [ ] **Step 2: Failing Tests `tests/test_anreicherung.py`** mit `FakeSysteme` (befüllt aus `systeme/daten/*.json`):
  - m01: Kontakt per E-Mail → Kunde K-10234, Bestellung B-2026-04711 mit `status versendet`; keine Hinweise.
  - m15: Bestellnummer B-2026-4688 unbekannt → `neue_unklarheiten` enthält „Bestellnummer B-2026-4688 ist im ERP nicht bekannt", `hinweise` ebenso; Kontakt gefunden.
  - m08: Liefertermin 2026-09-19 nach Frist 2026-09-18 → Hinweis „Liefertermin 2026-09-19 liegt nach der genannten Frist 2026-09-18".
  - m04: Veredelung V-2026-131 geladen, Maschine STK-01 `laeuft`; kein Hinweis. Variante mit Maschine `stoerung` (Fake manipuliert) → Hinweis „Maschine STK-01 meldet Störung, geplantes Ende gefährdet".
  - Bestellung gehört anderem Kunden (Fake: Kontakt K-10311 fragt B-2026-04711) → Hinweis „Bestellung B-2026-04711 gehört zu Kunde K-10234, Absender ist K-10311".
  - `ausgefallen={"erp"}` → `integrationsfehler == ["erp: ..."]`, übrige Systeme geladen, kein Abbruch.
  - `lege_ticket_an` zweimal → gleiche `ticket_id`.

- [ ] **Step 3: Implementierung**

`anreichere`: Kontakt via `crm.kontakt(mail["absender_email"])`; Kundennummer = aus Extraktion oder Kontakt; `erp.kunde`, `erp.bestellung(bezug.bestellnummer)`, `erp.letzte_bestellungen(kundennummer)` nur bei Kategorie `angebot`, `erp.rechnung`, `erp.artikel` je genannter Artikelnummer (Verfügbarkeit der genannten Größe/Farbe als `artikel: [{artikelnummer, groesse, farbe, bestand, nachfolger}]`), `mes.veredelungsauftrag(bezug.veredelungsauftrag)` und Maschine dazu. Jeder Systemaufruf in `try/except SystemNichtErreichbar` → Eintrag `f"{e.system}: {e.grund}"`. Plausibilitätsregeln wie in den Tests.

`lege_ticket_an`: Body aus Ergebnis (`externe_referenz=mail_id`, `kategorien`, `prioritaet=dringlichkeit`, `zustaendigkeit`, `zusammenfassung` = erste Anliegen-Beschreibung oder Betreff). Bei `SystemNichtErreichbar` → `None` und Eintrag in `integrationsfehler`.

`antwort.py` erweitern: bestellstatus mit Bestellung → „Ihre Bestellung {nr} ist am {liefertermin} bei Ihnen" / „wurde am ... versendet, Sendungsnummer ..., voraussichtliche Zustellung ..." / „wird gerade kommissioniert, geplanter Liefertermin ..."; teilgeliefert: offene Positionen auflisten; verfuegbarkeit mit Artikel: Bestand oder Nachfolger; veredelung mit MES: Status, Maschine, geplantes Ende, Hinweis; rechnung mit Rechnung: Betrag, fällig; reklamation: Entschuldigung, Ersatz/Abholung wird organisiert; ruecksendung: Rücksendeschein folgt; Hinweise mit Kundenbezug (Liefertermin nach Frist) als eigener Satz. Ohne Systemdaten (Ausfall) generische Formulierung „Wir prüfen den Stand und melden uns heute noch."

`pipeline.py`: nach Rücksetzen `anreichere`, `regeln.zustaendigkeit`/`dringlichkeit`, Antwort, `lege_ticket_an`; Status `pruefung_noetig`, wenn `extraktion_fehler` oder `integrationsfehler`. Signatur `verarbeite(mail, client, heute, systeme)`.

`main.py`: `systeme_factory` (Standard `Systeme.aus_umgebung`), `/api/status` prüft `systeme.mes.maschinen()` in try/except → `systeme_erreichbar` bool; Statusänderung ruft `crm.ticket_status` (freigegeben → beantwortet, abgelehnt → verworfen, offen → offen), Fehler dort → 502 mit Meldung, Status im Ergebnis bleibt unverändert.

- [ ] **Step 4: Tests, Commit**

`tests/test_pipeline.py` ergänzen: Ergebnis von m01 mit FakeSysteme hat `systemdaten["bestellung"]["status"] == "versendet"`, `ticket["ticket_id"]`, `zustaendigkeit == "kundenservice"`; Ausfall ERP → `status == "pruefung_noetig"`, Antwort enthält „Wir prüfen den Stand". `tests/test_main.py`: Freigabe setzt Ticket `beantwortet` (über FakeSysteme prüfen).

```bash
git add -A
git commit -m "feat: Anreicherung aus ERP, CRM, MES; Regeln für Zuständigkeit und Dringlichkeit; Antwort mit Systemdaten; idempotentes CRM-Ticket

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Modellvergleich `app/vergleich.py`

**Files:** Create `app/vergleich.py`, `tests/test_vergleich.py`; Output `data/vergleich.json`, `docs/modellvergleich.md`.

**Interfaces:**
- `python -m app.vergleich --modelle gpt-oss:20b,qwen2.5:14b-instruct [--anbieter ollama] [--ausgabe docs/modellvergleich.md]`
- `bewerte(ergebnisse: dict[str, dict], erwartet: dict) -> dict` mit Trefferzahlen je Feld (`kategorien` als Mengenvergleich, `zustaendigkeit`, `dringlichkeit`, `bestellnummer`, `kundennummer`, `frist`), `schemafehler`, `mittlere_dauer_ms`.
- `schreibe_tabelle(bewertungen: dict[str, dict], pfad)` → Markdown-Tabelle mit Kopf „Modell | Kategorien | Zuständigkeit | Dringlichkeit | Bestellnummer | Kundennummer | Frist | Schemafehler | Ø Dauer" und Zeile „Soll-Werte: data/erwartet.json, n = 15, Stand {Datum}".
- Der Lauf je Modell nutzt `LLMClient` mit überschriebenem `model`, führt Pseudonymisierung, Extraktion, Rücksetzen und Regeln aus (Funktion `pipeline.extrahiere_und_bewerte(mail, client, heute)` als kleiner öffentlicher Ausschnitt der Pipeline, ohne Systeme und Ticket).

- [ ] Tests mit `FakeClient`: perfekte Antwort → alle Treffer 15; eine falsche Kategorie → 14; Tabelle enthält Modellnamen und Zahlen. Commit `feat(vergleich): Modellvergleich gegen Soll-Werte, Markdown-Tabelle`.

---

### Task 6: Oberfläche `docs/index.html`

- Kopfzeile: Versender, Anbieter/Modell, Live-Badge (unverändert).
- Liste: Absender, Firma, Betreff, Statusbadge, Zuständigkeitsbadge, Dringlichkeit.
- Detail links: Roh-Text/Pseudonym-Text umschaltbar, Platzhaltertabelle, extrahierte Felder (Kunde, Ansprechpartner, Bezug, Artikel, Anliegen, Frist, Dringlichkeit mit Grund, Unklarheiten, Extraktionshinweise).
- Detail Mitte „Systemdaten": ERP (Kunde, Bestellung mit Status, Sendungsnummer, Liefertermin, Positionen; Rechnung; Artikelverfügbarkeit), MES (Auftrag, Status, Maschine mit Zustand), CRM (Kontakt, Ticket-ID und Status). Hinweise gelb, Integrationsfehler rot.
- Rechts: Antwortentwurf, Freigeben/Ablehnen/Neu verarbeiten, Fußnote (Anbieter, Modell, Dauer).
- Statischer Modus aus `docs/data/`. Keine Bibliotheken. Alle Werte per `esc()`.
- Prüfung: `python -m http.server 8041 -d docs` mit Beispiel-`docs/data` aus einem FakeClient-Lauf (Task 6 legt dafür vorübergehend Testdaten an, entfernt sie wieder; die echten kommen in Task 8). Commit `feat(ui): Oberfläche für Kundenanfragen mit Systemdaten`.

---

### Task 7: Betrieb (Docker, Compose, CI, Terraform, Render, Fly, .env.example, run-Skripte)

- `Dockerfile`: zusätzlich `COPY --chown=app:app systeme/ systeme/`; Kommentar, dass dasselbe Image beide Kommandos kann.
- `docker-compose.yml`: Dienst `systeme` (gleiches Image, `command: ["sh","-c","exec python -m uvicorn systeme.main:app --host 0.0.0.0 --port 8050"]`, Port 8050 nur intern, Healthcheck auf `/`), Dienst `app` mit `SYSTEME_BASE_URL=http://systeme:8050`, `depends_on`.
- `.dockerignore`: `systeme/daten/tickets.json` **nicht** ausschließen (leere Datei muss mit), `planung` weiter ausgeschlossen.
- `ci.yml`: Rauchtest startet beide Container in einem Docker-Netz, prüft `/api/status` mit `"systeme_erreichbar":true` und 403; Image-Name `ghcr.io/${{ github.repository }}`.
- Terraform: zweiter `container { name = "systeme" image = var.container_image command = ["sh","-c","exec python -m uvicorn systeme.main:app --host 0.0.0.0 --port 8050"] cpu 0.25 memory 0.5Gi }`, App-Env `SYSTEME_BASE_URL=http://localhost:8050`; Namen `kanfragen`-Präfix (`name_prefix` Standard `kanfragen`), Image `ghcr.io/dangtu1190-tech/kundenanfragen-assistent:latest`; tftest zusätzlich: genau zwei Container, nur Port 8040 im Ingress.
- `render.yaml`: Render-Free-Plan erlaubt einen Dienst je Blueprint-Eintrag; Systemlandschaft läuft dort **im Prozess** (kein `SYSTEME_BASE_URL`), Kommentar dazu. `fly.toml`: ebenso im Prozess.
- `.env.example`: Ollama-Standard, `SYSTEME_BASE_URL=` leer mit Kommentar „leer = Systemlandschaft im Prozess".
- `run.bat`/`run.sh`: nur die App (Systeme im Prozess).
- Prüfung: `docker compose up --build -d`, `curl /api/status` zeigt `systeme_erreichbar: true`, `curl http://localhost:8040/` 200, `docker compose down`; `terraform fmt -check`, `validate`, `test` grün. Commit `build/ci/infra: zwei Dienste aus einem Image, Sidecar in Azure, Namen umgestellt`.

---

### Task 8: Echtlauf mit Ollama und Modellvergleich

Voraussetzung: Ollama läuft lokal (`curl http://localhost:11434/api/version`), Modelle `gpt-oss:20b` und `qwen2.5:14b-instruct` vorhanden.

- `LLM_PROVIDER=ollama LLM_MODEL=gpt-oss:20b python -m app.cli --neu --pages` (Systemlandschaft im Prozess; vorher `systeme/daten/tickets.json` auf `[]` setzen, danach wieder auf `[]` setzen, damit keine Tickets im Repo stehen).
- Jede Mail gegen `erwartet.json` prüfen (`python -m app.vergleich --modelle gpt-oss:20b`); bei systematischen Fehlern Prompt nachschärfen (nur Prompt, kein Schema-Umbau), erneut laufen lassen. Ziel: kein Schemafehler, Kategorien mindestens 13 von 15, Bestellnummer 15 von 15. Ergebnis ehrlich dokumentieren, auch wenn das Ziel verfehlt wird.
- `python -m app.vergleich --modelle gpt-oss:20b,qwen2.5:14b-instruct` → `docs/modellvergleich.md`, `data/vergleich.json`.
- `python -m pytest -q` mit `LLM_API_KEY=ollama LLM_PROVIDER=ollama LLM_MODEL=gpt-oss:20b` → Echtlauf-Test grün.
- Commit `feat: Echtlauf mit gpt-oss:20b, Ergebnisse für die Browser-Demo, Modellvergleich`.

---

### Task 9: README und Gesprächsleitfaden

README-Gliederung: 1 Was das ist; 2 Demo im Browser (Pages-URL `https://dangtu1190-tech.github.io/kundenanfragen-assistent/`); 3 Architektur (ASCII-Bild der sieben Schritte und der drei Systeme, Hinweis auf OpenAPI unter `/erp/docs` usw.); 4 Pseudonymisierung (Tabelle wie bisher, Kennungsregel, ehrliche Grenzen übernommen); 5 Integrationsentscheidungen (Adapter mit Timeout/Retry, Degradation statt Abbruch, Idempotenz über externe Referenz, Regeln im Code statt im Modell, im Prozess gegen HTTP, Secrets nur über Umgebung/Key Vault); 6 Modellvergleich (Tabelle aus `docs/modellvergleich.md`, Lehren aus dem Vergleich); 7 Lokal starten (`docker compose up --build`, `run.bat`, Ollama-Hinweis); 8 Modellzugriff (Ollama Standard, OpenAI-kompatibel als Reserve, kein Langdock); 9 Testdaten (15 Mails, Tabelle kurz); 10 Tests; 11 GitHub Pages; 12 Betrieb (aus dem Vorgänger übernommen, Sidecar ergänzt); 13 Bewusst nicht enthalten; 14 Wie ich das in einem Betrieb umsetzen würde (ERP-API statt Mock, MES über OPC UA/MQTT, Ereignisse statt Polling, Warteschlange, Schema-Registry, Beobachtbarkeit, Freigabe im gewohnten Werkzeug).

`docs/GESPRAECH.md`: zehn wahrscheinliche Fragen mit Kurzantworten (Warum Mocks; warum Regeln statt Modell; wie idempotent; was passiert bei Ausfall; warum Ollama; Kosten in der Cloud; Grenzen; was fehlt für Produktion; wie MES real anbinden; warum keine Datenbank).

Badge-URL `https://github.com/dangtu1190-tech/kundenanfragen-assistent/actions/workflows/ci.yml/badge.svg`. Commit `docs: README und Gesprächsleitfaden für den Kundenanfragen-Assistenten`.
