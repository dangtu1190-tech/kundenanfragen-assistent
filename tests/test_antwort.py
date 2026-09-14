from app.antwort import baue_antwort

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
