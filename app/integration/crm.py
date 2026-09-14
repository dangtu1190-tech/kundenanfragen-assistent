"""Adapter für das CRM-Mock-System (Kontakte, Tickets)."""
import httpx

from app.integration.verbindung import _get, _patch, _post


class CRM:
    """Kapselt die CRM-Endpunkte unter /crm."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def kontakt(self, email: str) -> dict | None:
        return _get(self._client, "crm", "/crm/kontakte", params={"email": email})

    def ticket_anlegen(self, daten: dict) -> dict:
        return _post(self._client, "crm", "/crm/tickets", json=daten)

    def ticket_status(self, ticket_id: str, status: str) -> dict | None:
        return _patch(self._client, "crm", f"/crm/tickets/{ticket_id}", json={"status": status})
