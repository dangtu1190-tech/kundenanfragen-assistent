"""Adapterschicht für die Mock-Systemlandschaft (ERP, CRM, MES).

Wandelt HTTP-Fehler der Fachsysteme in SystemNichtErreichbar um und bietet
mit Systeme.aus_umgebung() den Einstiegspunkt für die Anwendung.
"""
import os

import httpx

from app.integration.crm import CRM
from app.integration.erp import ERP
from app.integration.mes import MES
from app.integration.verbindung import SystemNichtErreichbar, baue_client

__all__ = ["ERP", "CRM", "MES", "Systeme", "SystemNichtErreichbar", "baue_client"]


class Systeme:
    """Bündelt die drei Fachsystem-Adapter hinter einem gemeinsamen Client."""

    def __init__(self, client: httpx.Client):
        self.erp = ERP(client)
        self.crm = CRM(client)
        self.mes = MES(client)

    @classmethod
    def aus_umgebung(cls) -> "Systeme":
        """Baut Systeme anhand von SYSTEME_BASE_URL (None -> In-Process)."""
        return cls(baue_client(os.getenv("SYSTEME_BASE_URL")))
