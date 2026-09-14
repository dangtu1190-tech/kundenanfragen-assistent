"""Anreicherung aus ERP, CRM und MES sowie das idempotente CRM-Ticket.

Die Tests arbeiten mit den Fakes aus app/integration/fake.py, befüllt aus den
echten Mockdaten. Sie prüfen zwei Dinge getrennt: dass die richtigen Daten
geladen werden und dass Unstimmigkeiten als Hinweis auffallen, statt still in
einen falschen Antwortsatz zu wandern.
"""
from datetime import date

import pytest

from app.anreicherung import anreichere, lege_ticket_an
from tests.conftest import baue_fake_systeme, lies_systemdatei

HEUTE = date(2026, 9, 14)

MAIL_M01 = {"id": "m01", "absender_name": "Jens Brandt", "absender_firma": "Dachdeckerei Brandt GmbH",
            "absender_email": "j.brandt@dachdeckerei-brandt.example",
            "betreff": "Warnschutzjacken Bestellung B-2026-04711", "text": "..."}
MAIL_M15 = {"id": "m15", "absender_name": "Martina Kessler", "absender_firma": "Elektro Kessler & Sohn GmbH & Co. KG",
            "absender_email": "m.kessler@elektro-kessler.example", "betreff": "Lieferung B-2026-4688", "text": "..."}
MAIL_M08 = {"id": "m08", "absender_name": "Ole Hansen", "absender_firma": "Tiefbau Hansen & Petersen GmbH",
            "absender_email": "o.hansen@hansen-petersen.example", "betreff": "Order B-2026-04750 delivery date",
            "text": "..."}
MAIL_M04 = {"id": "m04", "absender_name": "Sabine Reuter", "absender_firma": "Metallbau Reuter AG",
            "absender_email": "s.reuter@metallbau-reuter.example", "betreff": "Stickerei Auftrag V-2026-131",
            "text": "..."}
MAIL_M05 = {"id": "m05", "absender_name": "Frank Lorenz", "absender_firma": "Zimmerei Lorenz GmbH",
            "absender_email": "f.lorenz@zimmerei-lorenz.example", "betreff": "Ausstattung neue Mitarbeiter",
            "text": "..."}
MAIL_M07 = {"id": "m07", "absender_name": "Torben Mertens", "absender_firma": "SHK Mertens GmbH",
            "absender_email": "t.mertens@shk-mertens.example", "betreff": "Teillieferung B-2026-04702", "text": "..."}
MAIL_M06 = {"id": "m06", "absender_name": "Petra Nowak", "absender_firma": "Gebäudereinigung Sauber & Co. GmbH",
            "absender_email": "p.nowak@sauber-co.example", "betreff": "Rechnung R-2026-07731", "text": "..."}


def extraktion(**felder) -> dict:
    basis = {"kunde": {"firma": None, "kundennummer": None},
             "ansprechpartner": {"anrede": None, "name": None},
             "bezug": {"bestellnummer": None, "rechnungsnummer": None, "veredelungsauftrag": None},
             "artikel": [], "anliegen": [], "dringlichkeit": "mittel", "frist": None, "unklarheiten": []}
    basis.update(felder)
    return basis


def anliegen(*kategorien) -> list[dict]:
    return [{"kategorie": k, "beschreibung": f"Anliegen {k}"} for k in kategorien]


def test_m01_kontakt_kunde_und_bestellung(fake_systeme):
    ex = extraktion(kunde={"firma": "Dachdeckerei Brandt GmbH", "kundennummer": "K-10234"},
                    bezug={"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"), frist="2026-09-18")
    systemdaten, hinweise, fehler, unklar = anreichere(ex, MAIL_M01, fake_systeme, HEUTE)

    assert systemdaten["kontakt"]["kundennummer"] == "K-10234"
    assert systemdaten["kunde"]["firma"] == "Dachdeckerei Brandt GmbH"
    assert systemdaten["bestellung"]["status"] == "versendet"
    assert systemdaten["bestellung"]["sendungsnummer"] == "SN-7F3K9Q2L"
    assert hinweise == [] and fehler == [] and unklar == []
    assert "letzte_bestellungen" not in systemdaten  # nur bei Angeboten


