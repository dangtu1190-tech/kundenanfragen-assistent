# Cloud-fähiger Deployment-Weg ohne laufende Kosten – Design

Stand: 11.09.2026. Branch `cloud-deployment`, Basis `origin/main` (0ae6e3b).

## Ziel

Der Serviceanfragen-Assistent bekommt einen nachvollziehbaren, reproduzierbaren
Deployment-Weg (Container, CI, Infrastruktur als Code), ohne dass irgendetwas
ausgerollt wird oder laufend Geld kostet. Die Anwendungslogik bleibt unverändert.

## Nicht-Ziele

- Kein Refactoring, keine „Verbesserung" der Anwendung.
- Kein `terraform apply`, weder lokal noch in der Pipeline.
- Kein Ausrollen auf Render oder Fly.io; nur Konfigurationsdateien.
- Keine Verwendung des Langdock-Zugangs des Arbeitgebers, nirgends.

## Bestandsaufnahme (belegt)

- FastAPI-Server `app/main.py`, Start `uvicorn app.main:app --port 8040`,
  Oberfläche `docs/index.html`, Daten als JSON in `data/`. Der Server
  **schreibt** in `data/` (Status, Kalender, neue Mails).
- Konfiguration über `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`;
  eine `.env` im Projektordner wird per `setdefault` eingelesen.
- 75 Testfunktionen; `test_echtlauf.py` skippt ohne `LLM_API_KEY`.
  Der zu zeigende Test: `tests/test_pipeline.py::test_kein_original_erreicht_das_modell`
  (schärfere Variante von `test_modell_sieht_keine_originale`).
- Git-Historie enthält keinen Schlüsselwert (geprüft: `LLM_API_KEY=` nur leer in
  `.env.example`; keine Treffer für `sk-…`, `Bearer …`, `BEGIN … KEY`, `ghp_…`).
- Werkzeuge lokal: Python 3.12.10, Docker 29.7.2 mit Compose 5.5, Terraform 1.16.2
  (als Binary im Scratchpad), Ruff 0.16.7 (Scratch-venv). Kein `gh`, kein `az`.
- Ruff 0.16 aktiviert standardmäßig Stilregeln (ISC, FURB, DTZ, RUF, …), die am
  bestehenden Code 29 Treffer liefern. Mit der Regelmenge `E4, E7, E9, F` bleibt
  genau ein Treffer: ungenutzter Import `Path` in `tests/test_main.py`.
- Render: Free-Plan für Web Services vorhanden (750 Instanzstunden/Monat,
  Spin-down nach 15 Minuten ohne Anfragen, flüchtiges Dateisystem).
  Fly.io: Preisseite nennt keinen kostenlosen Plan mehr; gestoppte Maschinen
  kosten Speicher (0,15 $ je GB und Monat). Beides per Abruf der Doku-Seiten am
  11.09.2026 geprüft, nicht durch ein Konto.

## Entscheidungen

### 1. Live-Schalter (einziger Eingriff in die Anwendung)

Der Verarbeiten-Endpunkt (`POST /api/mails/{id}/verarbeiten`) ruft heute immer das
Modell. Ohne Schlüssel scheitert der Aufruf zwar, überschreibt aber das
aufgezeichnete Ergebnis mit `pruefung_noetig`. Für eine öffentliche Instanz ist
das nicht tragbar. Deshalb:

- Umgebungsvariable `LIVE_MODELLAUFRUFE`, Standard aus. Werte `1`, `true`, `ja`,
  `on` (Groß/Klein egal) schalten ein; alles andere ist aus.
- Ist der Schalter aus, antwortet der Verarbeiten-Endpunkt mit HTTP 403 und
  einer deutschen Meldung; Ergebnisse und Kalender bleiben unangetastet.
