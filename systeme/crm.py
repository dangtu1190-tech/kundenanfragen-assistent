"""CRM-Mock: Kontakte und Tickets. Tickets werden über externe_referenz
idempotent angelegt, damit ein erneuter Aufruf der Adapterschicht kein
Duplikat erzeugt.
"""
import threading
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from systeme import speicher

app = FastAPI(title="CRM (Mock)")

# FastAPI führt synchrone Routen in einem Threadpool aus: mehrere gleichzeitige
# Requests laufen in echten Parallel-Threads. Lesen, Idempotenz-Prüfung, ID-Vergabe
# und Schreiben von tickets.json müssen deshalb als ein atomarer Block laufen,
# sonst können zwei parallele POST /tickets dieselbe ticket_id vergeben oder
# trotz gleicher externe_referenz zwei Tickets anlegen. Ein Lock pro Prozess
# reicht, da tickets.json ohnehin nur von diesem Prozess beschrieben wird.
_TICKETS_SPERRE = threading.Lock()


class TicketNeu(BaseModel):
    externe_referenz: str
    kundennummer: str | None = None
    kontakt_email: str
    betreff: str
    kategorien: list[str]
    prioritaet: str
    zustaendigkeit: str
    zusammenfassung: str


class StatusAenderung(BaseModel):
    status: Literal["offen", "beantwortet", "verworfen"]


@app.get("/kontakte")
def kontakt(email: str):
    for k in speicher.lies("kontakte.json"):
        if k["email"] == email:
            return k
    raise HTTPException(404, f"Kontakt {email} unbekannt")


@app.post("/tickets", status_code=201)
def ticket_anlegen(neu: TicketNeu):
    with _TICKETS_SPERRE:
        tickets = speicher.lies("tickets.json")
        vorhanden = next((t for t in tickets if t["externe_referenz"] == neu.externe_referenz), None)
        if vorhanden is not None:
            return JSONResponse(status_code=200, content=vorhanden)
        ticket = {"ticket_id": f"T-2026-{len(tickets) + 1:04d}", "status": "offen",
                  "angelegt": datetime.now().isoformat(timespec="seconds"), **neu.model_dump()}
        tickets.append(ticket)
        speicher.schreib("tickets.json", tickets)
        return ticket


@app.get("/tickets/{ticket_id}")
def ticket(ticket_id: str):
    for t in speicher.lies("tickets.json"):
        if t["ticket_id"] == ticket_id:
            return t
    raise HTTPException(404, f"Ticket {ticket_id} unbekannt")


@app.patch("/tickets/{ticket_id}")
def ticket_status(ticket_id: str, aenderung: StatusAenderung):
    with _TICKETS_SPERRE:
        tickets = speicher.lies("tickets.json")
        for t in tickets:
            if t["ticket_id"] == ticket_id:
                t["status"] = aenderung.status
                speicher.schreib("tickets.json", tickets)
                return t
        raise HTTPException(404, f"Ticket {ticket_id} unbekannt")
