"""Läuft nur mit gesetztem Schlüssel. Ein Aufruf, eine Mail."""
import os
from datetime import date

import pytest

from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite
from app.speicher import lade_mails

pytestmark = pytest.mark.skipif(not os.getenv("LLM_API_KEY"), reason="LLM_API_KEY nicht gesetzt")


def test_echtlauf_eine_mail():
    client = LLMClient(lade_konfig())
    mail = [m for m in lade_mails() if m["id"] == "m01"][0]
    erg = verarbeite(mail, client, date(2026, 9, 14))
    assert erg["status"] == "offen", erg["extraktion_fehler"]
    kategorien = [a["kategorie"] for a in erg["extraktion"]["anliegen"]]
    assert "bestellstatus" in kategorien, kategorien
    assert erg["extraktion"]["bezug"]["bestellnummer"] == "B-2026-04711"
    assert erg["extraktion"]["kunde"]["firma"] == "Dachdeckerei Brandt GmbH"
