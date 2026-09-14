# Serviceanfragen-Assistent: Umstellung auf ein branchenneutrales Szenario

Datum: 10.09.2026. Ersetzt die Domäne der Demo (Autohaus-Werkstatt) durch den
Service eines Sonderanlagenbauers (Vakuumöfen für Metallurgie und
Wärmebehandlung). Der technische Kern bleibt unverändert: Pipeline,
Pseudonymisierungsverfahren, Tests, Oberfläche, Umschaltung Langdock/Ollama,
Umfangsgrenzen (keine Mailanbindung, keine Auth, kein Deployment, keine DB).

## 1. Umbenennung

Projektname überall: „Werkstatt-Terminassistent" wird „Serviceanfragen-Assistent".
Betrifft README, Seitentitel und Überschriften der HTML, FastAPI-Titel,
Docstrings. Das GitHub-Repo benennt der Autor selbst in den Einstellungen um
(`serviceanfragen-assistent`); danach werden der lokale Ordner und die Remote-URL
nachgezogen. Neue Adressen:

- `https://github.com/dangtu1190-tech/serviceanfragen-assistent`
- `https://dangtu1190-tech.github.io/serviceanfragen-assistent/`

## 2. Extraktionsschema

```
kunde:            {firma: str|null}                      Platzhalter [FIRMA_n]
ansprechpartner:  {anrede: Herr|Frau|null, name: str|null}  Platzhalter [NAME_n]
anlage:           {typ: str|null, nummer: str|null, baujahr: int|null}
anliegen:         [{kategorie, beschreibung}]
                  kategorie aus ersatzteil | wartung | stoerung | angebot | reklamation | sonstiges
dringlichkeit:    niedrig | mittel | hoch | stillstand
wunschzeitraum:   {von, bis, tageszeit}  (unverändert)
zustaendigkeit:   service | vertrieb
unklarheiten:     [str]
```

Anlagen- und Seriennummern sowie Fehlercodes übernimmt das Modell wörtlich,
sie sind keine Platzhalter. `stillstand` gilt, wenn die Produktion steht oder
eine Charge im Ofen festsitzt. `vertrieb`, wenn es um eine Neuanlage, einen
Kauf oder ein Angebot für eine neue Anlage geht; Angebote für Wartung,
Retrofit oder Ersatzteile bleiben `service`.

## 3. Pseudonymisierung

Ersetzt werden: Name der Ansprechperson (NAME), Firmenname (FIRMA), Adresse
(ADRESSE), PLZ+Ort (ORT), Telefonnummer (TELEFON), E-Mail-Adresse (EMAIL).
Das Kennzeichen-Muster entfällt.

Firmennamen werden über Rechtsform-Endungen erkannt (GmbH, GmbH & Co. KG, AG,
KG, SE, OHG, e.K., Ltd., Inc., S.p.A., S.A., B.V.) mit bis zu vier
vorangestellten großgeschriebenen Wörtern oder „&". Zusätzlich wird die
Absenderfirma aus den Mail-Metadaten (`absender_firma`) wie der Absendername
behandelt: der volle Name wird unabhängig von Groß-/Kleinschreibung ersetzt,
außerdem das erste Wort, wenn es mindestens vier Buchstaben hat und keine
Rechtsform ist.

**Bewusst nicht ersetzt:** Anlagen- und Seriennummern, Fehlercodes,
Anlagentypen, Hallenbezeichnungen. Sie sind keine personenbezogenen Daten,
und das Modell braucht sie für die Zuordnung. Firmennamen werden dagegen
ersetzt, nicht aus Datenschutzgründen, sondern weil sie Geschäftsgeheimnisse
berühren (wer welche Anlage betreibt und welche Störungen hat). Beides steht
so im README, weil die Auswahl der Felder eine Entscheidung ist und keine
Pauschalregel.

Der Leck-Test prüft weiterhin für alle 15 Mails, dass kein Originalwert und
kein Bestandteil ab drei Zeichen das Modell erreicht; Rechtsform-Kürzel
(GmbH, AG, KG, Co., SE, &) sind vom Bestandteil-Vergleich ausgenommen, weil
sie kein Geheimnis tragen.

## 4. Kapazitätskalender: Servicetechniker

`data/kalender.json` (Dateiname bleibt, Struktur neu):

```
basisdatum: 2026-09-14
techniker: [{kuerzel: "T1", name: "Techniker 1", qualifikationen: ["elektrik","steuerung"]}, ... 5 Stück]
tage: [{datum: "2026-09-14", belegt: ["T1","T3"]}, ... alle Werktage über drei Wochen]
```

