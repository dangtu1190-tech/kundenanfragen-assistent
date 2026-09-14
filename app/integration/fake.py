"""In-Memory-Fakes der Systemadapter für Tests ohne HTTP.

FakeSysteme.ausgefallen simuliert den Ausfall einzelner Systeme: Zugriff auf
das entsprechende Attribut laesst jeden nachfolgenden Aufruf mit
SystemNichtErreichbar scheitern.
"""
from app.integration.verbindung import SystemNichtErreichbar


class FakeERP:
    def __init__(self, kunden=None, bestellungen=None, artikel=None, rechnungen=None):
        self._kunden = {k["kundennummer"]: k for k in (kunden or [])}
        self._bestellungen = {b["bestellnummer"]: b for b in (bestellungen or [])}
        self._artikel = {a["artikelnummer"]: a for a in (artikel or [])}
        self._rechnungen = {r["rechnungsnummer"]: r for r in (rechnungen or [])}

    def kunde(self, nr): return self._kunden.get(nr)
    def bestellung(self, nr): return self._bestellungen.get(nr)
    def artikel(self, nr): return self._artikel.get(nr)
    def rechnung(self, nr): return self._rechnungen.get(nr)

    def letzte_bestellungen(self, kundennummer):
        treffer = [b for b in self._bestellungen.values() if b["kundennummer"] == kundennummer]
        return sorted(treffer, key=lambda b: b["bestelldatum"], reverse=True)


class FakeCRM:
    def __init__(self, kontakte=None):
        self._kontakte = {k["email"]: k for k in (kontakte or [])}
        self._tickets, self._nach_referenz = {}, {}

    def kontakt(self, email): return self._kontakte.get(email)

    def ticket_anlegen(self, daten):
        vorhanden = self._nach_referenz.get(daten["externe_referenz"])
        if vorhanden is not None:
            return vorhanden
        ticket = {"ticket_id": f"T-FAKE-{len(self._tickets) + 1:04d}", "status": "offen", **daten}
        self._tickets[ticket["ticket_id"]] = ticket
        self._nach_referenz[daten["externe_referenz"]] = ticket
        return ticket

    def ticket_status(self, ticket_id, status):
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket["status"] = status
        return ticket


class FakeMES:
    def __init__(self, veredelung=None, maschinen=None):
        self._veredelung = {v["auftrag"]: v for v in (veredelung or [])}
        self._maschinen = {m["maschine"]: m for m in (maschinen or [])}

    def veredelungsauftrag(self, nr): return self._veredelung.get(nr)
    def maschine(self, id): return self._maschinen.get(id)
    def maschinen(self): return list(self._maschinen.values())


def _pruefen(systeme, name, ziel):
    if name in systeme.ausgefallen:
        raise SystemNichtErreichbar(name, "simulierter Ausfall")
    return ziel


class FakeSysteme:
    """Buendelt die Fakes; ausgefallen simuliert Systemausfaelle."""

    def __init__(self, erp=None, crm=None, mes=None):
        self._erp, self._crm, self._mes = erp or FakeERP(), crm or FakeCRM(), mes or FakeMES()
        self.ausgefallen: set[str] = set()

    @property
    def erp(self): return _pruefen(self, "erp", self._erp)
    @property
    def crm(self): return _pruefen(self, "crm", self._crm)
    @property
    def mes(self): return _pruefen(self, "mes", self._mes)
