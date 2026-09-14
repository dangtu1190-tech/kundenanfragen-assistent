# Gesprächsleitfaden

Zehn Fragen, die zu diesem Projekt naheliegen, mit kurzen Antworten. Die
ausführliche Fassung steht im [README](../README.md); hier stehen die Punkte so,
wie ich sie in einem Gespräch sagen würde.

## 1. Warum Mocks statt echter Systeme?

Weil ich für eine Bewerbungsdemo weder ein ERP noch ein CRM noch ein MES
bekomme, und weil eine Demo, die auf einen Firmenzugang angewiesen ist, bei
niemandem läuft. Die Mocks in `systeme/` sind aber keine leeren Attrappen: drei
getrennte FastAPI-Apps mit eigener OpenAPI-Doku (`/erp/docs`, `/crm/docs`,
`/mes/docs`), realistischen Feldern, 404 für Unbekanntes und einem CRM, das
Tickets idempotent über eine externe Referenz anlegt. Was ich damit zeigen
will, ist nicht "ich kann SAP anbinden", sondern der Umgang mit einem fremden
Vertrag: Zeitlimit, Wiederholung, Fehlerabbildung, Degradation. Die
Adapterschicht in `app/integration/` bleibt beim Wechsel auf ein echtes System
stehen, es ändern sich nur die Clients dahinter.

## 2. Warum Regeln im Code und nicht im Modell?

Zuständigkeit und Dringlichkeit stehen in `app/regeln.py`. "Reklamation geht an
den Kundenservice, Veredelung an die Veredelung, Angebot an den Vertrieb,
Rechnung an die Buchhaltung" ist eine Organisationsregel des Versenders und
kein Sprachverständnis. Sie muss dieselbe bleiben, egal welches Modell die
Extraktion geliefert hat, sie muss ohne Prompt-Änderung anpassbar sein, und sie
muss sich testen lassen. Das Modell macht das, was es gut kann: unstrukturierten
Text in Felder überführen. Die Messung stützt das: die Dringlichkeit war im
Modellvergleich das schwächste Feld (9 von 15 und 11 von 15), Bestell- und
Kundennummer dagegen 15 von 15. Ein Feld, das man nicht zuverlässig bekommt,
gehört nicht allein dem Modell.

## 3. Wie ist das idempotent?

Das CRM-Ticket wird mit `externe_referenz = mail_id` angelegt. Kennt das CRM
diese Referenz schon, antwortet es mit 200 und dem vorhandenen Ticket statt mit
201 und einem zweiten. Dieselbe Mail zweimal zu verarbeiten erzeugt also kein
Duplikat, und ein Wiederholungsversuch nach einem abgebrochenen Aufruf ist
gefahrlos. Das ist die Eigenschaft, die man braucht, sobald eine Warteschlange
oder ein Retry im Spiel ist: man weiß dann nicht, ob der erste Aufruf angekommen
ist, und muss ihn gefahrlos wiederholen können. Getestet ist das sowohl im Mock
(`tests/test_systeme.py`) als auch über die Pipeline nach einem Systemausfall.

## 4. Was passiert, wenn ein System ausfällt?

