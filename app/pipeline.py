"""Die vier Schritte je Mail: pseudonymisieren, extrahieren, Termin suchen, Entwurf bauen.

Das Modell bekommt ausschließlich `pseudonym_text`. Fehler der Extraktion
führen zu Status `pruefung_noetig`, nie zu einem Absturz.
"""
import time
from datetime import date, datetime

from app.anonymisierung import anonymisiere, zuruecksetzen
from app.antwort import baue_antwort
from app.ersatzteile import hinweise as ersatzteil_hinweise
from app.extraktion import ExtraktionsFehler, extrahiere
from app.kalender import finde_termin


def verarbeite(mail: dict, client, kalender: dict, heute: date) -> dict:
    start = time.perf_counter()
    pseudonym_text, tabelle = anonymisiere(mail["text"], mail.get("absender_name"), mail.get("absender_firma"))
    ergebnis = {
        "mail_id": mail["id"], "roh_text": mail["text"], "pseudonym_text": pseudonym_text,
        "platzhalter": tabelle, "extraktion": None, "extraktion_fehler": None,
        "termin": None, "ersatzteile": [], "antwort_entwurf": "", "status": "offen",
        "anbieter": client.konfig.provider, "modell": client.konfig.model,
        "dauer_ms": 0, "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        extraktion = extrahiere(client, pseudonym_text, heute).model_dump()
    except ExtraktionsFehler as e:
        ergebnis["extraktion_fehler"] = str(e)
        ergebnis["status"] = "pruefung_noetig"
    except Exception as e:  # Netz, Anbieter, Schlüssel
        ergebnis["extraktion_fehler"] = f"Modellaufruf fehlgeschlagen: {type(e).__name__}: {e}"
        ergebnis["status"] = "pruefung_noetig"
    else:
        ergebnis["termin"] = finde_termin(kalender, extraktion, heute)
        ergebnis["extraktion"] = zuruecksetzen(extraktion, tabelle)
        ergebnis["ersatzteile"] = ersatzteil_hinweise(ergebnis["extraktion"])
        ergebnis["antwort_entwurf"] = baue_antwort(ergebnis["extraktion"], ergebnis["termin"],
                                                   mail.get("betreff", ""), ergebnis["ersatzteile"])
    ergebnis["dauer_ms"] = int((time.perf_counter() - start) * 1000)
    return ergebnis
