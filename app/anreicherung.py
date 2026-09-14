"""Anreicherung der Extraktion aus ERP, CRM und MES und das CRM-Ticket.

Zwei Grundsätze:

1. Kein Systemausfall bricht die Verarbeitung ab. Jeder Aufruf läuft durch
   `_Sammler.hole`; faellt ein System aus, wird der Schritt uebersprungen und
   System samt Grund landen in `integrationsfehler`. Die Pipeline setzt daraufhin
   `pruefung_noetig`, der Antwortentwurf faellt auf eine Formulierung ohne
   Systemdaten zurueck.
2. Was nicht zusammenpasst, wird benannt statt geglaettet. Eine unbekannte
   Bestellnummer wird zur Rueckfrage an den Kunden (`unklarheiten`), eine
   Bestellung eines anderen Kunden oder eine gestoerte Maschine zum internen
   Hinweis. Beides ist besser als ein Antwortsatz, der etwas Falsches behauptet.
"""
from datetime import date

from app.integration import SystemNichtErreichbar


def _merke(liste: list[str], eintrag: str) -> None:
    """Haengt an, ohne zu doppeln (ein Systemausfall trifft viele Aufrufe)."""
    if eintrag not in liste:
        liste.append(eintrag)


class _Sammler:
    """Ergebnis der Anreicherung im Aufbau, samt Zugriff auf die Fachsysteme."""

    def __init__(self, systeme):
        self.systeme = systeme
        self.systemdaten: dict = {}
        self.hinweise: list[str] = []
        self.fehler: list[str] = []
        self.unklarheiten: list[str] = []

    def hole(self, aufruf, standard=None) -> tuple[bool, object]:
        """Ruft ein Fachsystem auf und liefert (erreichbar, Wert).

        Das Flag unterscheidet 'nicht gefunden' (404, Wert None) von 'System
        nicht erreichbar'. Nur im ersten Fall ist eine Rueckfrage an den Kunden
        angebracht.
        """
        try:
            return True, aufruf()
        except SystemNichtErreichbar as e:
            _merke(self.fehler, f"{e.system}: {e.grund}")
            return False, standard

    def hinweis(self, text: str) -> None:
        _merke(self.hinweise, text)

    def unbekannt(self, text: str) -> None:
        """Fehlende Kennung: Hinweis fuer uns und Rueckfrage an den Kunden."""
        _merke(self.hinweise, text)
        _merke(self.unklarheiten, text)


def _kontakt(s: _Sammler, mail: dict) -> dict | None:
    email = mail.get("absender_email") or ""
    if not email:
        return None
    _, kontakt = s.hole(lambda: s.systeme.crm.kontakt(email))
    if kontakt:
        s.systemdaten["kontakt"] = kontakt
    return kontakt


def _kunde(s: _Sammler, kundennummer: str | None, kategorien: list[str]) -> None:
    if not kundennummer:
        return
    _, kunde = s.hole(lambda: s.systeme.erp.kunde(kundennummer))
    if kunde:
        s.systemdaten["kunde"] = kunde
    if "angebot" in kategorien:
        # Nur beim Angebot nuetzlich: was der Kunde zuletzt bestellt hat, ist
        # die Grundlage fuer den Ausstattungsvorschlag.
        _, letzte = s.hole(lambda: s.systeme.erp.letzte_bestellungen(kundennummer), [])
        if letzte:
            s.systemdaten["letzte_bestellungen"] = letzte


def _bestellung(s: _Sammler, nummer: str | None, kundennummer: str | None, frist: str | None, heute: date) -> None:
    if not nummer:
        return
    erreichbar, bestellung = s.hole(lambda: s.systeme.erp.bestellung(nummer))
    if not bestellung:
        if erreichbar:
            s.unbekannt(f"Bestellnummer {nummer} ist im ERP nicht bekannt")
        return
    s.systemdaten["bestellung"] = bestellung
    if kundennummer and bestellung.get("kundennummer") != kundennummer:
        s.hinweis(f"Bestellung {nummer} gehört zu Kunde {bestellung['kundennummer']}, "
                  f"Absender ist {kundennummer}")
    liefertermin = bestellung.get("liefertermin")
    if liefertermin and frist and liefertermin > frist:
        s.hinweis(f"Liefertermin {liefertermin} liegt nach der genannten Frist {frist}")
    if liefertermin and liefertermin < heute.isoformat() and bestellung.get("status") != "zugestellt":
        s.hinweis(f"Liefertermin {liefertermin} ist überschritten, Bestellung steht auf "
                  f"{bestellung.get('status')}")


def _rechnung(s: _Sammler, nummer: str | None) -> None:
    if not nummer:
        return
    erreichbar, rechnung = s.hole(lambda: s.systeme.erp.rechnung(nummer))
    if rechnung:
        s.systemdaten["rechnung"] = rechnung
    elif erreichbar:
        s.unbekannt(f"Rechnungsnummer {nummer} ist im ERP nicht bekannt")