- `GET /api/status` liefert zusätzlich `live_modellaufrufe: bool`.
- `docs/index.html` zeigt bei ausgeschaltetem Live-Pfad ein Badge in der
  Kopfzeile und deaktiviert die Knöpfe „Alle verarbeiten", „Neu verarbeiten"
  und „Neue Mail" (deren Absenden würde sofort verarbeiten).
- Der Schalter wird zur Laufzeit je Anfrage gelesen, nicht beim Start, damit
  die Tests ihn per `monkeypatch` umschalten können.
- Lokaler Betrieb: `.env.example` bekommt `LIVE_MODELLAUFRUFE=0`; wer lokal
  live rechnen will, setzt `1`. Das ist die bewusste Verhaltensänderung: „aus"
  ist der sichere Standard.

Begründung für den Standard „aus": Bei einer öffentlich erreichbaren Instanz
zahlt der hinterlegte Schlüssel für jeden Besucher, der auf „Verarbeiten" klickt.

### 2. Container

- `Dockerfile`, zwei Stufen auf `python:3.12-slim`: Stufe 1 installiert die
  Abhängigkeiten nach `/install`, Stufe 2 kopiert nur dieses Prefix, `app/`,
  `data/` und `docs/index.html`. Non-root-User `app` (UID 10001), `data/` gehört
  ihm, weil der Server dort schreibt. `HEALTHCHECK` fragt `/api/status` per
  Python-Standardbibliothek ab (kein curl im Slim-Image). Port kommt aus `PORT`
  (Standard 8040), weil Render und Fly ihn selbst setzen. `CMD` per `exec`,
  damit uvicorn PID 1 ist und Signale bekommt.
- `pytest` landet mit im Image, weil `requirements.txt` es enthält. Eine zweite
  Requirements-Datei wäre Umbau am Projekt; nicht gemacht, im README erwähnt.
- `.dockerignore` schließt Git, Planung, Tests, Terraform, Pages-Daten, `.env`
  und Caches aus.
- `docker-compose.yml`: ein Dienst, Port 8040, `.env` optional (`required: false`).
- `.env.example`: alle Variablen, Werte leer oder unkritisch, mit
  `LIVE_MODELLAUFRUFE=0` und `PORT=8040`.
- `ruff.toml` mit Regelmenge `E4, E7, E9, F`, damit der Linter keine Umbauten
  am bestehenden Code erzwingt. Der eine Treffer (ungenutzter Import in einem
  Test) wird entfernt.

### 3. CI (GitHub Actions)

`.github/workflows/ci.yml`, läuft bei jedem Push und Pull Request, drei Jobs:

1. **Tests und Linter**: Python 3.12, `pip install -r requirements.txt ruff`,
   `ruff check app tests`, dann ein eigener, benannter Schritt nur mit den
   beiden Pseudonymisierungstests, dann die ganze Suite. Schlägt der benannte
   Schritt fehl, ist der Lauf rot.
2. **Docker-Image** (braucht Job 1): `docker build`, Rauchtest (Container
   starten, `/api/status` muss 200 liefern und `live_modellaufrufe: false`
   enthalten, `POST …/verarbeiten` muss 403 liefern), danach Push nach
   `ghcr.io/<owner>/<repo>` mit `latest` und `sha-…`, aber nur bei Push auf
   `main`. Anmeldung mit `GITHUB_TOKEN`, `permissions: packages: write`.
3. **Terraform**: `fmt -check`, `init -backend=false`, `validate`, `terraform
   test` (Plan gegen Mock-Provider, Details unter 4). Kein `apply`.

Statusbadge im README.

### 4. Infrastruktur als Code (Terraform, nur Plan)

Ordner `infra/azure/`, Provider `azurerm ~> 4.0`, Terraform `>= 1.7`
(wegen `mock_provider`).

Ressourcen: Resource Group, Log Analytics Workspace (Tagesquote 0,5 GB als
Kostendeckel), Container Apps Environment, User-Assigned Managed Identity,
Key Vault (RBAC), zwei Rollenzuweisungen (Ausrollender: Secrets Officer, App:
Secrets User), Key-Vault-Secret als **Platzhalter** mit `ignore_changes`,
Container App.

