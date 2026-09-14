from app.antwort import baue_antwort
from tests.conftest import lies_systemdatei

VERSENDER = "Berufskleidung Nord GmbH"
EX = {
    "kunde": {"firma": "Dachdeckerei Brandt GmbH", "kundennummer": "K-10234"},
    "ansprechpartner": {"anrede": "Herr", "name": "Jens Brandt"},
    "bezug": {"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
    "artikel": [{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "L",
                 "farbe": "gelb", "menge": 6}],
    "anliegen": [{"kategorie": "bestellstatus", "beschreibung": "Wo bleibt die Lieferung?"}],
    "dringlichkeit": "hoch",
    "frist": "2026-09-18",
    "unklarheiten": [],
}


def test_entwurf_grundgeruest():
    t = baue_antwort(EX, {}, "kundenservice", "Warnschutzjacken Bestellung B-2026-04711", VERSENDER)
    assert t.startswith("Sehr geehrter Herr Brandt,")
    assert "„Warnschutzjacken Bestellung B-2026-04711“" in t
    assert "- Bestellstatus: Wo bleibt die Lieferung?" in t
    assert "[" not in t
    assert t.rstrip().endswith("Mit freundlichen Grüßen\nIhr Kundenservice\nBerufskleidung Nord GmbH")


def test_entwurf_ohne_namen_und_ohne_betreff():
    ex = dict(EX, ansprechpartner={"anrede": None, "name": None})
    t = baue_antwort(ex, {}, "kundenservice", "", VERSENDER)
    assert t.startswith("Guten Tag,")
    assert "vielen Dank für Ihre Nachricht." in t


def test_entwurf_anrede_frau_und_nur_name():
    t = baue_antwort(dict(EX, ansprechpartner={"anrede": "Frau", "name": "Martina Kessler"}),
                     {}, "kundenservice", "x", VERSENDER)
    assert t.startswith("Sehr geehrte Frau Kessler,")
    t = baue_antwort(dict(EX, ansprechpartner={"anrede": None, "name": "Martina Kessler"}),
                     {}, "kundenservice", "x", VERSENDER)
    assert t.startswith("Guten Tag Martina Kessler,")


def test_entwurf_vertrieb_buchhaltung_veredelung():
    t = baue_antwort(EX, {}, "vertrieb", "Angebot", VERSENDER)
    assert "Ihr Anliegen betrifft unseren Vertrieb, die Kolleginnen und Kollegen melden sich mit einem Angebot." in t
    t = baue_antwort(EX, {}, "buchhaltung", "Rechnung", VERSENDER)
    assert "Ihre Rechnungsfrage haben wir an die Buchhaltung weitergegeben." in t
    t = baue_antwort(EX, {}, "veredelung", "Stickerei", VERSENDER)
    assert "Unsere Veredelung prüft Ihren Auftrag." in t


def test_entwurf_mehrere_anliegen_und_unklarheiten():
    ex = dict(EX, anliegen=[{"kategorie": "ruecksendung", "beschreibung": "sechs Regenjacken zurück"},
                            {"kategorie": "verfuegbarkeit", "beschreibung": "Größe L lieferbar?"}],
              unklarheiten=["angekündigte Fotos fehlen"])
    t = baue_antwort(ex, {}, "kundenservice", "Rücksendung", VERSENDER)
    assert "- Rücksendung: sechs Regenjacken zurück" in t
    assert "- Verfügbarkeit: Größe L lieferbar?" in t
    assert "- angekündigte Fotos fehlen" in t
    assert "benötigen wir noch" in t


def test_entwurf_ohne_anliegen_bleibt_hoeflich():
    t = baue_antwort(dict(EX, anliegen=[]), {}, "kundenservice", "", VERSENDER)
    assert "notiert" not in t
    assert t.count("\n\n") >= 1


def _eintrag(datei: str, schluessel: str, wert: str) -> dict:
    treffer = [e for e in lies_systemdatei(datei) if e[schluessel] == wert]
    assert treffer, f"{wert} fehlt in {datei}"
    return treffer[0]


def test_bestellstatus_versendet_nennt_sendungsnummer():
    sd = {"bestellung": _eintrag("bestellungen.json", "bestellnummer", "B-2026-04711")}
    t = baue_antwort(EX, sd, "kundenservice", "Bestellung", VERSENDER)
    assert ("Ihre Bestellung B-2026-04711 vom 2026-09-09 ist versendet, Sendungsnummer SN-7F3K9Q2L, "
            "voraussichtliche Zustellung am 2026-09-15.") in t
    assert "Wir prüfen den Stand" not in t


def test_bestellstatus_nennt_frist_konflikt():
    """Liefertermin nach der Kundenfrist gehört in die Antwort, nicht nur ins Protokoll."""
    sd = {"bestellung": _eintrag("bestellungen.json", "bestellnummer", "B-2026-04750")}
    t = baue_antwort(dict(EX, frist="2026-09-18"), sd, "kundenservice", "Lieferung", VERSENDER)
    assert "geplanter Liefertermin ist der 2026-09-19" in t
    assert "Der geplante Liefertermin 2026-09-19 liegt nach Ihrer Frist 2026-09-18" in t


def test_bestellstatus_teilgeliefert_listet_offene_positionen():
    ex = dict(EX, anliegen=[{"kategorie": "bestellstatus", "beschreibung": "Teillieferung"}], frist=None)
    sd = {"bestellung": _eintrag("bestellungen.json", "bestellnummer", "B-2026-04702")}
    t = baue_antwort(ex, sd, "kundenservice", "Teillieferung", VERSENDER)
    assert "Offen sind noch:" in t
    assert "- 2 x Softshelljacke (A-4210), Größe XL, navy" in t
    assert "Sicherheitsschuh" not in t  # geliefert, gehört nicht in die Liste


def test_bestellstatus_zugestellt_und_kommissionierung():
    sd = {"bestellung": _eintrag("bestellungen.json", "bestellnummer", "B-2026-04555")}
    assert "Ihre Bestellung B-2026-04555 ist am 2026-08-04 bei Ihnen eingetroffen." in baue_antwort(
        EX, sd, "kundenservice", "x", VERSENDER)
    sd = {"bestellung": _eintrag("bestellungen.json", "bestellnummer", "B-2026-04733")}
    assert "wird gerade kommissioniert, geplanter Liefertermin ist der 2026-09-18." in baue_antwort(
        EX, sd, "kundenservice", "x", VERSENDER)


def test_verfuegbarkeit_mit_bestand_und_nachfolger():
    ex = dict(EX, anliegen=[{"kategorie": "verfuegbarkeit", "beschreibung": "Noch lieferbar?"}], frist=None)
    sd = {"artikel": [{"artikelnummer": "A-4210", "groesse": "XL", "farbe": "navy",
                       "bestand": 0, "nachfolger": "A-4211"},
                      {"artikelnummer": "A-4610", "groesse": "L", "farbe": "gelb",
                       "bestand": 35, "nachfolger": None}]}
    t = baue_antwort(ex, sd, "kundenservice", "Verfügbarkeit", VERSENDER)
    assert "A-4210 in Größe XL, navy ist nicht mehr lieferbar; als Nachfolger können wir A-4211 anbieten." in t
    assert "A-4610 in Größe L, gelb ist lieferbar, Bestand 35 Stück." in t


def test_veredelung_mit_maschine_und_stoerung():
    ex = dict(EX, anliegen=[{"kategorie": "veredelung", "beschreibung": "Stand der Stickerei?"}], frist=None)
    auftrag = _eintrag("veredelung.json", "auftrag", "V-2026-131")
    sd = {"veredelung": auftrag, "maschine": _eintrag("maschinen.json", "maschine", "STK-01")}
    t = baue_antwort(ex, sd, "veredelung", "Stickerei", VERSENDER)
    assert "Ihr Veredelungsauftrag V-2026-131 (Stick) ist in Produktion." in t
    assert "Maschine STK-01, geplantes Ende ist der 2026-09-16." in t
    assert "Störung" not in t

    sd["maschine"] = dict(sd["maschine"], zustand="stoerung", meldung="Fadenbruch Kopf 2")
    t = baue_antwort(ex, sd, "veredelung", "Stickerei", VERSENDER)
    assert "Maschine STK-01 meldet derzeit eine Störung" in t
    assert "geplante Ende ist dadurch gefährdet" in t


def test_veredelung_wartet_auf_freigabe():
    ex = dict(EX, anliegen=[{"kategorie": "veredelung", "beschreibung": "Wann geht es los?"}], frist=None)
    sd = {"veredelung": _eintrag("veredelung.json", "auftrag", "V-2026-140")}
    t = baue_antwort(ex, sd, "veredelung", "Logo", VERSENDER)
    assert "Ihr Veredelungsauftrag V-2026-140 (Stick) wartet auf Ihre Freigabe." in t
    assert "Hinweis aus der Produktion: Stickdatei fehlt." in t


def test_rechnung_nennt_betrag_und_faelligkeit():
    ex = dict(EX, anliegen=[{"kategorie": "rechnung", "beschreibung": "Rechnungskopie"}], frist=None)
    sd = {"rechnung": _eintrag("rechnungen.json", "rechnungsnummer", "R-2026-07731")}
    t = baue_antwort(ex, sd, "buchhaltung", "Rechnung", VERSENDER)
    assert "Die Rechnung R-2026-07731 über 1284,50 Euro ist am 2026-10-09 fällig." in t


def test_reklamation_und_ruecksendung_brauchen_keine_systemdaten():
    ex = dict(EX, anliegen=[{"kategorie": "reklamation", "beschreibung": "Falsche Farbe"},
                            {"kategorie": "ruecksendung", "beschreibung": "Jacken zurück"}], frist=None)
    t = baue_antwort(ex, {}, "kundenservice", "Reklamation", VERSENDER)
    assert "Das tut uns leid." in t
    assert "Ersatz" in t and "Rücksendeschein" in t
    assert "Wir prüfen den Stand" not in t  # beide Kategorien kommen ohne Systemdaten aus


def test_ohne_systemdaten_generischer_satz_genau_einmal():
    """Faellt ein System aus, darf die Antwort nichts behaupten, was wir nicht wissen."""
    ex = dict(EX, anliegen=[{"kategorie": "bestellstatus", "beschreibung": "Wo bleibt die Lieferung?"},
                            {"kategorie": "rechnung", "beschreibung": "Rechnungskopie"}], frist=None)
    t = baue_antwort(ex, {}, "kundenservice", "Lieferung", VERSENDER)
    assert t.count("Wir prüfen den Stand und melden uns heute noch.") == 1
    assert "B-2026-04711" not in t


def test_bestellstatus_ohne_sendungsnummer_und_ohne_liefertermin():
    """Nullbare ERP-Felder dürfen nicht als "None" im Brief landen."""
    b = dict(_eintrag("bestellungen.json", "bestellnummer", "B-2026-04711"),
             sendungsnummer=None, liefertermin=None)
    t = baue_antwort(dict(EX, frist=None), {"bestellung": b}, "kundenservice", "x", VERSENDER)
    assert "Ihre Bestellung B-2026-04711 vom 2026-09-09 ist versendet, voraussichtliche Zustellung folgt." in t
    assert "None" not in t
    assert "Sendungsnummer" not in t


def test_bestellstatus_ohne_liefertermin_in_den_uebrigen_zustaenden():
    for status in ("zugestellt", "kommissionierung", "offen"):
        b = dict(_eintrag("bestellungen.json", "bestellnummer", "B-2026-04733"),
                 status=status, liefertermin=None)
        t = baue_antwort(dict(EX, frist=None), {"bestellung": b}, "kundenservice", "x", VERSENDER)
        assert "None" not in t, status
        assert "B-2026-04733" in t, status
    b = dict(_eintrag("bestellungen.json", "bestellnummer", "B-2026-04733"), bestelldatum=None, status="versendet")
    assert "None" not in baue_antwort(dict(EX, frist=None), {"bestellung": b}, "kundenservice", "x", VERSENDER)


def test_teilgeliefert_ohne_offene_positionen_bleibt_neutral():
    """Alles geliefert, Kopf trotzdem teilgeliefert: keine leere Aufzählung."""
    b = dict(_eintrag("bestellungen.json", "bestellnummer", "B-2026-04702"),
             positionen=[dict(p, status="geliefert")
                         for p in _eintrag("bestellungen.json", "bestellnummer", "B-2026-04702")["positionen"]])
    t = baue_antwort(dict(EX, frist=None), {"bestellung": b}, "kundenservice", "x", VERSENDER)
    assert "Offen sind noch:" not in t
    assert "B-2026-04702 ist bisher nur teilweise geliefert" in t
    assert "None" not in t


def test_verfuegbarkeit_nennt_die_beantwortete_variante():
    """Nur die Größe genannt: der Brief muss sagen, für welche Farbe er antwortet."""
    ex = dict(EX, anliegen=[{"kategorie": "verfuegbarkeit", "beschreibung": "Lieferbar?"}], frist=None)
    sd = {"artikel": [{"artikelnummer": "A-4305", "groesse": "L", "farbe": "gelb",
                       "bestand": 70, "nachfolger": None}]}
    t = baue_antwort(ex, sd, "kundenservice", "x", VERSENDER)
    assert "Artikel A-4305 in Größe L, gelb ist lieferbar, Bestand 70 Stück." in t
