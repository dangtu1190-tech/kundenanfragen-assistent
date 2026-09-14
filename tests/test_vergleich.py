import json
from datetime import date

from app import speicher, vergleich
from app.llm_client import DEFAULTS, Konfig

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


def test_konfig_fuer_modell_openai_uebernimmt_schluessel_aus_der_umgebung(monkeypatch):
    """Regression: --anbieter openai darf den in der .env gesetzten LLM_API_KEY
    nicht verwerfen, sonst scheitert jeder Aufruf still als Schemafehler."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "x")
    basis = Konfig(provider="ollama", base_url=DEFAULTS["ollama"]["base_url"], model="gpt-oss:20b", api_key="ollama")

    konfig = vergleich.konfig_fuer_modell("gpt-4.1-mini", "openai", basis)

    assert konfig.provider == "openai"
    assert konfig.api_key == "x"
    assert konfig.base_url == DEFAULTS["openai"]["base_url"]


def test_konfig_fuer_modell_ollama_behaelt_platzhalterschluessel(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    basis = Konfig(provider="openai", base_url=DEFAULTS["openai"]["base_url"], model="gpt-4.1-mini", api_key="sk-echt")

    konfig = vergleich.konfig_fuer_modell("gpt-oss:20b", "ollama", basis)

    assert konfig.provider == "ollama"
    assert konfig.api_key == "ollama"
    assert konfig.base_url == DEFAULTS["ollama"]["base_url"]


def test_konfig_fuer_modell_ignoriert_base_url_eines_anderen_anbieters(monkeypatch):
    """LLM_BASE_URL steht fuer den Standardanbieter; beim Wechsel auf einen
    anderen Anbieter darf sie nicht mitreisen."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    basis = Konfig(provider="ollama", base_url="http://localhost:11434/v1", model="gpt-oss:20b", api_key="ollama")

    konfig = vergleich.konfig_fuer_modell("gpt-4.1-mini", "openai", basis)

    assert konfig.base_url == DEFAULTS["openai"]["base_url"]


def test_warnt_bei_fehlendem_schluessel_fuer_nicht_ollama(capsys):
    vergleich._warne_bei_fehlendem_schluessel(Konfig("openai", "https://api.openai.com/v1", "m", ""))
    assert "LLM_API_KEY fehlt" in capsys.readouterr().err


def test_warnt_nicht_bei_gesetztem_schluessel_oder_ollama(capsys):
    vergleich._warne_bei_fehlendem_schluessel(Konfig("openai", "https://api.openai.com/v1", "m", "sk-x"))
    vergleich._warne_bei_fehlendem_schluessel(Konfig("ollama", "http://localhost:11434/v1", "m", ""))
    assert capsys.readouterr().err == ""
