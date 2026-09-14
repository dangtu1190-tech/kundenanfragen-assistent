"""Adapter für das ERP-Mock-System (Kunden, Bestellungen, Artikel, Rechnungen)."""
import httpx

from app.integration.verbindung import _get


class ERP:
    """Kapselt die ERP-Endpunkte unter /erp."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def kunde(self, kundennummer: str) -> dict | None:
        return _get(self._client, "erp", f"/erp/kunden/{kundennummer}")

    def bestellung(self, bestellnummer: str) -> dict | None:
        return _get(self._client, "erp", f"/erp/bestellungen/{bestellnummer}")

    def letzte_bestellungen(self, kundennummer: str) -> list[dict]:
        ergebnis = _get(self._client, "erp", f"/erp/kunden/{kundennummer}/bestellungen")
        return ergebnis if ergebnis is not None else []

    def artikel(self, artikelnummer: str) -> dict | None:
        return _get(self._client, "erp", f"/erp/artikel/{artikelnummer}")

    def rechnung(self, rechnungsnummer: str) -> dict | None:
        return _get(self._client, "erp", f"/erp/rechnungen/{rechnungsnummer}")
