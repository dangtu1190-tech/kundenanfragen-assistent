"""Gemeinsame Testhilfen: Fake-Systemlandschaft aus den echten Mockdaten.

Die Fakes werden aus systeme/daten/*.json befüllt, damit Tests gegen dieselben
Kunden, Bestellungen und Maschinen laufen wie die Mock-Systeme, aber ohne HTTP
und ohne die Datei systeme/daten/tickets.json zu beschreiben.
"""
import json
from pathlib import Path

import pytest

from app.integration.fake import FakeCRM, FakeERP, FakeMES, FakeSysteme

SYSTEM_DATEN = Path(__file__).resolve().parent.parent / "systeme" / "daten"


def lies_systemdatei(name: str) -> list[dict]:
    return json.loads((SYSTEM_DATEN / name).read_text(encoding="utf-8"))


def baue_fake_systeme(maschinen=None) -> FakeSysteme:
    """Fake-Systemlandschaft mit den Daten der Mock-Systeme.

    maschinen darf überschrieben werden, um einen Maschinenzustand zu setzen,
    den die Mockdaten nicht hergeben (zum Beispiel STK-01 in Störung).
    """
    return FakeSysteme(
        erp=FakeERP(kunden=lies_systemdatei("kunden.json"),
                    bestellungen=lies_systemdatei("bestellungen.json"),
                    artikel=lies_systemdatei("artikel.json"),
                    rechnungen=lies_systemdatei("rechnungen.json")),
        crm=FakeCRM(kontakte=lies_systemdatei("kontakte.json")),
        mes=FakeMES(veredelung=lies_systemdatei("veredelung.json"),
                    maschinen=maschinen if maschinen is not None else lies_systemdatei("maschinen.json")),
    )


@pytest.fixture
def fake_systeme() -> FakeSysteme:
    return baue_fake_systeme()
