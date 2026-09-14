"""MES-Mock: Veredelungsaufträge und Maschinenzustände (OT-Bezug)."""
from fastapi import FastAPI, HTTPException

from systeme import speicher

app = FastAPI(title="MES (Mock)")


@app.get("/veredelungsauftraege/{auftrag}")
def veredelungsauftrag(auftrag: str):
    for v in speicher.lies("veredelung.json"):
        if v["auftrag"] == auftrag:
            return v
    raise HTTPException(404, f"Veredelungsauftrag {auftrag} unbekannt")


@app.get("/maschinen")
def maschinen():
    return speicher.lies("maschinen.json")


@app.get("/maschinen/{maschine}")
def maschine(maschine: str):
    for m in speicher.lies("maschinen.json"):
        if m["maschine"] == maschine:
            return m
    raise HTTPException(404, f"Maschine {maschine} unbekannt")
