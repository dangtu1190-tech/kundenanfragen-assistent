"""FastAPI-Server des Kundenanfragen-Assistenten. Start: uvicorn app.main:app --reload --port 8040"""
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import speicher
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite

DOCS = Path(__file__).resolve().parent.parent / "docs"


class NeueMail(BaseModel):
    absender_name: str
    absender_firma: str = ""
    absender_email: str = ""
    betreff: str = ""
    text: str


class StatusAenderung(BaseModel):
    status: Literal["offen", "freigegeben", "abgelehnt"]
    antwort_entwurf: str | None = None


def _heute() -> date:
    return date.fromisoformat(speicher.lade_konfig()["basisdatum"])


def _live_modellaufrufe() -> bool:
    """Standard aus. Bei einer öffentlich erreichbaren Instanz zahlt sonst der
    hinterlegte Schlüssel für jeden Besucher, der auf Verarbeiten klickt."""
    return os.getenv("LIVE_MODELLAUFRUFE", "0").strip().lower() in ("1", "true", "ja", "on")


def _mail(mail_id: str) -> dict:
    for m in speicher.lade_mails():
        if m["id"] == mail_id:
            return m
    raise HTTPException(404, f"Mail {mail_id} unbekannt")


def erzeuge_app(client_factory=None, systeme_factory=None) -> FastAPI:
    app = FastAPI(title="Kundenanfragen-Assistent")
    konfig = lade_konfig()
    factory = client_factory or (lambda: LLMClient(konfig))
    # Die Systemlandschaft wird erst mit der Anreicherung angebunden; die Fabrik
    # steht schon hier, damit Tests sie ohne Umbau des Servers ersetzen können.
    systeme_bauen = systeme_factory

    @app.get("/")
    def start():
        return FileResponse(DOCS / "index.html")

    @app.get("/api/status")
    def status():
        client = factory()
        return {"anbieter": client.konfig.provider, "modell": client.konfig.model,
                "schluessel_gesetzt": client.konfig.schluessel_gesetzt or client.konfig.provider in ("ollama", "fake"),
                "live_modellaufrufe": _live_modellaufrufe(),
                "systeme_erreichbar": None,
                "heute": _heute().isoformat(), "modus": "server"}

    @app.get("/api/mails")
    def mails():
        ergebnisse = speicher.lade_ergebnisse()
        return [{"id": m["id"], "absender_name": m["absender_name"],
                 "absender_firma": m.get("absender_firma", ""), "betreff": m["betreff"],
                 "empfangen": m["empfangen"],
                 "status": ergebnisse.get(m["id"], {}).get("status", "unverarbeitet")}
                for m in speicher.lade_mails()]

    @app.get("/api/mails/{mail_id}")
    def mail_detail(mail_id: str):
        return {"mail": _mail(mail_id), "ergebnis": speicher.lade_ergebnisse().get(mail_id)}

    @app.post("/api/mails/{mail_id}/verarbeiten")
    def verarbeiten(mail_id: str):
        if not _live_modellaufrufe():
            raise HTTPException(403, "Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). "
                                     "Die Demo zeigt aufgezeichnete Ergebnisse.")
        mail = _mail(mail_id)
        ergebnisse = speicher.lade_ergebnisse()
        ergebnis = verarbeite(mail, factory(), _heute(), systeme_bauen() if systeme_bauen else None)
        ergebnisse[mail_id] = ergebnis
        speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    @app.post("/api/mails")
    def neue_mail(neu: NeueMail):
        mails = speicher.lade_mails()
        nr = max((int(m["id"][1:]) for m in mails), default=0) + 1
        mail = {"id": f"m{nr:02d}", **neu.model_dump(),
                "empfangen": datetime.now().isoformat(timespec="seconds")}
        mails.append(mail)
        speicher.speichere_mails(mails)
        return mail

    @app.post("/api/mails/{mail_id}/status")
    def status_setzen(mail_id: str, aenderung: StatusAenderung):
        _mail(mail_id)
        ergebnisse = speicher.lade_ergebnisse()
        ergebnis = ergebnisse.get(mail_id)
        if not ergebnis:
            raise HTTPException(409, "Mail ist noch nicht verarbeitet")
        if aenderung.antwort_entwurf is not None:
            ergebnis["antwort_entwurf"] = aenderung.antwort_entwurf
        ergebnis["status"] = aenderung.status
        speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    return app


app = erzeuge_app()
