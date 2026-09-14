"""Grenzfälle der Pseudonymisierung: Zeilenumbrüche, Firmen mit Rechtsform,
Ortszusätze, mehrdeutige Nachnamen, ASCII-Grußformeln."""
from app.anonymisierung import anonymisiere, zuruecksetzen


def test_telefon_frisst_die_folgezeile_nicht():
    text, tab = anonymisiere("Tel. 06021 123456\n63739 Aschaffenburg")
    assert text == "Tel. [TELEFON_1]\n[ORT_1]"
    assert {t["typ"] for t in tab} == {"TELEFON", "ORT"}
    assert zuruecksetzen(text, tab) == "Tel. 06021 123456\n63739 Aschaffenburg"


def test_telefon_frisst_das_datum_der_folgezeile_nicht():
    text, tab = anonymisiere("Rueckruf 0170 1234567\n15.09. passt mir")
    assert "15.09." in text
    assert [t["original"] for t in tab if t["typ"] == "TELEFON"] == ["0170 1234567"]


def test_zwei_nummern_in_zwei_zeilen_sind_zwei_eintraege():
    text, tab = anonymisiere("Telefon 06051 881720\n0171 6554321")
    originale = [t["original"] for t in tab if t["typ"] == "TELEFON"]
    assert originale == ["06051 881720", "0171 6554321"]
    assert text == "Telefon [TELEFON_1]\n[TELEFON_2]"


def test_firma_frisst_keine_folgeworte():
    text, tab = anonymisiere("Die Kolb Zahnradfabrik GmbH meldet: Halle 3 steht. Bitte Rückruf.")
    assert text == "Die [FIRMA_1] meldet: Halle 3 steht. Bitte Rückruf."


def test_firma_in_signatur_und_email_domain():
    text, tab = anonymisiere("Gruß\nAndrea Wittmann\nElektro Wittmann GmbH\na.wittmann@elektro-wittmann.example\n06051 881720",
                             absender_name="Andrea Wittmann", absender_firma="Elektro Wittmann GmbH")
    assert "Wittmann" not in text and "elektro-wittmann" not in text
    typen = [t["typ"] for t in tab]
    assert "FIRMA" in typen and "NAME" in typen and "EMAIL" in typen and "TELEFON" in typen


def test_ort_zusatz_frisst_keine_folgeworte():
    text, tab = anonymisiere("63739 Aschaffenburg bei Herrn Mueller vorbeikommen. 60313 Frankfurt am Main.")
    assert "Mueller" not in text
    assert [t["original"] for t in tab if t["typ"] == "ORT"] == ["63739 Aschaffenburg", "60313 Frankfurt"]


def test_gemeinsamer_nachname_bleibt_allein_stehen():
    text, tab = anonymisiere(
        "meine Frau Sabine Krämer und ich, Peter Krämer, kommen. Krämer allein reicht nicht.",
        absender_name="Peter Krämer",
    )
    namen = [t for t in tab if t["typ"] == "NAME"]
    assert len(namen) == 2
    assert {t["original"] for t in namen} == {"Sabine Krämer", "Peter Krämer"}
    assert "Sabine Krämer" not in text and "Peter Krämer" not in text
    # Dokumentierte Grenze: der allein stehende Nachname ist nicht zuordenbar
    assert "Krämer allein reicht nicht." in text


def test_eindeutiger_nachname_wird_weiter_ersetzt():
    """Dokumentierte Grenze: der Nachname wird zum vollen Namen zurückgesetzt.

    "Elektro Wittmann GmbH" (das frühere Beispiel hier) ist seit der
    Firmenerkennung selbst ein FIRMA-Treffer (siehe
    test_firma_in_signatur_und_email_domain); dieser Test prueft die reine
    Namensteil-Ersetzung deshalb an einem Satz ohne Rechtsform."""
    text, tab = anonymisiere("Anruf von Wittmann wegen der Anlage.", absender_name="Andrea Wittmann")
    assert text == "Anruf von [NAME_1] wegen der Anlage."
    assert zuruecksetzen(text, tab) == "Anruf von Andrea Wittmann wegen der Anlage."


