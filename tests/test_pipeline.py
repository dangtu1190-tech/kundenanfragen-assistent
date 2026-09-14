import json
import re
from datetime import date

from app.kalender import lade_kalender
from app.llm_client import FakeClient
from app.pipeline import verarbeite
from app.speicher import lade_mails

HEUTE = date(2026, 9, 14)
ANTWORT = {
    "kunde": {"firma": "[FIRMA_1]"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "anlage": {"typ": "Vakuumhärteofen", "nummer": None, "baujahr": 2019},
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": ["Anlagennummer fehlt"],
}


def test_alle_mails_laden():
    mails = lade_mails()
    assert len(mails) == 15
    assert {m["id"] for m in mails} == {f"m{i:02d}" for i in range(1, 16)}


def test_modell_sieht_keine_originale():
    mails = lade_mails()
    kal = lade_kalender("data/kalender.json")
    for mail in mails:
        fake = FakeClient(ANTWORT)
        erg = verarbeite(mail, fake, kal, HEUTE)
        gesendet = fake.aufrufe[0]
        assert gesendet == erg["pseudonym_text"]
        assert mail["absender_email"] not in gesendet
        assert mail["absender_firma"] not in gesendet
        for eintrag in erg["platzhalter"]:
            assert eintrag["original"] not in gesendet, (mail["id"], eintrag)
        nachname = mail["absender_name"].split()[-1]
        assert nachname not in gesendet, mail["id"]


def test_ergebnis_felder_und_rueckersetzung():
    mail = lade_mails()[0]
    erg = verarbeite(mail, FakeClient(ANTWORT), lade_kalender("data/kalender.json"), HEUTE)
    assert erg["mail_id"] == "m01"
    assert erg["status"] == "offen"
    assert erg["extraktion"]["ansprechpartner"]["name"] == "Frank Lindemann"
    assert erg["extraktion"]["kunde"]["firma"] == "Hartmann Wärmebehandlung GmbH"
    assert erg["termin"] == {"datum": "2026-09-21", "techniker": "T2", "qualifikation": "mechanik", "hinweis": ""}
    assert erg["ersatzteile"] == []
    assert "Frank Lindemann" not in erg["pseudonym_text"]
    assert "Hartmann" not in erg["pseudonym_text"]
    assert "[" not in erg["antwort_entwurf"]
    assert erg["anbieter"] == "fake" and erg["dauer_ms"] >= 0 and erg["zeitpunkt"]
    json.dumps(erg)  # muss serialisierbar sein


def test_ungueltige_modellantwort_wird_pruefung_noetig():
    mail = lade_mails()[0]
    erg = verarbeite(mail, FakeClient("kein json"), lade_kalender("data/kalender.json"), HEUTE)
    assert erg["status"] == "pruefung_noetig"
    assert erg["extraktion"] is None and "JSON" in erg["extraktion_fehler"]
    assert erg["termin"] is None
    assert "Frank Lindemann" not in erg["pseudonym_text"]


_GENERISCH = {"gmbh", "ag", "kg", "kgaa", "se", "ohg", "co.", "co", "&", "ltd.", "ltd", "inc.", "und", "e.k."}


def _woerter(wert: str) -> set[str]:
    """Alle durch Leerraum getrennten Teile ab drei Zeichen, ohne Rechtsform-Kürzel."""
    return {t for t in wert.split() if len(t) >= 3 and t.lower() not in _GENERISCH}


def test_kein_original_erreicht_das_modell():
    """Schaerfer als test_modell_sieht_keine_originale: auch Namensteile und
    Bestandteile jedes Platzhalter-Originals duerfen nicht im Prompt stehen."""
    kal = lade_kalender("data/kalender.json")
    for mail in lade_mails():
        fake = FakeClient(ANTWORT)
        erg = verarbeite(mail, fake, kal, HEUTE)
        gesendet = fake.aufrufe[0]
        verboten = {mail["absender_email"], mail["absender_firma"]} | _woerter(mail["absender_name"]) \
            | _woerter(mail["absender_firma"])
        for eintrag in erg["platzhalter"]:
            verboten.add(eintrag["original"])
            verboten |= _woerter(eintrag["original"])
        for wert in verboten:
            if not wert:
                continue
            muster = re.compile(r"(?<!\w)" + re.escape(wert) + r"(?!\w)", re.IGNORECASE)
            assert not muster.search(gesendet), (mail["id"], wert)


def test_von_zeile_und_auslandstelefon_werden_pseudonymisiert():
    """Regression: Vorname in zitierter 'Von:'-Zeile (m06) und internationale
    Telefonnummer ohne +49 (m07) duerfen den Prompt nicht erreichen; die
    Seriennummer bleibt sichtbar."""
    kal = lade_kalender("data/kalender.json")
    mails = {m["id"]: m for m in lade_mails()}

    fake = FakeClient(ANTWORT)
    verarbeite(mails["m06"], fake, kal, HEUTE)
    gesendet = fake.aufrufe[0]
    assert "Bernd" not in gesendet and "Kolb" not in gesendet

    fake = FakeClient(ANTWORT)
    verarbeite(mails["m07"], fake, kal, HEUTE)
    gesendet = fake.aufrufe[0]
    assert "+44 1234 567890" not in gesendet
    assert "VIM-2200-0417" in gesendet


# Erwartete Platzhaltertypen je Mail, aus dem Mailtext abgelesen (nicht aus dem
# Ergebnis der Pseudonymisierung erzeugt). FIRMA und NAME stehen ueberall, weil
# Absenderfirma und Absendername immer einen Platzhalter bekommen. Ein
# uebersehenes Feld - etwa die Adresse "Am Gewerbepark 12" in m01 - laesst diesen
# Test scheitern, ein Test gegen die eigene Ausgabe koennte das nicht.
ERWARTETE_TYPEN = {
    "m01": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m02": {"FIRMA", "NAME", "TELEFON"},
    "m03": {"FIRMA", "NAME"},
    "m04": {"FIRMA", "NAME", "ADRESSE", "ORT"},
    "m05": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m06": {"FIRMA", "NAME"},
    "m07": {"FIRMA", "NAME", "TELEFON"},
    "m08": {"FIRMA", "NAME", "TELEFON"},
    "m09": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m10": {"FIRMA", "NAME", "TELEFON"},
    "m11": {"FIRMA", "NAME"},
    "m12": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m13": {"FIRMA", "NAME", "TELEFON"},
    "m14": {"FIRMA", "NAME"},
    "m15": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
}


def test_erwartete_platzhaltertypen_je_mail():
    kal = lade_kalender("data/kalender.json")
    for mail in lade_mails():
        erg = verarbeite(mail, FakeClient(ANTWORT), kal, HEUTE)
        typen = {e["typ"] for e in erg["platzhalter"]}
        assert typen == ERWARTETE_TYPEN[mail["id"]], mail["id"]


def test_name_und_firma_bleiben_zusammen_nicht_lesbar():
    """Absender, der wie seine Firma heisst: aus der Signatur darf nicht
    '[NAME_1] [FIRMA_1]' werden - sonst laesst sich der Nachname zurueckrechnen."""
    kal = lade_kalender("data/kalender.json")
    mails = {m["id"]: m for m in lade_mails()}
    for mail_id in ("m02", "m03", "m09", "m12", "m14"):
        erg = verarbeite(mails[mail_id], FakeClient(ANTWORT), kal, HEUTE)
        assert re.search(r"\[NAME_\d+\] \[FIRMA_\d+\]", erg["pseudonym_text"]) is None, mail_id


def test_anlagennummern_erreichen_das_modell():
    """Bewusst: Anlagen-/Seriennummern und Fehlercodes sind keine Platzhalter."""
    kal = lade_kalender("data/kalender.json")
    erwartet = {"m02": ["VIM-3000-0917", "F-217"], "m03": ["R 03/118"], "m10": ["VSP-1800-0221"], "m15": ["4711-0815-22"]}
    for mail in lade_mails():
        if mail["id"] in erwartet:
            fake = FakeClient(ANTWORT)
            verarbeite(mail, fake, kal, HEUTE)
            for wert in erwartet[mail["id"]]:
                assert wert in fake.aufrufe[0], (mail["id"], wert)
