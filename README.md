# Serviceanfragen-Assistent

[![CI](https://github.com/dangtu1190-tech/serviceanfragen-assistent/actions/workflows/ci.yml/badge.svg)](https://github.com/dangtu1190-tech/serviceanfragen-assistent/actions/workflows/ci.yml)

## 1. Was das ist

Ein Assistent, der eingehende Servicemails eines Sonderanlagenbauers (Vakuumöfen
für Metallurgie und Wärmebehandlung) liest, die relevanten Angaben strukturiert
herauszieht und den Einsatz eines Servicetechnikers vorschlägt, samt
Antwortentwurf zur Freigabe. Abgedeckt sind Wartung, Störung, Ersatzteil,
Reklamation und Angebot. Eigenprojekt, Demo mit erfundenen Testdaten,
entstanden für Bewerbungen.

## 2. Demo im Browser ohne Installation

`https://dangtu1190-tech.github.io/serviceanfragen-assistent/`

Das ist der statische Modus: vorberechnete Ergebnisse aus `docs/data/`,
keine Modellaufrufe. Alle 15 Testmails lassen sich anklicken und zeigen den
kompletten Ablauf inklusive Pseudonymisierung, Extraktion und
Einsatzvorschlag, so wie sie beim letzten Echtlauf entstanden sind. Für eine
neue Mail „live" gegen ein Modell rechnen zu lassen, geht nur lokal
(Abschnitt 5).

## 3. Das Kernstück: Pseudonymisierung vor dem Modellaufruf

Bevor eine Mail an das Modell geht, ersetzt eine deterministische
Regex-Erkennung personenbezogene Angaben durch Platzhalter. Das Modell sieht
nie den Original-Text. Es ist bewusst Pseudonymisierung und keine
Anonymisierung: die Zuordnungstabelle bleibt lokal und macht den Schritt
umkehrbar, an das Modell gehen ausschließlich die Platzhalter. (Das Modul
heißt aus der Entstehungsgeschichte heraus weiterhin `anonymisierung.py`.)

| Typ | Beispiel | Platzhalter |
|---|---|---|
| E-Mail | `f.lindemann@hartmann-wb.example` | `[EMAIL_1]` |
| Firma | `Hartmann Wärmebehandlung GmbH` | `[FIRMA_1]` |
| Telefon | `06661 / 90 12 34` | `[TELEFON_1]` |
| Adresse | `Am Gewerbepark 12` | `[ADRESSE_1]` |
| Ort | `36381 Schlüchtern` | `[ORT_1]` |
| Name | `Frank Lindemann` | `[NAME_1]` |

Dieselbe Angabe bekommt immer denselben Platzhalter, auch bei
unterschiedlicher Schreibweise (Groß-/Kleinschreibung, Namensteile). Die
Antwort des Modells enthält deshalb dieselben Platzhalter. Erst danach
werden sie anhand der Zuordnungstabelle wieder auf die Originalwerte
zurückgesetzt, rekursiv über das ganze JSON-Ergebnis.

### Warum diese Felder und keine anderen

Anlagen- und Seriennummern, Fehlercodes und Anlagentypen werden bewusst nicht
ersetzt. Sie sind keine personenbezogenen Daten, und das Modell braucht sie
wörtlich, um die Anfrage der richtigen Anlage zuzuordnen. Firmennamen werden
dagegen ersetzt, aber nicht aus Datenschutzgründen: sie berühren
Geschäftsgeheimnisse, denn wer welche Anlage betreibt und welche Störungen
sie hat, ist selbst schützenswert. Die Auswahl der zu ersetzenden Felder ist
damit eine Entscheidung je Anwendungsfall, keine Pauschalregel, die sich
unbesehen auf andere Domänen übertragen ließe.

Ehrliche Grenzen: Namen, die im Fließtext ohne Anrede, Absenderfeld oder
Signatur auftauchen, werden nicht erkannt. Signaturen, die durchgehend klein
geschrieben sind, ebenfalls nicht, denn die Namenszeile wird über den
Großbuchstaben am Wortanfang gefunden. Teilen sich zwei erkannte Personen
einen Nachnamen, bleibt ein allein stehender Nachname stehen. Er ist nicht
zuordenbar, und ein geratener Platzhalter setzte die falsche Person wieder
ein. Umgekehrt gilt: ist nur eine Person mit diesem Nachnamen bekannt, wird
auch der allein stehende Nachname ersetzt und beim Zurücksetzen zum vollen
Namen aufgefüllt. Orte ohne vorangestellte PLZ bleiben stehen, und
Ortsnamen mit Zusatz wie „am Main" bleiben teilweise sichtbar: maskiert wird
„60437 Frankfurt", das „am Main" bleibt stehen. Ein Muster, das den Zusatz
mitnimmt, verschluckt sonst gewöhnlichen Fließtext und verdeckt damit eine
Anrede, hinter der ein Name steht. Firmennamen ohne Rechtsform im Namen
(also ohne GmbH, AG, KG und ähnliche Endungen) werden nur erkannt, wenn sie
als Absenderfirma aus den Mail-Metadaten bekannt sind. Taucht ein solcher
Name nur im Fließtext auf, etwa in einer Weiterleitung, bleibt er stehen.

## 4. Pipeline, Technikerkalender, Ersatzteilhinweise

```
Mail
  │
  ▼
1. Pseudonymisierung – personenbezogene Angaben durch Platzhalter ersetzen
  │
  ▼
2. Extraktion        – Modellaufruf liefert strukturiertes JSON (Kunde,
  │                     Ansprechpartner, Anlage, Anliegen, Dringlichkeit,
  │                     Wunschzeitraum, Zuständigkeit)
  ▼
3. Terminsuche        – freien Servicetechniker mit passender Qualifikation
  │                     im Kapazitätskalender finden
  ▼
4. Antwortentwurf     – deutscher Text aus einer festen Vorlage, nicht vom
                         Modell
```

Das Modell liefert ausschließlich das JSON aus Schritt 2. Der Antworttext
in Schritt 4 kommt aus einer Vorlage im Code, damit er vorhersagbar bleibt.

Der Technikerkalender kennt fünf Servicetechniker mit je ein bis zwei
Qualifikationen (Elektrik, Vakuumtechnik, Steuerung, Mechanik). Die
benötigte Qualifikation wird aus Kategorie und Beschreibung der Anliegen
abgeleitet, zum Beispiel führt ein genannter Fehlercode oder ein Hinweis
auf die Steuerung zur Qualifikation Steuerung. Bei Dringlichkeit
„Stillstand" (Produktion steht oder eine Charge sitzt im Ofen fest) wird
der Einsatz vorgezogen: gesucht wird der erste freie Tag ab heute statt im
Wunschzeitraum, mit dem Hinweis „Produktionsstillstand, Einsatz
vorgezogen." Geht es um eine Neuanlage, einen Kauf oder ein Angebot für
eine neue Anlage, ist die Zuständigkeit Vertrieb, und es wird kein Termin
gesucht. Reine Ersatzteilanliegen ohne weiteren Servicebedarf bekommen
ebenfalls keinen Termin. Der Vorschlag reserviert nichts, erst die Freigabe
belegt den Techniker. Ablehnen oder erneutes Verarbeiten geben ihn wieder
frei.

Für Anliegen der Kategorie Ersatzteil liefert ein kleiner Katalog
Verfügbarkeitshinweise (etwa „ab Lager" oder „Lieferzeit ca. 3 Wochen"),
die im Antwortentwurf mit aufgeführt werden. Ohne Treffer im Katalog steht
dort „Verfügbarkeit wird geprüft".

## 5. Lokal starten

```
copy .env.example .env
```

In der `.env` den Schlüssel eintragen (`LLM_API_KEY`), dann:

- Windows: `run.bat`
- Linux/Mac: `sh run.sh`

Neue Modellaufrufe („Verarbeiten", „Neue Mail") sind nur möglich, wenn in der
`.env` zusätzlich `LIVE_MODELLAUFRUFE=1` steht. Standard ist aus: der Server
zeigt dann die aufgezeichneten Ergebnisse, Freigabe und Ablehnung funktionieren,
der Verarbeiten-Endpunkt antwortet mit HTTP 403 (Abschnitt 10).

Danach im Browser `http://localhost:8040` öffnen. Ohne `.env` starten die
Skripte den Server trotzdem, mit einem Hinweis: die 15 vorberechneten
Ergebnisse aus `data/` lassen sich ansehen, ein neuer Modellaufruf scheitert
am fehlenden Schlüssel und endet sichtbar als `pruefung_noetig`.

Den statischen Modus selbst ansehen (ohne Server), zum Beispiel um
`docs/index.html` unverändert von der Festplatte zu prüfen:

```
python -m http.server 8041 -d docs
```

Alle Testmails auf einmal verarbeiten (ohne Server):

```
python -m app.cli --neu
```

## 6. Modellzugriff

Der Client ist OpenAI-kompatibel und über vier Umgebungsvariablen
konfiguriert:

| Variable | Langdock (verwendet) | Ollama (lokal) |
|---|---|---|
| `LLM_PROVIDER` | `langdock` | `ollama` |
| `LLM_BASE_URL` | `https://api.langdock.com/openai/eu/v1` | `http://localhost:11434/v1` |
| `LLM_MODEL` | `gpt-5.1` | z. B. `qwen2.5:7b` |
| `LLM_API_KEY` | Langdock-Schlüssel | beliebiger Wert |

Alle ausgelieferten Ergebnisse in `data/ergebnisse.json` und `docs/data/`
stammen aus echten Läufen gegen Langdock mit `gpt-5.1`. Der Ollama-Pfad ist
gebaut, aber von mir noch nicht gegen eine laufende Ollama-Instanz geprüft.
Für den Deployment-Weg aus Abschnitt 10 wird der Langdock-Zugang des
Arbeitgebers nicht verwendet; die dortigen Deployment-Variablen sind
Platzhalter für ein eigenes Konto.

## 7. Testdaten

15 erfundene Mails in `data/mails.json`, geschrieben von Instandhaltern,
Werksleitern und Einkäufern erfundener Industriefirmen, die typische
Störfälle abdecken:

- Anfrage ohne Anlagennummer (m01, „der Ofen in Halle 3")
- Produktionsstillstand mit Fehlercode am Bedienfeld (m02)
- alte Anlage mit einer Nummer außerhalb des üblichen Schemas (m03)
- drei Anliegen in einer Mail: Ersatzteil, Wartungstermin, Angebot (m04)
- Vertriebsfall, Anfrage für eine neue Anlage (m05)
- Weiterleitung mit drei Zitatebenen (m06)
- englische Mail (m07)
- vager Fall ohne klare Diagnose („riecht komisch, Charge nicht
  durchgehärtet", m08)
- Anhang-Bezug ohne tatsächlichen Anhang (m09)
- sehr knappe Mail ohne Anrede und Signatur (m10)
- Reklamation nach einem vorangegangenen Serviceeinsatz (m11)
- zwei Anlagen in einem Wartungswunsch, an einem Tag (m12)
- weiterer Stillstandsfall (m13)
- Anfrage außerhalb des Kerngeschäfts, Anlagenumzug (m14)
- Ersatzteil- und Wartungsfrage kombiniert (m15)

Vier Mails sind dringlich (Produktionsstillstand), erkennbar nur aus dem
Text, nicht aus Betreff oder Metadaten.

## 8. Tests

```
python -m pytest -q
```

76 Tests laufen ohne Netzzugriff und ohne Schlüssel (Fake-Client). Ein
Test, der wirklich gegen ein Modell fragt, wird nur ausgeführt, wenn
`LLM_API_KEY` gesetzt ist, sonst übersprungen (skip), nie fehlgeschlagen.

Der Linter ist Ruff mit einer bewusst schmalen Regelmenge (`ruff.toml`), damit
er Fehler findet, aber keine Umbauten am Code erzwingt.

Ergebnisse regenerieren sich mit:

```
python -m app.cli --neu --pages
```

## 9. GitHub Pages einschalten

Repository-Einstellungen → **Settings → Pages** → Source
„Deploy from a branch", Branch `main`, Ordner `/docs`. Nach jedem

```
python -m app.cli --pages
```

die aktualisierten Dateien unter `docs/data/` committen, damit der
statische Modus (Abschnitt 2) den aktuellen Stand zeigt.

## 10. Betrieb

Der Weg von der Quelle bis zur Cloud ist vollständig beschrieben und geprüft,
aber bewusst nicht ausgerollt. Nichts davon erzeugt laufende Kosten.

**Lokal starten (ein Befehl).** `docker compose up --build`, dann
`http://localhost:8040`. Die `.env` ist optional; ohne sie läuft der Server mit
den aufgezeichneten Ergebnissen. Konfiguration ausschließlich über
Umgebungsvariablen (`.env.example`), keine Werte im Image.

**Image.** Das `Dockerfile` baut in zwei Stufen auf `python:3.12-slim`:
Abhängigkeiten in Stufe 1, Laufzeitbild in Stufe 2 mit `app/`, `data/` und
`docs/index.html`, als Benutzer `app` (UID 10001) ohne Root-Rechte, mit
Healthcheck auf `/api/status`, lokal gemessen rund 257 MB groß. Der Server
schreibt Statusänderungen nach `data/`; im Container ist das flüchtig, ein
Neustart stellt den Stand des Images wieder her. Die Pipeline
(`.github/workflows/ci.yml`) baut das Image bei
jedem Push, prüft im Rauchtest, dass der Live-Pfad gesperrt ist, und schiebt es
bei einem Push auf `main` nach `ghcr.io/dangtu1190-tech/serviceanfragen-assistent`
(`latest` und `sha-…`). `pytest` liegt mit im Image, weil `requirements.txt`
keine Trennung in Laufzeit- und Testabhängigkeiten kennt; das kostet einige
Megabyte und ändert nichts am Verhalten. Das Paket muss einmal in den
GitHub-Paketeinstellungen auf public gestellt werden (neue Pakete sind
standardmäßig privat); sonst kann die Container App das Image nicht ziehen,
und die Terraform-Konfiguration enthält absichtlich keinen `registry`-Block
für Zugangsdaten.

**Pipeline.** Drei Jobs: Tests und Linter, Docker-Image, Terraform. Der
benannte Schritt führt
`tests/test_pipeline.py::test_kein_original_erreicht_das_modell` zusammen mit
`test_modell_sieht_keine_originale` vor der übrigen Suite aus. Schlägt einer
der beiden fehl, wird kein Image gebaut.

**Cloud-Deployment (Terraform, `infra/azure/`).** Azure Container Apps mit
Resource Group, Log Analytics Workspace (Tagesquote 0,1 GB), Container Apps
Environment, Container App mit externem HTTPS-Ingress, Key Vault und einer
User-Assigned Managed Identity, über die die App den Modellschlüssel liest.
Der Schlüssel steht nirgends in Code, Variablen oder State: Terraform legt nur
einen Platzhalter an, der echte Wert wird nach einem `apply` einmal mit
`az keyvault secret set` gesetzt (`terraform output secret_setzen`). Die
Pipeline führt `terraform fmt -check`, `terraform validate` und `terraform test`
aus; letzteres plant gegen einen Mock-Provider, also ohne Azure-Konto und ohne
Zugangsdaten, und prüft per Assertion unter anderem `min_replicas = 0`. Ein
`terraform apply` gibt es weder lokal noch in der Pipeline. Die Konfiguration
ist vollständig und validiert, aber nie angewendet worden; ein erstes `apply`
findet erfahrungsgemäß Kleinigkeiten (Verzögerung der Rollenzuweisung, weltweit
eindeutiger Key-Vault-Name, Sichtbarkeit des Pakets in der Registry). Eine neue
Version erreicht Azure, indem `container_image` auf den `sha-…`-Tag der
Pipeline gesetzt und ein apply ausgeführt wird; `latest` allein erzeugt bei
`revision_mode = "Single"` keine neue Revision. Zur Konfiguration gehört
außerdem ein Budget auf Ebene der Resource Group über wenige Euro im Monat mit
E-Mail-Alarm bei 80 Prozent (tatsächlicher Verbrauch) und 100 Prozent
(Forecast); es warnt, es stoppt nichts.

**Scale-to-zero.** `min_replicas = 0` ist die entscheidende Zeile. Bei einem
Wert über 0 laufen die Replikate rund um die Uhr und werden auch ohne Traffic
berechnet; das ist der häufigste Grund für unerwartete Rechnungen. Mit 0 fährt
die App ohne Anfragen herunter und startet beim nächsten Aufruf in einigen
Sekunden neu. `max_replicas` ist auf 2 begrenzt, damit auch unerwarteter
Traffic gedeckelt bleibt. Dieselbe Entscheidung steht in `render.yaml` (Free-Plan
mit Spin-down) und `fly.toml` (`min_machines_running = 0`); beide Dateien sind
vorbereitet, nicht ausgerollt. Render bietet laut Doku einen Free-Plan, Fly.io
weist keinen mehr aus (Stand 11.09.2026, Doku-Seiten, kein Konto angelegt).

**Live-Modellpfad standardmäßig aus.** `LIVE_MODELLAUFRUFE=0` ist in Image (und
damit in Compose), Terraform, Render und Fly der Standard. Eine öffentlich erreichbare
Instanz arbeitet dann wie GitHub Pages mit den aufgezeichneten Ergebnissen; der
Verarbeiten-Endpunkt antwortet mit HTTP 403. Grund: Sonst zahlt der hinterlegte
Schlüssel für jeden Besucher, der auf „Verarbeiten" klickt. Der Langdock-Zugang
des Arbeitgebers wird für keinen Teil dieses Deployment-Wegs verwendet; die
Anbietervariablen in `terraform.tfvars.example` sind Platzhalter für ein
eigenes Konto.

## 11. Bewusst nicht enthalten

Mailanbindung (Posteingang, IMAP/Graph), Login/Benutzerverwaltung,
ein tatsächlich ausgerolltes Cloud-Deployment (der Weg dahin steht in
Abschnitt 10, ausgerollt ist nichts), eine echte Datenbank. Die Demo arbeitet
mit JSON-Dateien und manuell eingespielten Testmails.

## 12. Wie ich das in einem Betrieb umsetzen würde

Das Folgende existiert nicht, es ist mein Vorschlag für den nächsten Schritt. Im Anlagenbau kämen die Stammdaten aus dem ERP statt aus der Mail. Anlagen- und Auftragsnummer wären der Schlüssel für den Abgleich, über ihn hingen Kunde, Anlagenhistorie, Wartungsvertrag und der zuletzt zuständige Techniker am Vorgang, statt dass das Modell sie aus dem Text erraten müsste. Der Sachbearbeiter sähe den Entwurf in seiner gewohnten Oberfläche, bestätigt und sendet, jede Antwort wird mit Absender und Zeitpunkt protokolliert. Dringlichkeit, Kapazität je Qualifikation und Ersatzteilverfügbarkeit steuerten die Priorisierung, ein Stillstand mit vorrätigem Teil ginge also vor eine Turnuswartung. Dasselbe Muster passt auf Serviceanfragen, Ersatzteilanfragen und Reklamationen in jedem Betrieb, der ein führendes System für seine Stammdaten hat.
