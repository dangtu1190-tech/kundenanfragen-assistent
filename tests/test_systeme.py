import concurrent.futures
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from systeme.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    shutil.copytree("systeme/daten", daten)
    # Der ausgelieferte Ticketbestand enthaelt die 15 Tickets des aufgezeichneten
    # Laufs. Die Tests zaehlen ab T-2026-0001 und brauchen deshalb einen leeren
    # Bestand; die Kopie wird dafuer zurueckgesetzt.
    (daten / "tickets.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("SYSTEME_DATEN", str(daten))
    return TestClient(app)


def test_erp_kunde_und_bestellung(client):
    k = client.get("/erp/kunden/K-10234").json()
    assert k["firma"] == "Dachdeckerei Brandt GmbH"
    b = client.get("/erp/bestellungen/B-2026-04711").json()
    assert b["status"] == "versendet" and b["sendungsnummer"] == "SN-7F3K9Q2L"
    assert client.get("/erp/bestellungen/B-2026-4688").status_code == 404
    letzte = client.get("/erp/kunden/K-10802/bestellungen").json()
    assert letzte[0]["bestellnummer"] == "B-2026-04120"


def test_erp_artikel_und_rechnung(client):
    a = client.get("/erp/artikel/A-4210").json()
    xl = [v for v in a["varianten"] if v["groesse"] == "XL" and v["farbe"] == "navy"][0]
    assert xl["bestand"] == 0 and xl["nachfolger"] == "A-4211"
    r = client.get("/erp/rechnungen/R-2026-07731").json()
    assert r["betrag"] == 1284.5 and r["kostenstelle"] is None


def test_crm_kontakt(client):
    k = client.get("/crm/kontakte", params={"email": "j.brandt@dachdeckerei-brandt.example"}).json()
    assert k["kundennummer"] == "K-10234"
    assert client.get("/crm/kontakte", params={"email": "niemand@example.org"}).status_code == 404


def test_crm_ticket_idempotent(client):
    body = {"externe_referenz": "m01", "kundennummer": "K-10234", "kontakt_email": "j.brandt@dachdeckerei-brandt.example",
            "betreff": "Test", "kategorien": ["bestellstatus"], "prioritaet": "hoch",
            "zustaendigkeit": "kundenservice", "zusammenfassung": "Wo bleibt B-2026-04711"}
    r1 = client.post("/crm/tickets", json=body)
    r2 = client.post("/crm/tickets", json=body)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["ticket_id"] == r2.json()["ticket_id"] == "T-2026-0001"
    assert client.patch("/crm/tickets/T-2026-0001", json={"status": "beantwortet"}).json()["status"] == "beantwortet"
    assert client.patch("/crm/tickets/T-2026-0001", json={"status": "kaputt"}).status_code == 422


def _ticket_body(externe_referenz):
    return {"externe_referenz": externe_referenz, "kundennummer": "K-10234",
            "kontakt_email": "j.brandt@dachdeckerei-brandt.example", "betreff": "Test",
            "kategorien": ["bestellstatus"], "prioritaet": "hoch", "zustaendigkeit": "kundenservice",
            "zusammenfassung": "Parallele Anfrage"}


def test_crm_ticket_parallel_anlage_vergibt_eindeutige_ids(client, tmp_path):
    """FastAPI fuehrt synchrone Routen im Threadpool aus: acht parallele POSTs mit
    unterschiedlicher externe_referenz duerfen wegen der Sperre in crm.py keine
    doppelte ticket_id vergeben."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        antworten = list(pool.map(
            lambda i: client.post("/crm/tickets", json=_ticket_body(f"parallel-{i}")), range(8)))
    assert all(a.status_code == 201 for a in antworten)
    ids = sorted(a.json()["ticket_id"] for a in antworten)
    assert ids == [f"T-2026-{n:04d}" for n in range(1, 9)]
    tickets = json.loads((tmp_path / "daten" / "tickets.json").read_text(encoding="utf-8"))
    assert len(tickets) == 8


def test_crm_ticket_parallel_gleiche_referenz_erzeugt_nur_ein_ticket(client, tmp_path):
    """Die Idempotenz ueber externe_referenz muss auch unter Parallelitaet gelten:
    acht gleichzeitige POSTs mit derselben externe_referenz duerfen nur ein
    Ticket anlegen."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        antworten = list(pool.map(
            lambda _: client.post("/crm/tickets", json=_ticket_body("gleiche-referenz")), range(8)))
    status_codes = sorted(a.status_code for a in antworten)
    assert status_codes == [200] * 7 + [201]
    ids = {a.json()["ticket_id"] for a in antworten}
    assert len(ids) == 1
    tickets = json.loads((tmp_path / "daten" / "tickets.json").read_text(encoding="utf-8"))
    assert len(tickets) == 1


def test_mes(client):
    v = client.get("/mes/veredelungsauftraege/V-2026-131").json()
    assert v["status"] == "in_produktion" and v["maschine"] == "STK-02"
    m = client.get("/mes/maschinen/STK-02").json()
    assert m["zustand"] == "stoerung"
    assert len(client.get("/mes/maschinen").json()) == 5


def test_openapi_je_system(client):
    for s in ("erp", "crm", "mes"):
        assert client.get(f"/{s}/openapi.json").status_code == 200
