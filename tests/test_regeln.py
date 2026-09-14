"""Regeln für Zuständigkeit und Dringlichkeit: bewusst im Code, nicht im Modell.

Die Zuständigkeit folgt einer festen Rangfolge, die Dringlichkeit darf das
Modell nur nach unten bestimmen: Frist innerhalb von drei Werktagen oder eine
Reklamation heben sie immer auf hoch.
"""
from datetime import date

from app.regeln import dringlichkeit, werktage_bis, zustaendigkeit

HEUTE = date(2026, 9, 14)  # Montag


def test_zustaendigkeit_rangfolge():
    assert zustaendigkeit(["bestellstatus"]) == "kundenservice"
    assert zustaendigkeit(["veredelung", "angebot"]) == "veredelung"
    assert zustaendigkeit(["angebot"]) == "vertrieb"
    assert zustaendigkeit(["rechnung", "bestellstatus"]) == "buchhaltung"
    assert zustaendigkeit(["reklamation", "veredelung"]) == "kundenservice"
    assert zustaendigkeit([]) == "kundenservice"


def test_werktage():
    assert werktage_bis(HEUTE, date(2026, 9, 18)) == 4
    assert werktage_bis(HEUTE, date(2026, 9, 22)) == 6
    assert werktage_bis(HEUTE, date(2026, 9, 14)) == 0


def test_werktage_ueberspringt_wochenende():
    """Freitag bis Montag ist ein Werktag, nicht drei Kalendertage."""
    assert werktage_bis(date(2026, 9, 18), date(2026, 9, 21)) == 1
    assert werktage_bis(HEUTE, date(2026, 9, 19)) == 4  # Samstag zählt nicht mit
    assert werktage_bis(HEUTE, date(2026, 9, 11)) == 0  # Vergangenheit


def test_dringlichkeit_regeln():
    assert dringlichkeit({"dringlichkeit": "mittel", "frist": "2026-09-17", "anliegen": []}, HEUTE) == (
        "hoch", "Frist 2026-09-17 liegt innerhalb von 3 Werktagen")
    assert dringlichkeit({"dringlichkeit": "mittel", "frist": "2026-09-18", "anliegen": []}, HEUTE) == ("mittel", None)
    assert dringlichkeit({"dringlichkeit": "niedrig", "frist": None,
                          "anliegen": [{"kategorie": "reklamation", "beschreibung": ""}]}, HEUTE) == ("hoch", "Reklamation")
    assert dringlichkeit({"dringlichkeit": "hoch", "frist": None, "anliegen": []}, HEUTE) == ("hoch", None)


def test_dringlichkeit_bei_abgelaufener_frist_und_fehlenden_feldern():
    """Eine Frist in der Vergangenheit ist erst recht dringend, eine kaputte
    Frist darf die Regel nicht zum Absturz bringen."""
    assert dringlichkeit({"dringlichkeit": "niedrig", "frist": "2026-09-11", "anliegen": []}, HEUTE) == (
        "hoch", "Frist 2026-09-11 liegt innerhalb von 3 Werktagen")
    assert dringlichkeit({"frist": "übermorgen", "anliegen": []}, HEUTE) == ("mittel", None)
    assert dringlichkeit({}, HEUTE) == ("mittel", None)