def test_ascii_grussformel_findet_die_signatur():
    text, tab = anonymisiere("Danke.\n\nViele Gruesse\nMax Muster")
    assert [t["original"] for t in tab if t["typ"] == "NAME"] == ["Max Muster"]
    assert text == "Danke.\n\nViele Gruesse\n[NAME_1]"


def test_ascii_grussformel_lange_variante():
    text, tab = anonymisiere("Bitte um Termin.\n\nMit freundlichen Gruessen\nJens Ohlmann")
    assert [t["original"] for t in tab if t["typ"] == "NAME"] == ["Jens Ohlmann"]


def test_vorname_aus_zitierter_von_zeile():
    text, tab = anonymisiere(
        "Bitte weiterleiten.\n\n> Von: Bernd Kolb\n> Petra, bitte an den Hersteller.\n>\n"
        "> > Von: Instandhaltung\n> > Bernd, das Thermoelement zeigt zu wenig.",
        absender_name="Petra Schulz", absender_firma="Kolb Zahnradfabrik GmbH")
    assert "Bernd" not in text and "Kolb" not in text and "Petra" not in text
    assert "Instandhaltung" in text          # Rollenwort ist kein Name
    assert "Thermoelement" in text


def test_adresse_mit_park_hof_feld_chaussee():
    """Gewerbepark, Kastanienhof und Co. sind Adressen, ein Wort ohne Hausnummer nicht."""
    text, tab = anonymisiere("Am Gewerbepark 12\n36381 Schlüchtern")
    assert [t["original"] for t in tab if t["typ"] == "ADRESSE"] == ["Am Gewerbepark 12"]
    assert [t["original"] for t in tab if t["typ"] == "ORT"] == ["36381 Schlüchtern"]
    assert text == "[ADRESSE_1]\n[ORT_1]"

    text, tab = anonymisiere("Kastanienhof 4")
    assert [t["original"] for t in tab if t["typ"] == "ADRESSE"] == ["Kastanienhof 4"]

    text, tab = anonymisiere("Wir sitzen im Industriepark und warten.")
    assert [t for t in tab if t["typ"] == "ADRESSE"] == []
    assert "Industriepark" in text


def test_absendername_faellt_vor_der_firmen_kurzform():
    """Absender heißt wie seine Firma: die Signatur darf nicht zu
    '[NAME_1] [FIRMA_1]' zerfallen, sonst ist der Nachname wieder ablesbar."""
    text, tab = anonymisiere(
        "Mit freundlichen Grüßen\nAndrea Wittmann\nWittmann Feinmechanik GmbH\nAm Bahndamm 7",
        absender_name="Andrea Wittmann", absender_firma="Wittmann Feinmechanik GmbH")
    assert "[NAME_1]\n[FIRMA_1]\n[ADRESSE_1]" in text
    assert "[NAME_1] [FIRMA_1]" not in text
    assert len([t for t in tab if t["typ"] == "NAME"]) == 1
    assert len([t for t in tab if t["typ"] == "FIRMA"]) == 1
    assert zuruecksetzen(text, tab).startswith("Mit freundlichen Grüßen\nAndrea Wittmann")


def test_firma_ueberschreitet_die_satzgrenze_nicht():
    text, tab = anonymisiere("Die Anlage meldet Stillstand. Unsere Hartmann GmbH auch.")
    firmen = [t["original"] for t in tab if t["typ"] == "FIRMA"]
    assert len(firmen) == 1
    assert "Stillstand" not in firmen[0]
    assert "Stillstand." in text


def test_internationale_telefonnummer():
    text, tab = anonymisiere(
        "Phone +44 1234 567890 or +33 1 23 45 67 89. Serial VIM-3000-0917, part 4711-0815-22, R 03/118.")
    tel = [t["original"] for t in tab if t["typ"] == "TELEFON"]
    assert tel == ["+44 1234 567890", "+33 1 23 45 67 89"]
    assert "VIM-3000-0917" in text and "4711-0815-22" in text and "R 03/118" in text
