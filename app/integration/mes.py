"""Adapter für das MES-Mock-System (Veredelungsaufträge, Maschinen)."""
import httpx

from app.integration.verbindung import _get


class MES:
    """Kapselt die MES-Endpunkte unter /mes."""

    def __init__(self, client: httpx.Client):
        self._client = client

    def veredelungsauftrag(self, nr: str) -> dict | None:
        return _get(self._client, "mes", f"/mes/veredelungsauftraege/{nr}")

    def maschine(self, id: str) -> dict | None:
        return _get(self._client, "mes", f"/mes/maschinen/{id}")

    def maschinen(self) -> list[dict]:
        ergebnis = _get(self._client, "mes", "/mes/maschinen")
        return ergebnis if ergebnis is not None else []