def test_kundennummer_kommt_notfalls_aus_dem_kontakt(fake_systeme):
    """m15 nennt keine Kundennummer; die Absenderadresse führt trotzdem zum Kunden."""
    ex = extraktion(bezug={"bestellnummer": None, "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"))
    systemdaten, _, _, _ = anreichere(ex, MAIL_M15, fake_systeme, HEUTE)
    assert systemdaten["kontakt"]["kontakt_id"] == "C-502"
    assert systemdaten["kunde"]["kundennummer"] == "K-10311"


def test_m15_unbekannte_bestellnummer_wird_unklarheit(fake_systeme):
    """Der Tippfehler B-2026-4688 darf nicht still verschwinden."""
    ex = extraktion(bezug={"bestellnummer": "B-2026-4688", "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"))
    systemdaten, hinweise, fehler, unklar = anreichere(ex, MAIL_M15, fake_systeme, HEUTE)

    meldung = "Bestellnummer B-2026-4688 ist im ERP nicht bekannt"
    assert unklar == [meldung] and hinweise == [meldung]
    assert fehler == []
    assert "bestellung" not in systemdaten
    assert systemdaten["kontakt"]["kundennummer"] == "K-10311"


def test_m08_liefertermin_nach_frist(fake_systeme):
    ex = extraktion(bezug={"bestellnummer": "B-2026-04750", "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"), frist="2026-09-18")
    systemdaten, hinweise, fehler, unklar = anreichere(ex, MAIL_M08, fake_systeme, HEUTE)

    assert systemdaten["bestellung"]["liefertermin"] == "2026-09-19"
    assert hinweise == ["Liefertermin 2026-09-19 liegt nach der genannten Frist 2026-09-18"]
    assert fehler == [] and unklar == []


def test_m04_veredelung_auf_maschine_in_stoerung(fake_systeme):
    """Die Mockdaten legen V-2026-131 auf STK-02, die eine Störung meldet: der Hinweis muss kommen."""
    ex = extraktion(bezug={"bestellnummer": "B-2026-04733", "rechnungsnummer": None,
                           "veredelungsauftrag": "V-2026-131"}, anliegen=anliegen("veredelung"), frist="2026-09-22")
    systemdaten, hinweise, fehler, unklar = anreichere(ex, MAIL_M04, fake_systeme, HEUTE)

    assert systemdaten["veredelung"]["status"] == "in_produktion"
    assert systemdaten["maschine"]["maschine"] == "STK-02" and systemdaten["maschine"]["zustand"] == "stoerung"
    assert systemdaten["bestellung"]["bestellnummer"] == "B-2026-04733"
    assert hinweise == ["Maschine STK-02 meldet Störung, geplantes Ende gefährdet"]
    assert fehler == [] and unklar == []


def test_m04_laufende_maschine_ohne_hinweis():
    maschinen = [dict(m, zustand="laeuft", meldung=None) if m["maschine"] == "STK-02" else m
                 for m in lies_systemdatei("maschinen.json")]
    systeme = baue_fake_systeme(maschinen=maschinen)
    ex = extraktion(bezug={"bestellnummer": None, "rechnungsnummer": None, "veredelungsauftrag": "V-2026-131"},
                    anliegen=anliegen("veredelung"))
    _, hinweise, fehler, _ = anreichere(ex, MAIL_M04, systeme, HEUTE)

    assert hinweise == []
    assert fehler == []


def test_unbekannter_veredelungsauftrag_wird_unklarheit(fake_systeme):
    ex = extraktion(bezug={"bestellnummer": None, "rechnungsnummer": None, "veredelungsauftrag": "V-2026-999"},
                    anliegen=anliegen("veredelung"))
    systemdaten, hinweise, _, unklar = anreichere(ex, MAIL_M04, fake_systeme, HEUTE)
    assert unklar == ["Veredelungsauftrag V-2026-999 ist im MES nicht bekannt"] and hinweise == unklar
    assert "veredelung" not in systemdaten


