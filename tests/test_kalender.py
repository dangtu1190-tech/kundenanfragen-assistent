from datetime import date
from app.kalender import belege, erzeuge_kalender, finde_termin, gebe_frei, qualifikation_fuer

HEUTE = date(2026, 9, 14)


def _kal():
    kal = erzeuge_kalender(HEUTE, wochen=3)
    # T1 (elektrik, steuerung) die ganze erste Woche unterwegs, T3 (steuerung) am 16./17.09.
    for tag in kal["tage"]:
        if tag["datum"] <= "2026-09-18":
            tag["belegt"].append("T1")
        if tag["datum"] in ("2026-09-16", "2026-09-17"):
            tag["belegt"].append("T3")
    return kal


def _ex(**kw):
    basis = {"zustaendigkeit": "service", "dringlichkeit": "mittel",
             "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"}],
             "wunschzeitraum": {"von": None, "bis": None, "tageszeit": "egal"}}
    basis.update(kw)
    return basis


def test_kalender_struktur():
    kal = erzeuge_kalender(HEUTE, wochen=1)
    assert [t["datum"] for t in kal["tage"]] == ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"]
    assert {t["kuerzel"] for t in kal["techniker"]} == {"T1", "T2", "T3", "T4", "T5"}
    assert all(t["belegt"] == [] for t in kal["tage"])


def test_qualifikation_aus_anliegen():
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode F-217 am Bedienfeld"}])) == "steuerung"
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Vakuum wird nicht erreicht, Pumpe laut"}])) == "vakuumtechnik"
    assert qualifikation_fuer(_ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Heizung fällt aus, Sicherung fliegt"}])) == "elektrik"
    assert qualifikation_fuer(_ex()) == "mechanik"


def test_produktwort_vakuumofen_ist_keine_vakuumstoerung():
    """Der Anlagenname enthaelt fast immer "Vakuum"; die Qualifikation muss
    sich am Fehlerbild entscheiden, nicht am Maschinenwort."""
    elektrik = _ex(anliegen=[{"kategorie": "stoerung", "beschreibung":
                              "Heizung des Vakuumofens VK-3600-0304 fällt aus, Sicherung im Schaltschrank löst aus"}])
    assert qualifikation_fuer(elektrik) == "elektrik"
    wartung = _ex(anliegen=[{"kategorie": "wartung", "beschreibung": "Jahreswartung am Vakuumhärteofen"}])
    assert qualifikation_fuer(wartung) == "mechanik"
    vakuum = _ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Vakuum wird nicht erreicht, 5x10-2 mbar"}])
    assert qualifikation_fuer(vakuum) == "vakuumtechnik"


def test_ohne_wunsch_ab_morgen_mit_passendem_techniker():
    t = finde_termin(_kal(), _ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode E12 Steuerung"}]), HEUTE)
    # T1 ist die ganze Woche belegt, T3 hat Steuerung und ist am 15.09. frei
    assert t == {"datum": "2026-09-15", "techniker": "T3", "qualifikation": "steuerung", "hinweis": ""}


def test_wunschzeitraum_ausgebucht_naechster_danach():
    ex = _ex(anliegen=[{"kategorie": "stoerung", "beschreibung": "Fehlercode E12 Steuerung"}],
             wunschzeitraum={"von": "2026-09-16", "bis": "2026-09-17", "tageszeit": "egal"})
    t = finde_termin(_kal(), ex, HEUTE)
    assert t["datum"] == "2026-09-18" and t["techniker"] == "T3"
    assert "außerhalb" in t["hinweis"]


def test_stillstand_zieht_vor():
    ex = _ex(dringlichkeit="stillstand", anliegen=[{"kategorie": "stoerung", "beschreibung": "Heizung tot, Anlage steht"}],
             wunschzeitraum={"von": "2026-09-28", "bis": "2026-09-30", "tageszeit": "egal"})
    t = finde_termin(_kal(), ex, HEUTE)
    assert t["datum"] == "2026-09-14" and t["qualifikation"] == "elektrik" and t["techniker"] == "T4"
    assert "vorgezogen" in t["hinweis"]


def test_vertrieb_und_nur_ersatzteil_kein_termin():
    assert finde_termin(_kal(), _ex(zustaendigkeit="vertrieb"), HEUTE) is None
    assert finde_termin(_kal(), _ex(anliegen=[{"kategorie": "ersatzteil", "beschreibung": "Heizelement"}]), HEUTE) is None


def test_bis_vor_von_wird_offener_zeitraum():
    t = finde_termin(_kal(), _ex(wunschzeitraum={"von": "2026-09-25", "bis": "2026-09-14", "tageszeit": "egal"}), HEUTE)
    assert t["datum"] == "2026-09-25" and t["hinweis"] == ""


def test_belegen_und_freigeben():
    kal = _kal()
    assert belege(kal, "2026-09-15", "T3") is True
    assert "T3" in [t for t in kal["tage"] if t["datum"] == "2026-09-15"][0]["belegt"]
    assert belege(kal, "2026-09-15", "T3") is False   # schon belegt
    assert belege(kal, "2099-01-01", "T3") is False
    assert gebe_frei(kal, "2026-09-15", "T3") is True
    assert gebe_frei(kal, "2026-09-15", "T3") is False
