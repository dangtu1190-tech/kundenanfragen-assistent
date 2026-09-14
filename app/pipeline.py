"""Die Schritte je Mail: pseudonymisieren, extrahieren, zurücksetzen, Entwurf bauen.

Das Modell bekommt ausschließlich `pseudonym_text`. Fehler der Extraktion
führen zu Status `pruefung_noetig`, nie zu einem Absturz.

Anreicherung (ERP, CRM, MES), Regeln für Zuständigkeit und Dringlichkeit sowie
das CRM-Ticket folgen in einem eigenen Schritt; die Ergebnisfelder dafür stehen
hier schon und bleiben vorerst leer. `systeme` wird deshalb noch nicht benutzt.
"""
import time
from datetime import date, datetime

from app import speicher
from app.anonymisierung import anonymisiere, zuruecksetzen
from app.antwort import baue_antwort
from app.extraktion import ExtraktionsFehler, extrahiere


def _leeres_ergebnis(mail: dict, pseudonym_text: str, tabelle: list, client) -> dict:
    return {
        "mail_id": mail["id"], "roh_text": mail["text"], "pseudonym_text": pseudonym_text,
        "platzhalter": tabelle,
        "extraktion": None, "extraktion_fehler": None, "extraktion_hinweise": [],
        "systemdaten": {}, "hinweise": [], "integrationsfehler": [],
        "zustaendigkeit": "kundenservice", "dringlichkeit": "mittel", "dringlichkeit_grund": None,
        "antwort_entwurf": "", "ticket": None, "status": "offen",
        "anbieter": client.konfig.provider, "modell": client.konfig.model,
        "dauer_ms": 0, "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
    }


def verarbeite(mail: dict, client, heute: date, systeme=None) -> dict:
    start = time.perf_counter()
    pseudonym_text, tabelle = anonymisiere(mail["text"], mail.get("absender_name"), mail.get("absender_firma"))
    ergebnis = _leeres_ergebnis(mail, pseudonym_text, tabelle, client)
    try:
        extraktion, hinweise = extrahiere(client, pseudonym_text, heute)
    except ExtraktionsFehler as e:
        ergebnis["extraktion_fehler"] = str(e)
        ergebnis["status"] = "pruefung_noetig"
    except Exception as e:  # Netz, Anbieter, Schlüssel
        ergebnis["extraktion_fehler"] = f"Modellaufruf fehlgeschlagen: {type(e).__name__}: {e}"
        ergebnis["status"] = "pruefung_noetig"
    else:
        ergebnis["extraktion"] = zuruecksetzen(extraktion.model_dump(), tabelle)
        ergebnis["extraktion_hinweise"] = hinweise
        ergebnis["dringlichkeit"] = ergebnis["extraktion"]["dringlichkeit"]
        ergebnis["antwort_entwurf"] = baue_antwort(
            ergebnis["extraktion"], ergebnis["systemdaten"], ergebnis["zustaendigkeit"],
            mail.get("betreff", ""), speicher.lade_konfig().get("versender", ""))
    ergebnis["dauer_ms"] = int((time.perf_counter() - start) * 1000)
    return ergebnis
