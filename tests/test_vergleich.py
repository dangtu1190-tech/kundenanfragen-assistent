import json
from datetime import date

from app import speicher, vergleich
from app.llm_client import Konfig

HEUTE = date(2026, 9, 14)
ERWARTET = json.loads((speicher.DATEN / "erwartet.json").read_text(encoding="utf-8"))
MAILS = speicher.lade_mails()


class MehrereAntworten:
    """Fake-Client, der je Aufruf die nächste vorbereitete Antwort liefert.

    Anders als `FakeClient` (immer dieselbe Antwort) braucht der Modellvergleich
    für jede der 15 Mails eine eigene, damit sich Soll-Werte je Mail prüfen lassen.
    """

    def __init__(self, antworten: list[dict]):
        self._antworten = [json.dumps(a, ensure_ascii=False) for a in antworten]
        self.aufrufe: list[str] = []
        self.konfig = Konfig("fake", "", "fake", "")

    def frage_json(self, system: str, user: str) -> str:
        self.aufrufe.append(user)
        return self._antworten[len(self.aufrufe) - 1]


def _perfekte_antwort(mail_id: str) -> dict:
    """Baut aus dem Soll-Wert eine Modellantwort, die exakt darauf trifft.

    dringlichkeit und frist kommen direkt aus dem Soll: bei m03/m13 hebt die
    Reklamationsregel ohnehin auf 'hoch', bei m01/m08 greift die Fristregel
    nicht (Frist liegt mehr als drei Werktage entfernt), das 'hoch' muss also
    aus der Antwort selbst kommen.
    """
    soll = ERWARTET[mail_id]
    return {
        "kunde": {"firma": None, "kundennummer": soll["kundennummer"]},
        "ansprechpartner": {"anrede": None, "name": None},
        "bezug": {"bestellnummer": soll["bestellnummer"], "rechnungsnummer": None, "veredelungsauftrag": None},
        "artikel": [],
        "anliegen": [{"kategorie": k, "beschreibung": "Testanliegen"} for k in soll["kategorien"]],
        "dringlichkeit": soll["dringlichkeit"],
        "frist": soll["frist"],
        "unklarheiten": [],
    }


def _laufe(antworten_je_mail: dict[str, dict]) -> dict[str, dict]:
    client = MehrereAntworten([antworten_je_mail[m["id"]] for m in MAILS])
    return vergleich.laufe_modell(client, MAILS, HEUTE)


def test_perfekte_antworten_treffen_alle_felder():
    ergebnisse = _laufe({m["id"]: _perfekte_antwort(m["id"]) for m in MAILS})
    bewertung = vergleich.bewerte(ergebnisse, ERWARTET)

    assert bewertung["n"] == 15
    assert bewertung["schemafehler"] == 0
    for feld in ("kategorien", "zustaendigkeit", "dringlichkeit", "bestellnummer", "kundennummer", "frist"):
        assert bewertung[feld] == 15, feld
    assert bewertung["mittlere_dauer_ms"] >= 0


def test_eine_falsche_kategorie_zaehlt_als_einzelner_fehlschlag():
    antworten = {m["id"]: _perfekte_antwort(m["id"]) for m in MAILS}
    # m01 erwartet nur "bestellstatus"; "verfuegbarkeit" gehört wie "bestellstatus"
    # zu keiner Kategorie der Zuständigkeits-Rangfolge, ändert also nur den
    # Kategorienvergleich, nicht Zuständigkeit oder Dringlichkeit.
    antworten["m01"] = dict(antworten["m01"], anliegen=[{"kategorie": "verfuegbarkeit", "beschreibung": "x"}])
    ergebnisse = _laufe(antworten)
    bewertung = vergleich.bewerte(ergebnisse, ERWARTET)

    assert bewertung["kategorien"] == 14
    assert bewertung["zustaendigkeit"] == 15
    assert bewertung["dringlichkeit"] == 15
    assert bewertung["schemafehler"] == 0


def test_schemafehler_zaehlt_als_fehlschlag_in_jedem_feld():
    antworten = {m["id"]: _perfekte_antwort(m["id"]) for m in MAILS}
    client = MehrereAntworten([antworten[m["id"]] for m in MAILS])
    # m01 als kaputte Antwort ueberschreiben: kein JSON.
    client._antworten[0] = "kein json"
    ergebnisse = vergleich.laufe_modell(client, MAILS, HEUTE)
    bewertung = vergleich.bewerte(ergebnisse, ERWARTET)

    assert bewertung["schemafehler"] == 1
    for feld in ("kategorien", "zustaendigkeit", "dringlichkeit", "bestellnummer", "kundennummer", "frist"):
        assert bewertung[feld] == 14, feld


def test_schreibe_tabelle_enthaelt_modellname_zahlen_und_fussnote(tmp_path):
    ergebnisse = _laufe({m["id"]: _perfekte_antwort(m["id"]) for m in MAILS})
    bewertungen = {"testmodell": vergleich.bewerte(ergebnisse, ERWARTET)}
    pfad = tmp_path / "vergleich.md"

    vergleich.schreibe_tabelle(bewertungen, pfad)
    text = pfad.read_text(encoding="utf-8")

    assert "testmodell" in text
    assert "15/15" in text
    assert "Modell" in text and "Schemafehler" in text
    assert f"Soll-Werte: data/erwartet.json, n = 15, Stand {date.today().isoformat()}" in text
