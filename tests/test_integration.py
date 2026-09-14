import shutil

import httpx
import pytest

from app.integration import SystemNichtErreichbar, Systeme, baue_client
from app.integration.fake import FakeSysteme


@pytest.fixture
def systeme(tmp_path, monkeypatch):
    # Kopie der Daten, damit Tickets nicht in systeme/daten landen
    daten = tmp_path / "daten"
    shutil.copytree("systeme/daten", daten)
    # Leerer Ticketbestand: der ausgelieferte enthaelt die 15 Tickets des
    # aufgezeichneten Laufs, die Tests erwarten IDs ab T-2026-0001.
    (daten / "tickets.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("SYSTEME_DATEN", str(daten))
    return Systeme(baue_client(None))


def test_erp_lesen(systeme):
    assert systeme.erp.kunde("K-10234")["firma"] == "Dachdeckerei Brandt GmbH"
    assert systeme.erp.bestellung("B-2026-4688") is None
    assert systeme.erp.letzte_bestellungen("K-10802")[0]["bestellnummer"] == "B-2026-04120"


def test_crm_ticket_idempotent(systeme):
    daten = {"externe_referenz": "m99", "kundennummer": None, "kontakt_email": "x@example.org", "betreff": "t",
             "kategorien": ["sonstiges"], "prioritaet": "niedrig", "zustaendigkeit": "kundenservice", "zusammenfassung": "z"}
    t1 = systeme.crm.ticket_anlegen(daten)
    t2 = systeme.crm.ticket_anlegen(daten)
    assert t1["ticket_id"] == t2["ticket_id"]
    assert systeme.crm.ticket_status(t1["ticket_id"], "verworfen")["status"] == "verworfen"


def test_nicht_erreichbar():
    client = httpx.Client(base_url="http://127.0.0.1:9", timeout=0.2)
    s = Systeme(client)
    with pytest.raises(SystemNichtErreichbar) as e:
        s.erp.kunde("K-10234")
    assert e.value.system == "erp"


def test_fake_ausfall():
    f = FakeSysteme()
    f.ausgefallen.add("mes")
    with pytest.raises(SystemNichtErreichbar):
        f.mes.maschinen()


def test_crm_ticket_lesen(systeme):
    daten = {"externe_referenz": "m98", "kundennummer": "K-10234", "kontakt_email": "y@example.org",
             "betreff": "t", "kategorien": ["bestellstatus"], "prioritaet": "mittel",
             "zustaendigkeit": "kundenservice", "zusammenfassung": "z"}
    angelegt = systeme.crm.ticket_anlegen(daten)
    gelesen = systeme.crm.ticket(angelegt["ticket_id"])
    assert gelesen["externe_referenz"] == "m98" and gelesen["status"] == "offen"
    assert systeme.crm.ticket("T-2026-9999") is None


def _client_mit(handler):
    """Adapter auf einem httpx.Client mit frei gesetzter Antwort."""
    return Systeme(httpx.Client(transport=httpx.MockTransport(handler), base_url="http://systeme"))


@pytest.mark.parametrize("code", [401, 429])
def test_vierhundert_ist_systemfehler(code):
    """Alles ausser 404 ist ein Systemfehler, nicht "gibt es nicht".

    Ein 429 (Drosselung) oder 401 (Schluessel abgelaufen) darf nicht still als
    fehlender Datensatz durchgehen: die Anreicherung wuerde den Schritt
    ueberspringen, statt den Ausfall in integrationsfehler zu melden.
    """
    s = _client_mit(lambda anfrage: httpx.Response(code, json={"detail": "nein"}))
    with pytest.raises(SystemNichtErreichbar) as e:
        s.erp.kunde("K-10234")
    assert e.value.system == "erp" and e.value.grund == f"HTTP {code}"


def test_vierhundertvier_bleibt_kein_treffer():
    s = _client_mit(lambda anfrage: httpx.Response(404, json={"detail": "unbekannt"}))
    assert s.erp.kunde("K-99999") is None


@pytest.mark.parametrize("fehler", [httpx.ConnectTimeout, httpx.PoolTimeout])
def test_zeitueberschreitung_wird_einmal_wiederholt(fehler):
    """Ein Zeitlimit beim Verbindungsaufbau oder aus dem Pool ist ein
    Verbindungsproblem und rechtfertigt denselben zweiten Versuch wie ein
    ConnectError. Ohne diese Aufnahme flog er als RequestError sofort durch."""
    versuche = []

    def handler(anfrage):
        versuche.append(anfrage)
        if len(versuche) == 1:
            raise fehler("Zeitlimit")
        return httpx.Response(200, json=[{"maschine": "STK-01"}])

    assert _client_mit(handler).mes.maschinen() == [{"maschine": "STK-01"}]
    assert len(versuche) == 2


@pytest.mark.parametrize("fehler", [httpx.ConnectTimeout, httpx.PoolTimeout])
def test_zeitueberschreitung_nur_einmal_wiederholt(fehler):
    versuche = []

    def handler(anfrage):
        versuche.append(anfrage)
        raise fehler("Zeitlimit")

    with pytest.raises(SystemNichtErreichbar):
        _client_mit(handler).mes.maschinen()
    assert len(versuche) == 2
