"""ERP-Mock: Kunden, Bestellungen, Artikel, Rechnungen."""
from fastapi import FastAPI, HTTPException

from systeme import speicher

app = FastAPI(title="ERP (Mock)")


def _finde(datei: str, feld: str, wert: str, bezeichnung: str) -> dict:
    for eintrag in speicher.lies(datei):
        if eintrag[feld] == wert:
            return eintrag
    raise HTTPException(404, f"{bezeichnung} {wert} unbekannt")


@app.get("/kunden/{kundennummer}")
def kunde(kundennummer: str):
    return _finde("kunden.json", "kundennummer", kundennummer, "Kunde")


@app.get("/kunden/{kundennummer}/bestellungen")
def kunden_bestellungen(kundennummer: str):
    bestellungen = [b for b in speicher.lies("bestellungen.json") if b["kundennummer"] == kundennummer]
    return sorted(bestellungen, key=lambda b: b["bestelldatum"], reverse=True)


@app.get("/bestellungen/{bestellnummer}")
def bestellung(bestellnummer: str):
    return _finde("bestellungen.json", "bestellnummer", bestellnummer, "Bestellung")


@app.get("/artikel/{artikelnummer}")
def artikel(artikelnummer: str):
    return _finde("artikel.json", "artikelnummer", artikelnummer, "Artikel")


@app.get("/rechnungen/{rechnungsnummer}")
def rechnung(rechnungsnummer: str):
    return _finde("rechnungen.json", "rechnungsnummer", rechnungsnummer, "Rechnung")
