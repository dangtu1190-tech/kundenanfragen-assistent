"""FastAPI-Server des Kundenanfragen-Assistenten. Start: uvicorn app.main:app --reload --port 8040"""
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import speicher
from app.integration import SystemNichtErreichbar, Systeme
from app.llm_client import LLMClient, lade_konfig
from app.pipeline import verarbeite

DOCS = Path(__file__).resolve().parent.parent / "docs"

# Der Ticketstatus im CRM folgt der Entscheidung im Assistenten.
CRM_STATUS = {"freigegeben": "beantwortet", "abgelehnt": "verworfen", "offen": "offen"}


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
    # Standard ist die Systemlandschaft aus der Umgebung (ohne SYSTEME_BASE_URL
    # in-process); Tests setzen hier ihre Fakes ein.
    systeme_bauen = systeme_factory or Systeme.aus_umgebung

    @app.get("/")
    def start():
        return FileResponse(DOCS / "index.html")

    def _systeme_erreichbar() -> bool:
        """Ein echter Aufruf gegen das MES, kein Ping: nur so zeigt sich, ob die
        Systemlandschaft wirklich antwortet."""
        try:
            systeme_bauen().mes.maschinen()
        except SystemNichtErreichbar:
            return False
        return True

    @app.get("/api/health")
    def health():
        """Lebenszeichen des Prozesses, ohne ein einziges Fachsystem anzufassen.

        Dafür gedacht, dass Docker, Container Apps, Render und Fly hier ihre
        Proben stellen. /api/status ruft das MES auf; als Probe würde ein
        Ausfall der Systemlandschaft (oder ein Sidecar, der eine Sekunde später
        startet) den App-Container als ungesund abstempeln und neu starten
        lassen, obwohl die App selbst einwandfrei läuft.
        """
        return {"status": "ok"}

    @app.get("/api/status")
    def status():
        client = factory()
        return {"anbieter": client.konfig.provider, "modell": client.konfig.model,
                "schluessel_gesetzt": client.konfig.schluessel_gesetzt or client.konfig.provider in ("ollama", "fake"),
                "live_modellaufrufe": _live_modellaufrufe(),
                "systeme_erreichbar": _systeme_erreichbar(),
                "versender": speicher.lade_konfig().get("versender", ""),
                "heute": _heute().isoformat(), "modus": "server"}

    @app.get("/api/mails")
    def mails():
        """Liste für den Posteingang.

        Zuständigkeit und Dringlichkeit stehen mit in der Liste, damit die
        Oberfläche sie sofort als Kennzeichen anzeigen kann; sie kommen aus dem
        ohnehin geladenen Ergebnis-Dict und kosten keinen weiteren Zugriff. Für
        eine unverarbeitete Mail sind beide null, nicht etwa ein Standardwert:
        eine geratene Zuständigkeit wäre in der Liste nicht von einer
        entschiedenen zu unterscheiden."""
        ergebnisse = speicher.lade_ergebnisse()
        eintraege = []
        for m in speicher.lade_mails():
            ergebnis = ergebnisse.get(m["id"], {})
            eintraege.append({"id": m["id"], "absender_name": m["absender_name"],
                              "absender_firma": m.get("absender_firma", ""), "betreff": m["betreff"],
                              "empfangen": m["empfangen"],
                              "status": ergebnis.get("status", "unverarbeitet"),
                              "zustaendigkeit": ergebnis.get("zustaendigkeit"),
                              "dringlichkeit": ergebnis.get("dringlichkeit")})
        return eintraege

    @app.get("/api/mails/{mail_id}")
    def mail_detail(mail_id: str):
        return {"mail": _mail(mail_id), "ergebnis": speicher.lade_ergebnisse().get(mail_id)}

    @app.post("/api/mails/{mail_id}/verarbeiten")
    def verarbeiten(mail_id: str):
        if not _live_modellaufrufe():
            raise HTTPException(403, "Live-Modellaufrufe sind abgeschaltet (LIVE_MODELLAUFRUFE=0). "
                                     "Die Demo zeigt aufgezeichnete Ergebnisse.")
        mail = _mail(mail_id)
        # Der Modellaufruf steht bewusst vor der Sperre: er dauert Sekunden, und
        # solange müsste sonst jede andere Anfrage warten. Gesperrt wird nur das,
        # was atomar bleiben muss, nämlich Lesen, Ändern und Schreiben der Datei.
        ergebnis = verarbeite(mail, factory(), _heute(), systeme_bauen())
        with speicher.SPERRE:
            ergebnisse = speicher.lade_ergebnisse()
            ergebnisse[mail_id] = ergebnis
            speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    @app.post("/api/mails")
    def neue_mail(neu: NeueMail):
        # Lesen, ID vergeben und Schreiben in einem Block: ohne Sperre lesen
        # zwei gleichzeitige Anfragen denselben Stand, vergeben dieselbe ID und
        # die zweite überschreibt die erste Mail.
        with speicher.SPERRE:
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
        # Die Sperre umschließt auch den CRM-Aufruf: er steht mitten in der
        # Folge aus Lesen, Ändern und Schreiben, und nur gemeinsam bleibt der
        # Ticketstatus im CRM mit dem Status in ergebnisse.json konsistent. Der
        # Aufruf ist durch ZEITLIMIT und einen Wiederholungsversuch begrenzt,
        # die Sperre also nie länger als wenige Sekunden gehalten.
        with speicher.SPERRE:
            ergebnisse = speicher.lade_ergebnisse()
            ergebnis = ergebnisse.get(mail_id)
            if not ergebnis:
                raise HTTPException(409, "Mail ist noch nicht verarbeitet")
            ticket = ergebnis.get("ticket")
            if ticket and ticket.get("ticket_id"):
                # Erst das CRM, dann speichern: scheitert die Synchronisation, darf
                # der Status hier nicht schon weitergelaufen sein.
                try:
                    aktuell = systeme_bauen().crm.ticket_status(ticket["ticket_id"], CRM_STATUS[aenderung.status])
                except SystemNichtErreichbar as e:
                    raise HTTPException(502, f"Ticketstatus konnte nicht gesetzt werden ({e.system}: {e.grund})") from e
                if aktuell is None:
                    raise HTTPException(409, f"Ticket {ticket['ticket_id']} im CRM unbekannt, "
                                             "Status wurde nicht geändert")
                ticket["status"] = aktuell["status"]
            if aenderung.antwort_entwurf is not None:
                ergebnis["antwort_entwurf"] = aenderung.antwort_entwurf
            ergebnis["status"] = aenderung.status
            speicher.speichere_ergebnisse(ergebnisse)
        return ergebnis

    return app


app = erzeuge_app()