Qualifikationen: elektrik, vakuumtechnik, steuerung, mechanik. Die benötigte
Qualifikation wird aus den Anliegen abgeleitet (Schlüsselwörter in Kategorie
und Beschreibung): Fehlercode, Steuerung, SPS, Bedienfeld, Display, Software
→ steuerung; Vakuum, Pumpe, Leck, Druck → vakuumtechnik; Heizung,
Heizelement, elektrisch, Sicherung, Thermoelement, Strom → elektrik; sonst
mechanik.

Terminregeln: `vertrieb` → kein Termin. Nur Ersatzteil-Anliegen → kein
Termin, stattdessen Verfügbarkeitshinweise. `stillstand` → erster Tag ab
heute mit freiem Techniker der benötigten Qualifikation, Hinweis
„Produktionsstillstand, Einsatz vorgezogen." Sonst erster freier Tag im
Wunschzeitraum, danach erster freier Tag nach dem Zeitraum mit Hinweis
„außerhalb des Wunschzeitraums". Ohne Wunsch: ab morgen. Der Vorschlag
reserviert nichts; Freigeben belegt den Techniker an dem Tag, Ablehnen und
Neu-Verarbeiten geben ihn wieder frei (Symmetrie wie bisher).

Termin-Objekt: `{datum, techniker, qualifikation, hinweis}`.

## 5. Ersatzteile

`data/ersatzteile.json`: kleine Liste aus Begriffen, Teilbezeichnung und
Status („ab Lager", „Lieferzeit ca. 3 Wochen", …). Für jedes Anliegen der
Kategorie `ersatzteil` liefert `app/ersatzteile.py` einen Hinweis; ohne
Treffer „Verfügbarkeit wird geprüft". Ergebnisobjekt bekommt das Feld
`ersatzteile: [{teil, status}]`. Der Antwortentwurf listet diese Hinweise.

## 6. Antwortentwurf

Anrede aus `ansprechpartner`. Bezug: „Für Ihre Anlage {typ} ({nummer}) haben
wir notiert:" bzw. „Für Ihre Anlage haben wir notiert:". Termin: „Wir
schlagen Ihnen den Einsatz eines Servicetechnikers ({Qualifikation}) am
{Wochentag, Datum} vor." Ersatzteilzeilen: „Ersatzteil {teil}: {status}".
Vertrieb: Weiterleitungstext plus Liste der Anliegen. Unklarheiten wie bisher.
Signatur „Ihr Serviceteam".

## 7. Testdaten

15 erfundene Mails von Instandhaltern, Werksleitern und Einkäufern erfundener
Industriefirmen (alle mit Rechtsform im Namen). Mail-Objekt: `id,
absender_name, absender_firma, absender_email, betreff, empfangen, text`.
Enthalten sind: Anfrage ohne Anlagennummer („der Ofen in Halle 3"); Anlage von
2003 mit Nummer außerhalb des Schemas; drei Anliegen in einer Mail
(Ersatzteil, Wartungstermin, Angebot); Störung mit Fehlercode vom Bedienfeld;
Vertriebsfall (Neuanlage); Weiterleitung mit drei Zitatebenen; englische
Mail; vager Fall („riecht komisch, Charge nicht durchgehärtet"); Anhang-Bezug
ohne Anhang; sehr knappe Mail ohne Anrede und Signatur. Vier Mails sind
dringlich (Produktionsstillstand), erkennbar nur aus dem Text.

## 8. Oberfläche

Titel „Serviceanfragen-Assistent – Demo". Extrahierte Felder: Kunde,
Ansprechpartner, Anlage (Typ, Nummer, Baujahr), Anliegen, Dringlichkeit,
Wunschzeitraum, Zuständigkeit, Unklarheiten. Rechte Spalte: „Einsatzvorschlag"
mit Datum und Techniker (Qualifikation), darunter Ersatzteilhinweise, sonst
wie bisher. Formular „Neue Mail" bekommt ein Feld Firma.

## 9. README und Gesprächsleitfaden

README: Projektzweck ohne Autohaus-Bezug, Abschnitt zur Feldauswahl der
Pseudonymisierung (Abschnitt 3 oben), Grenzen wie bisher, Ollama-Vorbehalt
bleibt. Gesprächsleitfaden auf die neuen Mails umgeschrieben.

## 10. Echtlauf und Screenshot

Alle 15 Mails laufen erneut über Langdock, Ergebnisse und Pages-Kopie werden
committet. Dabei entsteht eine Liste der Mails, bei denen die Extraktion
Mühe hat. Screenshot der Gegenüberstellung mit der Mail ohne Anlagennummer
als PNG für das Portfolio.
