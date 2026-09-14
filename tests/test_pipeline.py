import json
import re
from datetime import date

from app.llm_client import FakeClient
from app.pipeline import verarbeite
from app.speicher import lade_mails

HEUTE = date(2026, 9, 14)
ANTWORT = {
    "kunde": {"firma": "[FIRMA_1]", "kundennummer": "K-10234"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "bezug": {"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
    "artikel": [{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "L",
                 "farbe": "gelb", "menge": 6}],
    "anliegen": [{"kategorie": "bestellstatus", "beschreibung": "Frage nach dem Liefertermin"}],
    "dringlichkeit": "hoch",
    "frist": "2026-09-18",
    "unklarheiten": ["angekündigter Anhang fehlt"],
}

ERGEBNISFELDER = {
    "mail_id", "roh_text", "pseudonym_text", "platzhalter", "extraktion", "extraktion_fehler",
    "extraktion_hinweise", "systemdaten", "hinweise", "integrationsfehler", "zustaendigkeit",
    "dringlichkeit", "dringlichkeit_grund", "antwort_entwurf", "ticket", "status", "anbieter",
    "modell", "dauer_ms", "zeitpunkt",
}


def test_alle_mails_laden():
    mails = lade_mails()
    assert len(mails) == 15
    assert {m["id"] for m in mails} == {f"m{i:02d}" for i in range(1, 16)}


def test_modell_sieht_keine_originale():
    for mail in lade_mails():
        fake = FakeClient(ANTWORT)
        erg = verarbeite(mail, fake, HEUTE)
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
    erg = verarbeite(mail, FakeClient(ANTWORT), HEUTE)
    assert set(erg) == ERGEBNISFELDER
    assert erg["mail_id"] == "m01" and erg["status"] == "offen"
    assert erg["extraktion"]["ansprechpartner"]["name"] == "Jens Brandt"
    assert erg["extraktion"]["kunde"]["firma"] == "Dachdeckerei Brandt GmbH"
    assert erg["extraktion"]["bezug"]["bestellnummer"] == "B-2026-04711"
    assert "Jens Brandt" not in erg["pseudonym_text"]
    assert "Dachdeckerei" not in erg["pseudonym_text"]
    assert "[" not in erg["antwort_entwurf"]
    assert "Berufskleidung Nord GmbH" in erg["antwort_entwurf"]
    assert erg["anbieter"] == "fake" and erg["dauer_ms"] >= 0 and erg["zeitpunkt"]
    json.dumps(erg)  # muss serialisierbar sein


def test_ohne_systemlandschaft_bleiben_die_systemfelder_leer():
    """Ohne Systeme laufen Pseudonymisierung, Extraktion, Regeln und Entwurf
    trotzdem durch; der Modellvergleich braucht genau diesen Weg."""
    erg = verarbeite(lade_mails()[0], FakeClient(ANTWORT), HEUTE)
    assert erg["systemdaten"] == {} and erg["hinweise"] == [] and erg["integrationsfehler"] == []
    assert erg["ticket"] is None and erg["status"] == "offen"
    assert erg["zustaendigkeit"] == "kundenservice"
    # Frist 2026-09-18 sind vier Werktage ab Montag: die Fristregel greift nicht,
    # das hoch kommt aus dem Modell.
    assert erg["dringlichkeit"] == "hoch" and erg["dringlichkeit_grund"] is None


def test_extraktion_hinweise_landen_im_ergebnis():
    kaputt = dict(ANTWORT, dringlichkeit="sehr hoch")
    erg = verarbeite(lade_mails()[0], FakeClient(kaputt), HEUTE)
    assert erg["status"] == "offen"
    assert erg["extraktion_hinweise"] == ["dringlichkeit 'sehr hoch' ungültig, auf 'mittel' gesetzt"]
    assert erg["dringlichkeit"] == "mittel"


def test_ungueltige_modellantwort_wird_pruefung_noetig():
    erg = verarbeite(lade_mails()[0], FakeClient("kein json"), HEUTE)
    assert erg["status"] == "pruefung_noetig"
    assert erg["extraktion"] is None and "JSON" in erg["extraktion_fehler"]
    assert erg["antwort_entwurf"] == ""
    assert "Jens Brandt" not in erg["pseudonym_text"]


_GENERISCH = {"gmbh", "ag", "kg", "kgaa", "se", "ohg", "co.", "co", "&", "ltd.", "ltd", "inc.", "und", "e.k.", "lda"}


def _woerter(wert: str) -> set[str]:
    """Alle durch Leerraum getrennten Teile ab drei Zeichen, ohne Rechtsform-Kürzel."""
    return {t for t in wert.split() if len(t) >= 3 and t.lower() not in _GENERISCH}


def test_kein_original_erreicht_das_modell():
    """Schaerfer als test_modell_sieht_keine_originale: auch Namensteile und
    Bestandteile jedes Platzhalter-Originals duerfen nicht im Prompt stehen."""
    for mail in lade_mails():
        fake = FakeClient(ANTWORT)
        erg = verarbeite(mail, fake, HEUTE)
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


# Erwartete Platzhaltertypen je Mail, aus dem Mailtext abgelesen (nicht aus dem
# Ergebnis der Pseudonymisierung erzeugt). FIRMA und NAME stehen ueberall, auch
# in m10: Absendername und Absenderfirma bekommen in anonymisiere() immer einen
# Platzhalter, selbst wenn sie im Text gar nicht vorkommen. Ein uebersehenes
# Feld - etwa die Adresse "Ziegeleiweg 18" in m01 - laesst diesen Test
# scheitern, ein Test gegen die eigene Ausgabe koennte das nicht.
# m14 ist die bekannte Grenze: die portugiesische Anschrift ("Rua da Fabrica 40",
# "4400-123 Vila Nova de Gaia") passt auf kein deutsches Strassen- oder
# PLZ-Muster und bleibt stehen.
ERWARTETE_TYPEN = {
    "m01": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m02": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m03": {"FIRMA", "NAME", "ADRESSE", "ORT"},
    "m04": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m05": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m06": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON", "EMAIL"},
    "m07": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m08": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m09": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON", "EMAIL"},
    "m10": {"FIRMA", "NAME", "TELEFON"},
    "m11": {"FIRMA", "NAME", "ADRESSE", "ORT"},
    "m12": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m13": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
    "m14": {"FIRMA", "NAME", "TELEFON", "EMAIL"},
    "m15": {"FIRMA", "NAME", "ADRESSE", "ORT", "TELEFON"},
}


def test_erwartete_platzhaltertypen_je_mail():
    for mail in lade_mails():
        erg = verarbeite(mail, FakeClient(ANTWORT), HEUTE)
        typen = {e["typ"] for e in erg["platzhalter"]}
        assert typen == ERWARTETE_TYPEN[mail["id"]], mail["id"]


def test_zweiter_name_in_der_weiterleitung():
    """m09 zitiert eine Mail eines Kollegen: auch dessen Name und Adresse
    duerfen das Modell nicht erreichen."""
    mail = [m for m in lade_mails() if m["id"] == "m09"][0]
    fake = FakeClient(ANTWORT)
    erg = verarbeite(mail, fake, HEUTE)
    originale = [e["original"] for e in erg["platzhalter"]]
    assert "Kevin Braun" in originale and "k.braun@kfz-adler.example" in originale
    assert "Kevin" not in fake.aufrufe[0] and "Braun" not in fake.aufrufe[0]


def test_name_und_firma_bleiben_zusammen_nicht_lesbar():
    """Absender, der wie seine Firma heisst: aus der Signatur darf nicht
    '[NAME_1] [FIRMA_1]' werden - sonst laesst sich der Nachname zurueckrechnen."""
    mails = {m["id"]: m for m in lade_mails()}
    for mail_id in ("m01", "m03", "m04", "m05", "m11", "m13"):
        erg = verarbeite(mails[mail_id], FakeClient(ANTWORT), HEUTE)
        assert re.search(r"\[NAME_\d+\] \[FIRMA_\d+\]", erg["pseudonym_text"]) is None, mail_id


KENNUNGEN_JE_MAIL = {
    "m01": ["B-2026-04711", "K-10234"], "m02": ["B-2026-04688", "A-4101"],
    "m03": ["B-2026-04590"], "m04": ["V-2026-131", "B-2026-04733"],
    "m05": ["K-10802"], "m06": ["R-2026-07731"], "m07": ["B-2026-04702", "A-4210"],
    "m08": ["B-2026-04750"], "m09": ["V-2026-140"], "m10": ["B-2026-04711"],
    "m11": ["A-4520"], "m12": ["A-4610", "B-2026-04699"], "m13": ["B-2026-04761"],
    "m15": ["B-2026-4688"],
}


def test_kennungen_erreichen_das_modell():
    """Bewusst: Kennungen sind keine personenbezogenen Daten und werden
    buchstabengetreu durchgereicht - auch der Tippfehler in m15."""
    mails = {m["id"]: m for m in lade_mails()}
    for mail_id, kennungen in KENNUNGEN_JE_MAIL.items():
        fake = FakeClient(ANTWORT)
        verarbeite(mails[mail_id], fake, HEUTE)
        for kennung in kennungen:
            assert kennung in fake.aufrufe[0], (mail_id, kennung)


def _mail(mail_id: str) -> dict:
    return {m["id"]: m for m in lade_mails()}[mail_id]


def test_anreicherung_regeln_und_ticket(fake_systeme):
    erg = verarbeite(_mail("m01"), FakeClient(ANTWORT), HEUTE, fake_systeme)

    assert set(erg) == ERGEBNISFELDER
    assert erg["systemdaten"]["bestellung"]["status"] == "versendet"
    assert erg["systemdaten"]["kontakt"]["kundennummer"] == "K-10234"
    assert erg["zustaendigkeit"] == "kundenservice"
    assert erg["dringlichkeit"] == "hoch" and erg["dringlichkeit_grund"] is None
    assert erg["ticket"]["ticket_id"] and erg["ticket"]["status"] == "offen"
    assert set(erg["ticket"]) == {"ticket_id", "status"}
    assert erg["hinweise"] == [] and erg["integrationsfehler"] == [] and erg["status"] == "offen"
    assert "SN-7F3K9Q2L" in erg["antwort_entwurf"]
    json.dumps(erg)


def test_zweiter_lauf_erzeugt_kein_zweites_ticket(fake_systeme):
    erste = verarbeite(_mail("m01"), FakeClient(ANTWORT), HEUTE, fake_systeme)
    zweite = verarbeite(_mail("m01"), FakeClient(ANTWORT), HEUTE, fake_systeme)
    assert erste["ticket"]["ticket_id"] == zweite["ticket"]["ticket_id"]


def test_systemausfall_wird_pruefung_noetig(fake_systeme):
    """Ausfall heisst: weiterarbeiten, nichts behaupten, zur Prüfung vorlegen."""
    fake_systeme.ausgefallen.add("erp")
    erg = verarbeite(_mail("m01"), FakeClient(ANTWORT), HEUTE, fake_systeme)

    assert erg["status"] == "pruefung_noetig"
    assert erg["integrationsfehler"] == ["erp: simulierter Ausfall"]
    assert "bestellung" not in erg["systemdaten"]
    assert "Wir prüfen den Stand und melden uns heute noch." in erg["antwort_entwurf"]
    assert "SN-7F3K9Q2L" not in erg["antwort_entwurf"]
    assert erg["ticket"]["ticket_id"]  # das CRM läuft, das Ticket entsteht trotzdem


def test_unbekannte_bestellnummer_wird_zur_rueckfrage(fake_systeme):
    """m15 nennt B-2026-4688 statt B-2026-04688: der Entwurf fragt nach."""
    antwort = dict(ANTWORT, kunde={"firma": "[FIRMA_1]", "kundennummer": None},
                   ansprechpartner={"anrede": "Frau", "name": "[NAME_1]"},
                   bezug={"bestellnummer": "B-2026-4688", "rechnungsnummer": None, "veredelungsauftrag": None},
                   artikel=[], dringlichkeit="mittel", frist=None, unklarheiten=[])
    erg = verarbeite(_mail("m15"), FakeClient(antwort), HEUTE, fake_systeme)

    meldung = "Bestellnummer B-2026-4688 ist im ERP nicht bekannt"
    assert erg["hinweise"] == [meldung]
    assert erg["extraktion"]["unklarheiten"] == [meldung]
    assert meldung in erg["antwort_entwurf"]
    assert erg["status"] == "offen"  # unbekannte Kennung ist kein Integrationsfehler
    assert erg["systemdaten"]["kunde"]["kundennummer"] == "K-10311"


def test_reklamation_hebt_die_dringlichkeit(fake_systeme):
    antwort = dict(ANTWORT, anliegen=[{"kategorie": "reklamation", "beschreibung": "Falsche Farbe"}],
                   dringlichkeit="niedrig", frist=None)
    erg = verarbeite(_mail("m13"), FakeClient(antwort), HEUTE, fake_systeme)
    assert erg["dringlichkeit"] == "hoch" and erg["dringlichkeit_grund"] == "Reklamation"
    assert erg["zustaendigkeit"] == "kundenservice"
