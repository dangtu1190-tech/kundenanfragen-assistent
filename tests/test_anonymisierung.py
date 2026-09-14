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


def test_firma_ueber_rechtsform():
    text, tab = anonymisiere("Wir sind die Hartmann Wärmebehandlung GmbH. Die Roth & Söhne Metallguss GmbH & Co. KG "
                             "und die Nordlicht Turbinentechnik AG kennen Sie.")
    firmen = [t["original"] for t in tab if t["typ"] == "FIRMA"]
    assert firmen == ["Hartmann Wärmebehandlung GmbH", "Roth & Söhne Metallguss GmbH & Co. KG",
                      "Nordlicht Turbinentechnik AG"]
    assert "Hartmann" not in text and "Söhne" not in text and "Nordlicht" not in text
    assert text.startswith("Wir sind die [FIRMA_1]. Die [FIRMA_2] und die [FIRMA_3] kennen Sie.")


def test_absenderfirma_auch_kurzform():
    text, tab = anonymisiere("hier ist die präzisionsteile menzel ag, wir von Präzisionsteile brauchen Hilfe.",
                             absender_firma="Präzisionsteile Menzel AG")
    assert tab[0] == {"typ": "FIRMA", "platzhalter": "[FIRMA_1]", "original": "Präzisionsteile Menzel AG"}
    assert "menzel" not in text.lower() and "Präzisionsteile" not in text
    assert text.count("[FIRMA_1]") == 2


def test_anlagen_und_seriennummern_bleiben():
    text, tab = anonymisiere("Anlage VIM 30, SN VIM-3000-0917, Fehlercode F-217, alte Nummer R 03/118, Halle 3, "
                             "Vakuum 5x10-3 mbar, Baujahr 2003.")
    assert tab == []
    assert "VIM-3000-0917" in text and "F-217" in text and "R 03/118" in text and "Halle 3" in text


def test_rechtsform_allein_ist_keine_firma():
    text, tab = anonymisiere("Die GmbH als Rechtsform. Eine AG auch.")
    assert [t for t in tab if t["typ"] == "FIRMA"] == []


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
    text, tab = anonymisiere("Herr Weber, Tel 0176 12345678, Firma Weber Stahl GmbH")
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
    assert PLATZHALTER_MUSTER.fullmatch("[FIRMA_12]")
    assert not PLATZHALTER_MUSTER.fullmatch("[KENNZEICHEN_1]")


def test_adresse_frisst_kein_folgeleerzeichen():
    text, tab = anonymisiere("Bitte kommen Sie zur Musterstrasse 12 dann klappt es.")
    assert text == "Bitte kommen Sie zur [ADRESSE_1] dann klappt es."
    assert zuruecksetzen(text, tab) == "Bitte kommen Sie zur Musterstrasse 12 dann klappt es."


def test_adresse_nimmt_keine_fremden_vorwoerter():
    text, tab = anonymisiere("Unser Kunde Peter Weg 3 hat angerufen. Kaiser-Wilhelm-Straße 5 auch.")
    originale = [t["original"] for t in tab if t["typ"] == "ADRESSE"]
    assert originale == ["Weg 3", "Kaiser-Wilhelm-Straße 5"]
    assert text.startswith("Unser Kunde Peter [ADRESSE_1] hat")