def test_bestellung_gehoert_anderem_kunden(fake_systeme):
    """Kontakt K-10311 fragt nach einer Bestellung von K-10234: das muss auffallen."""
    ex = extraktion(bezug={"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"))
    _, hinweise, fehler, unklar = anreichere(ex, MAIL_M15, fake_systeme, HEUTE)

    assert hinweise == ["Bestellung B-2026-04711 gehört zu Kunde K-10234, Absender ist K-10311"]
    assert fehler == [] and unklar == []


def test_rechnung_wird_geladen_und_unbekannte_gemeldet(fake_systeme):
    ex = extraktion(bezug={"bestellnummer": None, "rechnungsnummer": "R-2026-07731", "veredelungsauftrag": None},
                    anliegen=anliegen("rechnung"))
    systemdaten, hinweise, _, unklar = anreichere(ex, MAIL_M06, fake_systeme, HEUTE)
    assert systemdaten["rechnung"]["betrag"] == 1284.5 and hinweise == [] and unklar == []

    ex = extraktion(bezug={"bestellnummer": None, "rechnungsnummer": "R-2026-00001", "veredelungsauftrag": None},
                    anliegen=anliegen("rechnung"))
    systemdaten, hinweise, _, unklar = anreichere(ex, MAIL_M06, fake_systeme, HEUTE)
    assert unklar == ["Rechnungsnummer R-2026-00001 ist im ERP nicht bekannt"] and hinweise == unklar


def test_artikelverfuegbarkeit_mit_nachfolger(fake_systeme):
    """m07 fragt nach A-4210 in navy XL: Bestand 0, Nachfolger A-4211."""
    ex = extraktion(bezug={"bestellnummer": "B-2026-04702", "rechnungsnummer": None, "veredelungsauftrag": None},
                    artikel=[{"artikelnummer": "A-4210", "bezeichnung": "Softshelljacke", "groesse": "XL",
                              "farbe": "navy", "menge": 2}],
                    anliegen=anliegen("bestellstatus", "verfuegbarkeit"))
    systemdaten, _, _, _ = anreichere(ex, MAIL_M07, fake_systeme, HEUTE)

    assert systemdaten["artikel"] == [{"artikelnummer": "A-4210", "groesse": "XL", "farbe": "navy",
                                       "bestand": 0, "nachfolger": "A-4211"}]


def test_ueberschrittener_liefertermin_faellt_auf(fake_systeme):
    """m07: Liefertermin 2026-09-10 vorbei, Bestellung steht auf teilgeliefert."""
    ex = extraktion(bezug={"bestellnummer": "B-2026-04702", "rechnungsnummer": None, "veredelungsauftrag": None},
                    anliegen=anliegen("bestellstatus"))
    _, hinweise, _, unklar = anreichere(ex, MAIL_M07, fake_systeme, HEUTE)
    assert hinweise == ["Liefertermin 2026-09-10 ist überschritten, Bestellung steht auf teilgeliefert"]
    assert unklar == []


def test_letzte_bestellungen_nur_bei_angebot(fake_systeme):
    ex = extraktion(kunde={"firma": None, "kundennummer": "K-10802"}, anliegen=anliegen("angebot"))
    systemdaten, _, _, _ = anreichere(ex, MAIL_M05, fake_systeme, HEUTE)
    assert [b["bestellnummer"] for b in systemdaten["letzte_bestellungen"]] == ["B-2026-04120"]


