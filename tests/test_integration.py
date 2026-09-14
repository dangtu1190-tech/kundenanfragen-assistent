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
