"""Kennungen dürfen nie pseudonymisiert werden: ohne sie ist keine Anreicherung möglich.

Sie beginnen bewusst nie mit 0 oder +, damit das Telefonmuster sie nicht frisst.
"""
import pytest

from app.anonymisierung import anonymisiere


@pytest.mark.parametrize("kennung", ["K-10234", "B-2026-04711", "R-2026-07731", "V-2026-131",
                                     "A-4305", "SN-7F3K9Q2L", "STK-01", "DRK-02", "B-2026-4688"])
def test_kennungen_bleiben_stehen(kennung):
    text, tab = anonymisiere(f"Bitte prüfen: {kennung}, danke. Rückruf 0451 / 88 12 34.")
    assert kennung in text
    assert [t["typ"] for t in tab] == ["TELEFON"]