def test_erp_ausfall_bricht_nicht_ab(fake_systeme):
    fake_systeme.ausgefallen.add("erp")
    ex = extraktion(kunde={"firma": None, "kundennummer": "K-10234"},
                    bezug={"bestellnummer": "B-2026-04711", "rechnungsnummer": None,
                           "veredelungsauftrag": "V-2026-131"}, anliegen=anliegen("bestellstatus"))
    systemdaten, hinweise, fehler, unklar = anreichere(ex, MAIL_M01, fake_systeme, HEUTE)

    assert fehler == ["erp: simulierter Ausfall"]  # ein Eintrag je System, nicht je Aufruf
    assert systemdaten["kontakt"]["kundennummer"] == "K-10234"  # CRM laeuft weiter
    assert systemdaten["veredelung"]["auftrag"] == "V-2026-131"  # MES laeuft weiter
    assert "bestellung" not in systemdaten and "kunde" not in systemdaten
    assert unklar == []  # ein Ausfall ist keine Rückfrage an den Kunden
    assert hinweise == ["Maschine STK-02 meldet Störung, geplantes Ende gefährdet"]  # MES läuft weiter


def test_ticket_ist_idempotent(fake_systeme):
    ergebnis = {"extraktion": extraktion(kunde={"firma": None, "kundennummer": "K-10234"},
                                         anliegen=anliegen("bestellstatus")),
                "systemdaten": {}, "integrationsfehler": [], "zustaendigkeit": "kundenservice",
                "dringlichkeit": "hoch"}
    erstes = lege_ticket_an(ergebnis, MAIL_M01, fake_systeme)
    zweites = lege_ticket_an(ergebnis, MAIL_M01, fake_systeme)

    assert erstes["ticket_id"] == zweites["ticket_id"]
    assert erstes["externe_referenz"] == "m01"
    assert erstes["kategorien"] == ["bestellstatus"] and erstes["prioritaet"] == "hoch"
    assert erstes["zustaendigkeit"] == "kundenservice"
    assert erstes["zusammenfassung"] == "Anliegen bestellstatus"
    assert erstes["kontakt_email"] == "j.brandt@dachdeckerei-brandt.example"
    assert erstes["kundennummer"] == "K-10234"


def test_ticket_bei_crm_ausfall(fake_systeme):
    fake_systeme.ausgefallen.add("crm")
    ergebnis = {"extraktion": extraktion(anliegen=anliegen("sonstiges")), "systemdaten": {},
                "integrationsfehler": [], "zustaendigkeit": "kundenservice", "dringlichkeit": "niedrig"}
    assert lege_ticket_an(ergebnis, MAIL_M01, fake_systeme) is None
    assert ergebnis["integrationsfehler"] == ["crm: simulierter Ausfall"]


@pytest.mark.parametrize("mail_id", ["m01", "m15"])
def test_anreicherung_ohne_extraktionsfelder_stuerzt_nicht(fake_systeme, mail_id):
    mail = {"id": mail_id, "absender_email": "unbekannt@example.org", "betreff": "", "text": ""}
    systemdaten, hinweise, fehler, unklar = anreichere({}, mail, fake_systeme, HEUTE)
    assert systemdaten == {} and hinweise == [] and fehler == [] and unklar == []


def test_artikel_nennt_die_gewaehlte_variante(fake_systeme):
    """m01 nennt nur die Größe L; A-4305 gibt es in gelb und orange. Die Antwort
    muss festhalten, für welche Variante der Bestand gilt."""
    ex = extraktion(artikel=[{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "L",
                              "farbe": None, "menge": 6}],
                    anliegen=anliegen("verfuegbarkeit"))
    systemdaten, _, _, _ = anreichere(ex, MAIL_M01, fake_systeme, HEUTE)
    assert systemdaten["artikel"] == [{"artikelnummer": "A-4305", "groesse": "L", "farbe": "gelb",
                                       "bestand": 70, "nachfolger": None}]


def test_artikel_ohne_passende_variante_bleibt_ohne_bestand(fake_systeme):
    ex = extraktion(artikel=[{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "3XL",
                              "farbe": None, "menge": 1}],
                    anliegen=anliegen("verfuegbarkeit"))
    systemdaten, _, _, _ = anreichere(ex, MAIL_M01, fake_systeme, HEUTE)
    assert systemdaten["artikel"] == [{"artikelnummer": "A-4305", "groesse": "3XL", "farbe": None,
                                       "bestand": None, "nachfolger": None}]
