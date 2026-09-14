"""Die Schritte je Mail: pseudonymisieren, extrahieren, zurücksetzen, anreichern,
Regeln anwenden, Entwurf bauen, Ticket anlegen.

Das Modell bekommt ausschließlich `pseudonym_text`. Fehler der Extraktion
führen zu Status `pruefung_noetig`, nie zu einem Absturz; dasselbe gilt für
einen Ausfall von ERP, CRM oder MES: die Verarbeitung läuft weiter, der Grund
steht in `integrationsfehler` und der Entwurf verzichtet auf Systemdaten.

`systeme` darf None sein. Dann laufen nur die lokalen Schritte samt Regeln und
Entwurf, ohne Systemzugriff und ohne Ticket; genau das braucht der
Modellvergleich, der viele Modelle gegen dieselben Mails laufen lässt.
"""
import time
from datetime import date, datetime

from app import regeln, speicher
from app.anonymisierung import anonymisiere, zuruecksetzen
from app.anreicherung import anreichere, lege_ticket_an
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


def _reichere_an(ergebnis: dict, mail: dict, systeme, heute: date) -> None:
    """Systemdaten laden und die neuen Rückfragen in die Extraktion übernehmen."""
    extraktion = ergebnis["extraktion"]
    systemdaten, hinweise, fehler, neue_unklarheiten = anreichere(extraktion, mail, systeme, heute)
    ergebnis["systemdaten"] = systemdaten
    ergebnis["hinweise"] = hinweise
    ergebnis["integrationsfehler"] = fehler
    if neue_unklarheiten:
        # In die Unklarheiten, damit der Entwurf sie als Rückfrage auflistet.
        vorhanden = extraktion.get("unklarheiten") or []
        extraktion["unklarheiten"] = list(dict.fromkeys(vorhanden + neue_unklarheiten))


def extrahiere_und_bewerte(mail: dict, client, heute: date) -> dict:
    """Schlanker Ausschnitt der Pipeline für den Modellvergleich (`app.vergleich`).

    Nur Pseudonymisierung, Extraktion, Rücksetzen und Regeln, ohne Systeme und
    ohne Ticket - der Modellvergleich braucht weder Systemdaten noch ein CRM.
    Bewusst nicht in `verarbeite` eingebaut: dort müsste die Dringlichkeitsbegründung
    (`dringlichkeit_grund`) ein zweites Mal aus den Regeln geholt werden, weil
    dieser schlanke Ausschnitt sie nicht zurückgibt - kein echtes Wiederverwenden,
    nur verschobener Code. `verarbeite` bleibt deshalb unverändert.
    """
    start = time.perf_counter()
    pseudonym_text, tabelle = anonymisiere(mail["text"], mail.get("absender_name"), mail.get("absender_firma"))
    ergebnis = {
        "mail_id": mail["id"], "extraktion": None, "extraktion_fehler": None,
        "extraktion_hinweise": [], "zustaendigkeit": "kundenservice", "dringlichkeit": "mittel",
    }
    try:
        extraktion, hinweise = extrahiere(client, pseudonym_text, heute)
    except ExtraktionsFehler as e:
        ergebnis["extraktion_fehler"] = str(e)
    except Exception as e:  # Netz, Anbieter, Schlüssel
        ergebnis["extraktion_fehler"] = f"Modellaufruf fehlgeschlagen: {type(e).__name__}: {e}"
    else:
        ex = zuruecksetzen(extraktion.model_dump(), tabelle)
        ergebnis["extraktion"] = ex
        ergebnis["extraktion_hinweise"] = hinweise
        kategorien = [a["kategorie"] for a in ex["anliegen"]]
        ergebnis["zustaendigkeit"] = regeln.zustaendigkeit(kategorien)
        ergebnis["dringlichkeit"], _ = regeln.dringlichkeit(ex, heute)
    ergebnis["dauer_ms"] = int((time.perf_counter() - start) * 1000)
    return ergebnis


def verarbeite(mail: dict, client, heute: date, systeme=None) -> dict:
    start = time.perf_counter()
    pseudonym_text, tabelle = anonymisiere(mail["text"], mail.get("absender_name"), mail.get("absender_firma"))
    ergebnis = _leeres_ergebnis(mail, pseudonym_text, tabelle, client)
    try:
        extraktion, hinweise = extrahiere(client, pseudonym_text, heute)
    except ExtraktionsFehler as e:
        ergebnis["extraktion_fehler"] = str(e)
    except Exception as e:  # Netz, Anbieter, Schlüssel
        ergebnis["extraktion_fehler"] = f"Modellaufruf fehlgeschlagen: {type(e).__name__}: {e}"
    else:
        ergebnis["extraktion"] = zuruecksetzen(extraktion.model_dump(), tabelle)
        ergebnis["extraktion_hinweise"] = hinweise
        if systeme is not None:
            _reichere_an(ergebnis, mail, systeme, heute)
        kategorien = [a["kategorie"] for a in ergebnis["extraktion"]["anliegen"]]
        ergebnis["zustaendigkeit"] = regeln.zustaendigkeit(kategorien)
        ergebnis["dringlichkeit"], ergebnis["dringlichkeit_grund"] = regeln.dringlichkeit(
            ergebnis["extraktion"], heute)
        ergebnis["antwort_entwurf"] = baue_antwort(
            ergebnis["extraktion"], ergebnis["systemdaten"], ergebnis["zustaendigkeit"],
            mail.get("betreff", ""), speicher.lade_konfig().get("versender", ""))
        if systeme is not None:
            ticket = lege_ticket_an(ergebnis, mail, systeme)
            ergebnis["ticket"] = {"ticket_id": ticket["ticket_id"], "status": ticket["status"]} if ticket else None
    if ergebnis["extraktion_fehler"] or ergebnis["integrationsfehler"]:
        ergebnis["status"] = "pruefung_noetig"
    ergebnis["dauer_ms"] = int((time.perf_counter() - start) * 1000)
    return ergebnis