def _variante(artikel: dict, groesse: str | None, farbe: str | None) -> dict | None:
    """Passende Variante zur genannten Groesse und Farbe.

    Ohne beide Angaben gibt es keine belastbare Bestandsaussage; dann bleibt
    der Bestand leer, statt die erstbeste Variante als Antwort auszugeben.
    Ist nur eines von beiden genannt, gewinnt die erste passende Variante; der
    Aufrufer haelt deren Groesse und Farbe fest, damit die Antwort benennt,
    worauf sie sich bezieht.
    """
    if groesse is None and farbe is None:
        return None
    for v in artikel.get("varianten") or []:
        if groesse is not None and v.get("groesse") != groesse:
            continue
        if farbe is not None and v.get("farbe") != farbe:
            continue
        return v
    return None


def _artikel(s: _Sammler, genannte: list[dict]) -> None:
    eintraege: list[dict] = []
    gesehen: set[tuple] = set()
    for eintrag in genannte:
        nummer = (eintrag or {}).get("artikelnummer")
        groesse, farbe = (eintrag or {}).get("groesse"), (eintrag or {}).get("farbe")
        if not nummer or (nummer, groesse, farbe) in gesehen:
            continue
        gesehen.add((nummer, groesse, farbe))
        _, artikel = s.hole(lambda nr=nummer: s.systeme.erp.artikel(nr))
        if not artikel:
            continue
        variante = _variante(artikel, groesse, farbe) or {}
        # Groesse und Farbe kommen aus der gewaehlten Variante: nennt der Kunde
        # nur die Groesse, muss im Ergebnis stehen, fuer welche Farbe der
        # Bestand gilt. Ohne Treffer bleibt es bei dem, was genannt wurde.
        eintraege.append({"artikelnummer": nummer,
                          "groesse": variante.get("groesse", groesse),
                          "farbe": variante.get("farbe", farbe),
                          "bestand": variante.get("bestand"), "nachfolger": variante.get("nachfolger")})
    if eintraege:
        s.systemdaten["artikel"] = eintraege


def _veredelung(s: _Sammler, nummer: str | None) -> None:
    if not nummer:
        return
    erreichbar, auftrag = s.hole(lambda: s.systeme.mes.veredelungsauftrag(nummer))
    if not auftrag:
        if erreichbar:
            s.unbekannt(f"Veredelungsauftrag {nummer} ist im MES nicht bekannt")
        return
    s.systemdaten["veredelung"] = auftrag
    maschine_id = auftrag.get("maschine")
    if not maschine_id:
        return
    _, maschine = s.hole(lambda: s.systeme.mes.maschine(maschine_id))
    if not maschine:
        return
    s.systemdaten["maschine"] = maschine
    if maschine.get("zustand") == "stoerung":
        # Der OT-Bezug der Demo: ein Maschinenzustand relativiert die Zusage
        # aus dem MES-Auftrag, bevor sie beim Kunden landet.
        s.hinweis(f"Maschine {maschine_id} meldet Störung, geplantes Ende gefährdet")


def anreichere(ex: dict, mail: dict, systeme, heute: date) -> tuple[dict, list[str], list[str], list[str]]:
    """Laedt Systemdaten zur Extraktion und prueft sie auf Plausibilitaet.

    Liefert (systemdaten, hinweise, integrationsfehler, neue_unklarheiten).
    """
    s = _Sammler(systeme)
    ex = ex or {}
    bezug = ex.get("bezug") or {}
    kategorien = [a.get("kategorie") for a in ex.get("anliegen") or []]

    kontakt = _kontakt(s, mail)
    kundennummer = (ex.get("kunde") or {}).get("kundennummer") or (kontakt or {}).get("kundennummer")
    _kunde(s, kundennummer, kategorien)
    _bestellung(s, bezug.get("bestellnummer"), kundennummer, ex.get("frist"), heute)
    _rechnung(s, bezug.get("rechnungsnummer"))
    _artikel(s, ex.get("artikel") or [])
    _veredelung(s, bezug.get("veredelungsauftrag"))
    return s.systemdaten, s.hinweise, s.fehler, s.unklarheiten


def lege_ticket_an(ergebnis: dict, mail: dict, systeme) -> dict | None:
    """Legt das CRM-Ticket an; idempotent über externe_referenz = mail_id.

    Ein erneuter Lauf derselben Mail erzeugt deshalb kein zweites Ticket,
    sondern liefert das vorhandene zurueck.
    """
    ex = ergebnis.get("extraktion") or {}
    anliegen = ex.get("anliegen") or []
    kontakt = (ergebnis.get("systemdaten") or {}).get("kontakt") or {}
    betreff = mail.get("betreff") or f"Anfrage {mail['id']}"
    daten = {
        "externe_referenz": mail["id"],
        "kundennummer": (ex.get("kunde") or {}).get("kundennummer") or kontakt.get("kundennummer"),
        "kontakt_email": mail.get("absender_email") or "",
        "betreff": betreff,
        "kategorien": [a.get("kategorie") for a in anliegen],
        "prioritaet": ergebnis.get("dringlichkeit", "mittel"),
        "zustaendigkeit": ergebnis.get("zustaendigkeit", "kundenservice"),
        "zusammenfassung": anliegen[0].get("beschreibung") if anliegen else betreff,
    }
    try:
        return systeme.crm.ticket_anlegen(daten)
    except SystemNichtErreichbar as e:
        _merke(ergebnis.setdefault("integrationsfehler", []), f"{e.system}: {e.grund}")
        return None