- Der echte Schlüssel steht nie in Code, Variablen oder State: Terraform legt
  nur den Platzhalter an; der Wert wird danach mit `az keyvault secret set`
  gesetzt. `ignore_changes` verhindert, dass ein späteres `apply` ihn
  zurücksetzt.
- Container App: `identity` UserAssigned, `secret` als Key-Vault-Referenz über
  diese Identität, `LLM_API_KEY` ausschließlich aus `secret_name`.
- Ingress extern, `allow_insecure_connections = false` (nur HTTPS).
- `min_replicas = 0` mit Kommentar (Scale-to-zero; bei > 0 laufen Replikate
  rund um die Uhr und kosten auch ohne Traffic), `max_replicas` als Variable
  mit Obergrenze 10, Standard 2. CPU 0,25, Speicher 0,5 GiB.
- User-Assigned statt System-Assigned Identity, weil die App das Secret schon
  bei der Erstellung referenziert; eine System-Identität existiert erst danach.
- Variablen in `variables.tf`, Beispiel in `terraform.tfvars.example`.
- `tests/plan.tftest.hcl`: `mock_provider "azurerm" {}` und `command = plan`.
  Läuft ohne Azure-Konto. Assertions: `min_replicas == 0`, `max_replicas <= 10`,
  Ingress extern und nur HTTPS, `LLM_API_KEY` nur aus dem Secret,
  `LIVE_MODELLAUFRUFE` standardmäßig `"0"`.

Ehrliche Grenze: Die Konfiguration wurde nie angewendet. Ein erstes `apply`
findet erfahrungsgemäß Kleinigkeiten (RBAC-Verzögerung nach Rollenzuweisung,
weltweit eindeutiger Key-Vault-Name, Sichtbarkeit des GHCR-Pakets). Das steht
so im README.

### 5. Öffentliche Demo (vorbereitet, nicht ausgerollt)

- `render.yaml`: Web Service, `runtime: docker`, `plan: free`, Region Frankfurt,
  Healthcheck `/api/status`, `autoDeploy: false`, `LIVE_MODELLAUFRUFE=0`,
  `LLM_API_KEY` mit `sync: false` (nur im Dashboard, nie in der Datei).
- `fly.toml`: `min_machines_running = 0`, `auto_stop_machines = "stop"`,
  `force_https`, kleinste VM, mit Warnhinweis, dass Fly.io keinen kostenlosen
  Plan mehr ausweist. Empfehlung im README: Render.

### 6. Dokumentation

README: Badge unter der Überschrift, Abschnitt 5 um den Schalter ergänzt,
Abschnitt 8 mit aktueller Testzahl, neuer Abschnitt „Betrieb" (lokal starten,
Image bauen und Herkunft, Cloud-Deployment und warum nicht ausgerollt,
Scale-to-zero-Entscheidung, Live-Pfad standardmäßig aus, Langdock-Regel,
Grenzen), Abschnitt „Bewusst nicht enthalten" angepasst (Deployment-Weg
existiert jetzt, ausgerollt ist nichts).

## Tests

- Neue Tests in `tests/test_main.py`: Schalter aus → 403, Ergebnis unverändert,
  Status meldet `false`; Schalter an → wie bisher. Bestehende Fixture setzt den
  Schalter an, damit die vorhandenen Tests unverändert bleiben.
- Docker: Image bauen, Container starten, `/api/status` und 403 prüfen (lokal
  und in der Pipeline).
- Terraform: `fmt -check`, `validate`, `test` lokal mit Binary 1.16.2 grün.
- Pipeline selbst kann lokal nicht ausgeführt werden; jeder Schritt wird lokal
  mit demselben Befehl nachvollzogen.
