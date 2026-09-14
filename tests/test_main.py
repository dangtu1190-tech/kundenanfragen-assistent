import shutil
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import speicher
from app.llm_client import FakeClient
from app.main import erzeuge_app

ANTWORT = {
    "kunde": {"firma": "[FIRMA_1]", "kundennummer": "K-10234"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "bezug": {"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
    "artikel": [{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "L",
                 "farbe": "gelb", "menge": 6}],
    "anliegen": [{"kategorie": "bestellstatus", "beschreibung": "Frage nach dem Liefertermin"}],
    "dringlichkeit": "hoch",
    "frist": "2026-09-18",
    "unklarheiten": [],
}


@pytest.fixture
def client(tmp_path, monkeypatch, fake_systeme):
    """Server mit Fake-Modell und Fake-Systemlandschaft.

    Ohne systeme_factory wuerde der Server die Mock-Systeme im Prozess starten
    und Tickets nach systeme/daten/tickets.json schreiben; die Tests wuerden
    also das Repo veraendern.
    """
    daten = tmp_path / "data"
    daten.mkdir()
    shutil.copyfile("data/mails.json", daten / "mails.json")
    shutil.copyfile("data/konfig.json", daten / "konfig.json")
    monkeypatch.setattr(speicher, "DATEN", daten)
    monkeypatch.setenv("LIVE_MODELLAUFRUFE", "1")
    app = erzeuge_app(client_factory=lambda: FakeClient(ANTWORT), systeme_factory=lambda: fake_systeme)
    return TestClient(app)


def test_startseite_und_status(client):
    assert client.get("/").status_code == 200
    s = client.get("/api/status").json()
    assert s["anbieter"] == "fake" and s["heute"] == "2026-09-14"
    assert s["systeme_erreichbar"] is True


def test_status_meldet_systemausfall(client, fake_systeme):
    fake_systeme.ausgefallen.add("mes")
    assert client.get("/api/status").json()["systeme_erreichbar"] is False


def test_mails_liste_und_detail(client):
    liste = client.get("/api/mails").json()
    assert len(liste) == 15 and liste[0]["status"] == "unverarbeitet"
    d = client.get("/api/mails/m01").json()
    assert d["mail"]["id"] == "m01" and d["ergebnis"] is None
    assert client.get("/api/mails/gibtsnicht").status_code == 404


def test_liste_nennt_zustaendigkeit_und_dringlichkeit(client):
    """Die Kennzeichen der Liste kommen aus dem Ergebnis, nicht aus einem Standardwert."""
    unverarbeitet = client.get("/api/mails").json()[0]
    assert unverarbeitet["zustaendigkeit"] is None and unverarbeitet["dringlichkeit"] is None

    client.post("/api/mails/m01/verarbeiten")
    eintrag = client.get("/api/mails").json()[0]
    assert eintrag["id"] == "m01"
    assert eintrag["zustaendigkeit"] == "kundenservice"
    assert eintrag["dringlichkeit"] in ("niedrig", "mittel", "hoch")
    # Die übrigen Mails bleiben ohne Kennzeichen, solange sie unverarbeitet sind.
    assert client.get("/api/mails").json()[1]["zustaendigkeit"] is None


def test_verarbeiten_und_freigeben(client):
    r = client.post("/api/mails/m01/verarbeiten").json()
    assert r["status"] == "offen"
    assert r["extraktion"]["ansprechpartner"]["name"] == "Jens Brandt"
    assert r["extraktion"]["bezug"]["bestellnummer"] == "B-2026-04711"
    assert client.get("/api/mails").json()[0]["status"] == "offen"
    r = client.post("/api/mails/m01/status", json={"status": "freigegeben", "antwort_entwurf": "Geändert"}).json()
    assert r["status"] == "freigegeben" and r["antwort_entwurf"] == "Geändert"
    assert client.post("/api/mails/m01/status", json={"status": "kaputt"}).status_code == 422


def test_status_ohne_verarbeitung_ist_konflikt(client):
    r = client.post("/api/mails/m02/status", json={"status": "freigegeben"})
    assert r.status_code == 409


def test_neue_mail_anlegen(client):
    r = client.post("/api/mails", json={"absender_name": "Test Person", "absender_firma": "Testfirma GmbH",
                                        "absender_email": "t@example.org",
                                        "betreff": "Test", "text": "Hallo, Test Person hier."}).json()
    assert r["id"] == "m16"
    assert len(client.get("/api/mails").json()) == 16
    e = client.post("/api/mails/m16/verarbeiten").json()
    assert "Test Person" not in e["pseudonym_text"]
    assert "Testfirma" not in e["pseudonym_text"]


def test_status_meldet_live_schalter(client, monkeypatch):
    assert client.get("/api/status").json()["live_modellaufrufe"] is True
    monkeypatch.setenv("LIVE_MODELLAUFRUFE", "0")
    assert client.get("/api/status").json()["live_modellaufrufe"] is False


def test_verarbeiten_ohne_live_schalter_ist_gesperrt(client, monkeypatch):
    """Standard aus: kein Modellaufruf, kein Überschreiben des aufgezeichneten Ergebnisses.
    Sonst zahlt der hinterlegte Schlüssel für jeden Besucher der öffentlichen Demo."""
    client.post("/api/mails/m01/verarbeiten")
    vorher = client.get("/api/mails/m01").json()["ergebnis"]
    monkeypatch.delenv("LIVE_MODELLAUFRUFE", raising=False)
    r = client.post("/api/mails/m01/verarbeiten")
    assert r.status_code == 403
    assert r.json()["detail"] == ("Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). "
                                 "Die Demo zeigt aufgezeichnete Ergebnisse.")
    assert client.get("/api/mails/m01").json()["ergebnis"] == vorher
    for wert in ("0", "false", "nein", ""):
        monkeypatch.setenv("LIVE_MODELLAUFRUFE", wert)
        assert client.post("/api/mails/m01/verarbeiten").status_code == 403, wert
    for wert in ("1", "true", "JA", "on"):
        monkeypatch.setenv("LIVE_MODELLAUFRUFE", wert)
        assert client.post("/api/mails/m01/verarbeiten").status_code == 200, wert


def test_freigabe_und_ablehnung_setzen_den_ticketstatus(client, fake_systeme):
    """Der Ticketstatus im CRM folgt der Entscheidung im Assistenten."""
    ticket_id = client.post("/api/mails/m01/verarbeiten").json()["ticket"]["ticket_id"]
    assert fake_systeme.crm.ticket(ticket_id)["status"] == "offen"

    r = client.post("/api/mails/m01/status", json={"status": "freigegeben"}).json()
    assert fake_systeme.crm.ticket(ticket_id)["status"] == "beantwortet"
    assert r["ticket"]["status"] == "beantwortet"

    client.post("/api/mails/m01/status", json={"status": "abgelehnt"})
    assert fake_systeme.crm.ticket(ticket_id)["status"] == "verworfen"

    client.post("/api/mails/m01/status", json={"status": "offen"})
    assert fake_systeme.crm.ticket(ticket_id)["status"] == "offen"


def test_statusaenderung_bei_crm_ausfall_ist_502(client, fake_systeme):
    """Schlaegt die Synchronisation fehl, darf der gespeicherte Status nicht
    weiterlaufen: sonst steht im Assistenten freigegeben und im CRM offen."""
    client.post("/api/mails/m01/verarbeiten")
    fake_systeme.ausgefallen.add("crm")

    r = client.post("/api/mails/m01/status", json={"status": "freigegeben", "antwort_entwurf": "Geändert"})
    assert r.status_code == 502 and "crm" in r.json()["detail"]

    gespeichert = client.get("/api/mails/m01").json()["ergebnis"]
    assert gespeichert["status"] == "offen"
    assert gespeichert["antwort_entwurf"] != "Geändert"


def test_statusaenderung_ohne_ticket_bleibt_moeglich(client, fake_systeme):
    """Ist beim Verarbeiten kein Ticket entstanden (CRM war aus), soll die
    Freigabe trotzdem funktionieren."""
    fake_systeme.ausgefallen.add("crm")
    erg = client.post("/api/mails/m01/verarbeiten").json()
    assert erg["ticket"] is None and erg["status"] == "pruefung_noetig"

    fake_systeme.ausgefallen.clear()
    r = client.post("/api/mails/m01/status", json={"status": "freigegeben"})
    assert r.status_code == 200 and r.json()["status"] == "freigegeben"


def test_verarbeiten_liefert_systemdaten_und_ticket(client):
    erg = client.post("/api/mails/m01/verarbeiten").json()
    assert erg["systemdaten"]["bestellung"]["status"] == "versendet"
    assert erg["ticket"]["ticket_id"].startswith("T-")
    assert erg["integrationsfehler"] == []


def test_statuswechsel_bei_unbekanntem_ticket_ist_409(client, fake_systeme):
    """Ticket im CRM verschwunden: lieber ein Konflikt als ein Status, der
    nur im Assistenten weiterläuft."""
    client.post("/api/mails/m01/verarbeiten")
    fake_systeme.crm._tickets.clear()  # im CRM geloescht

    r = client.post("/api/mails/m01/status", json={"status": "freigegeben"})
    assert r.status_code == 409 and "im CRM unbekannt" in r.json()["detail"]
    assert client.get("/api/mails/m01").json()["ergebnis"]["status"] == "offen"


def test_health_ohne_systemaufruf(client, fake_systeme):
    """Die Probe darf nicht am Sidecar haengen: auch bei ausgefallener
    Systemlandschaft meldet /api/health ok, waehrend /api/status das
    Fachsystem weiterhin wirklich anfragt."""
    fake_systeme.ausgefallen.add("mes")
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert client.get("/api/status").json()["systeme_erreichbar"] is False


def test_status_nennt_versender(client):
    """Die Oberflaeche setzt daraus den Untertitel (docs/index.html, s.versender)."""
    assert client.get("/api/status").json()["versender"] == "Berufskleidung Nord GmbH"


def test_gleichzeitige_neue_mails_bekommen_eigene_ids(client):
    """Acht parallele POST /api/mails duerfen keine ID doppelt vergeben.

    FastAPI fuehrt synchrone Routen in einem Threadpool aus; ohne die Sperre in
    app/speicher.py lesen zwei Anfragen denselben Stand, vergeben dieselbe ID
    und die zweite ueberschreibt die erste Mail.
    """
    def anlegen(n: int):
        return client.post("/api/mails", json={"absender_name": f"Person {n}", "absender_firma": "",
                                               "absender_email": f"p{n}@example.org",
                                               "betreff": "Test", "text": "Hallo."})

    with ThreadPoolExecutor(max_workers=8) as pool:
        antworten = list(pool.map(anlegen, range(8)))

    assert [r.status_code for r in antworten] == [200] * 8
    ids = sorted(r.json()["id"] for r in antworten)
    assert ids == [f"m{n}" for n in range(16, 24)]
    gespeichert = speicher.lade_mails()
    assert len(gespeichert) == 23
    assert len({m["id"] for m in gespeichert}) == 23
