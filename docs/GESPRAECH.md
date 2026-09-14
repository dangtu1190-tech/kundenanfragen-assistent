# Gesprächsleitfaden

Was ich im Gespräch live zeige (5 Minuten):

1. Seite öffnen, Mail m01 (Wartung ohne Anlagennummer) anklicken: links steht
   das Original, rechts das, was das Modell tatsächlich bekommen hat. Auf
   „[NAME_1]" zeigen, das aus der Signatur „Frank Lindemann" stammt, dazu
   Firma „[FIRMA_1]" (Hartmann Wärmebehandlung GmbH), Adresse, Ort und
   Telefon sind ebenfalls ersetzt. Der Kunde nennt keine Anlagennummer
   („Die Nummer vom Typenschild habe ich gerade nicht zur Hand"), das landet
   in den extrahierten Unklarheiten statt einer geratenen Nummer.

2. Mail m02 (VIM 30 steht, Fehlercode F-217) öffnen: Dringlichkeit
   Stillstand, weil die Produktion steht und die Charge im Ofen festsitzt.
   Im pseudonymisierten Text auf „Fehlercode F-217" zeigen: Anlagen- und
   Seriennummern sowie Fehlercodes werden bewusst nicht ersetzt, das Modell
   braucht sie wörtlich. Der Fehlercode löst zugleich die Qualifikation
   Steuerung aus, und die Terminregel für Stillstand sucht den ersten freien
   Techniker mit dieser Qualifikation ab heute statt im Wunschzeitraum, mit
   dem Hinweis „Produktionsstillstand, Einsatz vorgezogen." Dazu der Hinweis,
   dass mehrere Vorschläge auf denselben Techniker am selben Tag fallen
   können, im aktuellen Lauf etwa m07 und m10 beide auf T2 am 14.09. Ein
   Vorschlag reserviert nichts, erst die Freigabe belegt den Slot im
   Kalender, und ab dann ist der Techniker für die anderen Mails belegt.

3. Mail m05 (zweiter Vakuumlötofen) öffnen: Zuständigkeit Vertrieb, weil es
   um eine neue Anlage geht, kein Servicetechniker wird gesucht. Die
   Oberfläche zeigt „kein Einsatz (Vertrieb)", der Antwortentwurf leitet an
   den Vertrieb weiter statt einen Termin vorzuschlagen.

4. Mail m06 (WG: WG: Thermoelement Ofen 2) öffnen: eine Weiterleitung mit
   drei Zitatebenen. Die eigentliche Anfrage steht in der untersten Ebene
   (Thermoelement, SN VK-2200-0144), nicht im obersten Text von Petra
   Schulz. Auf die Zeile „Von: [NAME_2] [FIRMA_1]" zeigen: Aus „Von: Bernd
   Kolb" werden im pseudonymisierten Text zwei verschiedene Platzhalter,
   erkannt über zwei getrennte Mechanismen. „Bernd" wird über das
   Von:-Zeilen-Muster als Vorname erkannt und bekommt denselben Platzhalter
   wie die spätere Anrede „[NAME_2], das Thermoelement …". „Kolb" dagegen
   wird gar nicht als Namensteil erkannt, sondern schon vorher als
   Firmen-Kurzform von „Kolb Zahnradfabrik GmbH" maskiert, weil die
   Firmenerkennung vor der Namenserkennung läuft. Eine Ausnahme davon gibt
   es: der volle Name des Absenders fällt vor der Firma, sonst zerfiele die
   Signatur eines Absenders, der wie seine Firma heißt, in
   „[NAME_1] [FIRMA_1]" und der Nachname wäre wieder ablesbar. Zum Vergleich die Zeilen
   „Von: Instandhaltung" und „Von: Schichtführer" in den tieferen
   Zitatebenen zeigen: Die bleiben unverändert sichtbar, weil Rollenwörter
   wie „Instandhaltung" und „Schichtführer" auf einer Ausschlussliste
   stehen und nicht als Name durchgehen.

5. Mail m07 (Vacuum leak VIM 22, line down) öffnen: eine englische Mail. Das
   Modell versteht sie trotzdem und liefert die deutschen Kategoriewerte
   des Schemas (Kategorie, Dringlichkeit, Tageszeit). Auch die
   internationale Telefonnummer („+44 1234 567890") und die Rechtsform
   „Ltd." werden erkannt.

6. Mail m09 (Türdichtung, Foto vom Typenschild anbei) öffnen: der Text
   kündigt ein Foto des Typenschilds an, das in dieser Demo keinen
   tatsächlichen Anhang gibt. Das gehört ebenfalls in die Unklarheiten,
   sonst würde die Anlagennummer stillschweigend fehlen.

7. Über „Neue Mail" eine Anfrage live eintippen und verarbeiten lassen,
   inklusive des neuen Felds Firma. Dabei erwähnen: Der Modellanbieter ist
   umschaltbar, mit Ollama bliebe dabei alles auf dem eigenen Rechner statt
   bei einem externen Anbieter.

8. Zum Schluss den Fehlerpfad zeigen: Liefert das Modell kein gültiges
   JSON, bekommt die Mail den Status „Prüfung nötig" statt eines Absturzes.