Die Verarbeitung läuft weiter. Der Adapter versucht es nach einer
Zeitüberschreitung oder einem Verbindungsfehler ein zweites Mal (Zeitlimit drei
Sekunden), danach wirft er `SystemNichtErreichbar`. Der betroffene Schritt der
Anreicherung wird übersprungen, `integrationsfehler` im Ergebnis benennt System
und Grund, der Antwortentwurf fällt auf eine Formulierung ohne Systemdaten
zurück, und der Status wird `pruefung_noetig`, damit ein Mensch hinsieht. Eine
Mail geht nicht verloren, weil das ERP gerade neu startet. HTTP 404 ist davon
getrennt: das ist kein Ausfall, sondern ein fachlicher Befund ("Bestellnummer
unbekannt"), und der landet als Rückfrage in `unklarheiten`.

## 5. Warum Ollama, und was sagen die Zahlen?

Ollama läuft lokal, kostet nichts, und keine Kundendaten verlassen den Rechner.
Das passt zu einer Demo, die jeder nachbauen können soll, und es ist in vielen
Betrieben ohnehin die realistischere Variante als ein Cloud-Modell. Gemessen
habe ich zwei Modelle gegen handgeschriebene Soll-Werte in `data/erwartet.json`,
auf einer RTX 5070 Ti mit 16 GB:

| Modell | Kategorien | Zuständigkeit | Dringlichkeit | Bestellnummer | Kundennummer | Frist | Schemafehler | Ø Dauer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss:20b | 13/15 | 14/15 | 9/15 | 15/15 | 15/15 | 14/15 | 0 | 7033 ms |
| qwen2.5:14b-instruct | 9/15 | 11/15 | 11/15 | 13/15 | 9/15 | 12/15 | 1 | 3415 ms |

Wichtig ist, was die Zahlen nicht sagen: jede Zeile ist ein einzelner Lauf über
15 Mails, kein Mittelwert über mehrere Läufe. Ein Punkt Unterschied in einem
Feld ist Rauschen. Belastbar ist die Richtung, also dass gpt-oss:20b in fünf von
sechs Feldern besser und qwen gut doppelt so schnell ist. Der einzige
Schemafehler kam übrigens nicht vom Prompt: Ollamas Standard-Kontextfenster von
4096 Token lief bei einer vagen Mail voll, weil gpt-oss den Rest im
Reasoning-Kanal verbrauchte (1001 + 3095 Token, leere Antwort). Eine Zeile im
Prompt hat das Symptom beseitigt, der saubere Fix wäre ein größeres `num_ctx`
und eine eigene Fehlermeldung für `finish_reason == "length"`. Das steht offen.

## 6. Wie ist das kostenseitig gebaut?

Drei Entscheidungen, alle in der Konfiguration nachlesbar. Erstens
`min_replicas = 0` in `infra/azure/main.tf`: ohne Anfragen läuft nichts und
wird nichts berechnet. Das ist die häufigste Ursache für überraschende
Cloud-Rechnungen und die wichtigste Zeile der Datei; dieselbe Entscheidung
steht in `fly.toml` als `min_machines_running = 0` und in `render.yaml` als
Free-Plan mit Spin-down. Zweitens eine Tagesquote von 0,1 GB auf dem Log
Analytics Workspace, weil Logs der zweite übliche Kostenposten sind. Drittens
ein Budget auf Ebene der Resource Group über wenige Euro im Monat mit Alarm bei
80 und 100 Prozent; das warnt, es stoppt nichts, deshalb ist es die dritte und
nicht die erste Verteidigungslinie. Dazu kommt der Live-Modellpfad, der
standardmäßig aus ist: sonst zahlt der hinterlegte Schlüssel für jeden
Besucher, der auf "Verarbeiten" klickt.

## 7. Wo sind die Grenzen?

Der Zustand ist flüchtig: der Server schreibt nach `data/`, im Container ist
das nach einem Neustart weg. Es gibt keine Anmeldung und keine Rollen, wer die
Seite erreicht, darf alles. Der Server ist auf eine Instanz ausgelegt, mehrere
Repliken würden sich beim Schreiben in dieselben JSON-Dateien in die Quere
kommen; genau deshalb ist `max_replicas` niedrig. Die Terraform-Konfiguration
ist validiert und per `terraform test` gegen einen Mock-Provider geplant, aber
nie angewendet worden. Und die CI ist noch nie gelaufen, weil das Repository
erst angelegt wird; der Badge im README ist bis dahin grau.

## 8. Was fehlt für den Produktivbetrieb?

Anmeldung und Rollen, eine echte Datenbank statt JSON-Dateien, eine
Mailanbindung, ein Ausrollen mit einem ersten `apply` und dem, was dabei
erfahrungsgemäß auffällt (Verzögerung bei der Rollenzuweisung, weltweit
eindeutiger Key-Vault-Name, Sichtbarkeit des Images in der Registry),
strukturierte Logs mit Korrelations-ID und ein Alarm auf die Rate von
`pruefung_noetig`. Fachlich fehlt vor allem eines: Soll-Werte, die mit den
Fachabteilungen abgestimmt sind statt von mir allein festgelegt. Und eine
Freigabe dort, wo die Sachbearbeitung ohnehin arbeitet, also im CRM oder im
Mailclient, nicht in einer zusätzlichen Oberfläche.

## 9. Wie würde man das MES wirklich anbinden?

Nicht über REST-Polling. Maschinenzustände sind ein Strom, kein Datensatz, den
man alle paar Minuten abfragt. In der Praxis wäre das OPC UA mit Subscriptions
auf die relevanten Knoten oder MQTT mit einem Topic je Maschine, dazu ein
kleiner Übersetzer, der den jeweils aktuellen Zustand in einen Cache schreibt.
Die Anreicherung liest dann den Cache und hängt nicht an der Antwortzeit einer
Steuerung. Dasselbe Prinzip gilt in die andere Richtung: ändert sich der Status
einer Bestellung, kommt das als Ereignis, nicht durch wiederholtes Nachfragen.
Die Mock-Schnittstelle `GET /mes/maschinen` bildet fachlich schon das ab, was
dabei herauskommt, nämlich einen Zustand je Maschine samt Meldung und Zeitpunkt.
Er wird auch benutzt: steht die Maschine eines Veredelungsauftrags auf
`stoerung`, vermerkt die Anreicherung, dass das geplante Ende gefährdet ist.

## 10. Warum keine Datenbank?

Weil sie für diese Demo nichts beweisen würde und einiges verhindern würde. Die
Menge ist bekannt und klein (15 Mails), es gibt keine gleichzeitigen Schreiber,
und ohne Datenbank läuft die Demo als GitHub Pages, als einzelner Container und
als `python -m app.cli` ohne Server. Eine Datenbank hätte einen Dienst mehr
bedeutet, der rund um die Uhr Geld kostet, und damit genau die Entscheidung
untergraben, um die es in Abschnitt 6 geht. Für den Produktivbetrieb wäre sie
selbstverständlich, und die Stelle, an der sie hingehört, ist klar abgegrenzt:
der Dateizugriff der Anwendung und der der Mock-Systeme steckt jeweils in einem
eigenen Modul, `app/speicher.py` und `systeme/speicher.py`.

## Grenzen, die ich selbst nenne

Damit das nicht in Rückfragen versteckt bleibt, hier gebündelt:

- **Nichts ist ausgerollt.** Terraform ist validiert und gegen einen
  Mock-Provider geplant, aber nie angewendet. Ein erstes `apply` findet
  erfahrungsgemäß Kleinigkeiten.
- **Die CI ist noch nie gelaufen.** Das Repository wird gerade erst angelegt.
- **Zustand ist flüchtig**, es gibt **keine Anmeldung**, und der Server ist auf
  **eine Instanz** ausgelegt.
- **Die Modellzahlen sind je ein Lauf**, keine Mittelwerte. Einzelne Punkte
  sind Rauschen.
- **Zwei fachliche Restfehler bleiben** (m11 und m12 im Modellvergleich). Die
  Prompt-Regel, die den einen repariert hätte, hätte einen anderen Fall
  kaputtgemacht; das wäre eine Anpassung an die Testdaten gewesen, keine Regel.
- **Die Pseudonymisierung hat bekannte Lücken**, die im README benannt sind:
  Namen ohne Anrede oder Signatur, klein geschriebene Signaturen, mehrdeutige
  Nachnamen, Orte ohne PLZ, Firmennamen ohne Rechtsform.
- **Ein Kontextfenster-Problem ist nur umschifft, nicht gelöst.** Ollamas
  Standard von 4096 Token kann bei einer längeren Mail wieder zuschlagen.
- **Alle Daten sind erfunden**, Versender und Kunden ebenso. Es ist eine Demo,
  kein Produkt.
