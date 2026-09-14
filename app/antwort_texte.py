"""Textbausteine je Kategorie, gefüttert aus den Systemdaten.

Getrennt von antwort.py, damit der Briefaufbau (Anrede, Anliegenliste, Gruß)
kurz bleibt und die fachlichen Formulierungen an einer Stelle stehen.

Grundregel: Ein Satz wird nur gebaut, wenn die Daten dafür vorliegen. Fehlt die
Bestellung, weil das ERP ausgefallen ist, gibt der Baustein nichts zurück und
der Entwurf faellt auf GENERISCH zurueck, statt etwas zu behaupten.
"""
GENERISCH = "Wir prüfen den Stand und melden uns heute noch."

STATUS_VEREDELUNG = {
    "entwurf": "liegt als Entwurf vor",
    "freigabe_offen": "wartet auf Ihre Freigabe",
    "eingeplant": "ist eingeplant",
    "in_produktion": "ist in Produktion",
    "fertig": "ist fertig",
}
ART_VEREDELUNG = {"stick": "Stick", "druck": "Druck"}
# Positionen in diesen Zustaenden sind beim Kunden, gehoeren also nicht in die
# Liste der offenen Positionen einer Teillieferung.
GELIEFERT = ("geliefert", "zugestellt", "versendet")


def _groesse_farbe(eintrag: dict) -> str:
    teile = []
    if eintrag.get("groesse"):
        teile.append(f"Größe {eintrag['groesse']}")
    if eintrag.get("farbe"):
        teile.append(str(eintrag["farbe"]))
    return ", ".join(teile)


def _offene_positionen(bestellung: dict) -> list[str]:
    zeilen = []
    for p in bestellung.get("positionen") or []:
        if p.get("status") in GELIEFERT:
            continue
        merkmale = _groesse_farbe(p)
        zeile = f"- {p.get('menge')} x {p.get('bezeichnung')} ({p.get('artikelnummer')})"
        zeilen.append(f"{zeile}, {merkmale}" if merkmale else zeile)
    return zeilen


def _liefertermin_zusatz(termin: str | None) -> str:
    if termin:
        return f", geplanter Liefertermin ist der {termin}."
    return "; den Liefertermin nennen wir Ihnen, sobald er feststeht."


def _versendet(nr, bestellung: dict, termin: str | None) -> str:
    """Aus Bausteinen, weil Sendungsnummer und Liefertermin leer sein dürfen.

    Ein ungeprüftes Feld stünde sonst als "None" im Kundenbrief.
    """
    satz = f"Ihre Bestellung {nr}"
    if bestellung.get("bestelldatum"):
        satz += f" vom {bestellung['bestelldatum']}"
    satz += " ist versendet"
    if bestellung.get("sendungsnummer"):
        satz += f", Sendungsnummer {bestellung['sendungsnummer']}"
    return satz + (f", voraussichtliche Zustellung am {termin}." if termin
                   else ", voraussichtliche Zustellung folgt.")


def _teilgeliefert(nr, bestellung: dict) -> str:
    offen = _offene_positionen(bestellung)
    if not offen:
        # Keine leere Aufzählung: der Kopf allein wäre eine Ankündigung, der
        # nichts folgt.
        return (f"Ihre Bestellung {nr} ist bisher nur teilweise geliefert; welche Positionen noch "
                "offen sind, klären wir und melden uns.")
    return "\n".join([f"Ihre Bestellung {nr} ist bisher nur teilweise geliefert. Offen sind noch:"] + offen)


def bestellstatus(ex: dict, systemdaten: dict) -> list[str]:
    b = systemdaten.get("bestellung")
    if not b:
        return []
    nr, status, termin = b.get("bestellnummer"), b.get("status"), b.get("liefertermin")
    if status == "versendet":
        saetze = [_versendet(nr, b, termin)]
    elif status == "zugestellt":
        saetze = [f"Ihre Bestellung {nr} ist am {termin} bei Ihnen eingetroffen." if termin
                  else f"Ihre Bestellung {nr} ist bei Ihnen eingetroffen."]
    elif status == "teilgeliefert":
        saetze = [_teilgeliefert(nr, b)]
    elif status == "kommissionierung":
        saetze = [f"Ihre Bestellung {nr} wird gerade kommissioniert" + _liefertermin_zusatz(termin)]
    else:
        saetze = [f"Ihre Bestellung {nr} ist bei uns erfasst" + _liefertermin_zusatz(termin)]
    frist = ex.get("frist")
    if termin and frist and termin > frist:
        # Derselbe Konflikt steht als Hinweis im Ergebnis; hier gehoert er in
        # den Brief, weil der Kunde sonst von einer Zusage ausgeht.
        saetze.append(f"Der geplante Liefertermin {termin} liegt nach Ihrer Frist {frist}; wir prüfen, "
                      "ob wir vorab teilliefern können, und melden uns dazu.")
    return saetze


def verfuegbarkeit(ex: dict, systemdaten: dict) -> list[str]:
    saetze = []
    for a in systemdaten.get("artikel") or []:
        bestand = a.get("bestand")
        if bestand is None:
            continue  # Groesse oder Farbe war nicht genannt, kein belastbarer Bestand
        merkmale = _groesse_farbe(a)
        kopf = f"Artikel {a.get('artikelnummer')}"
        kopf = f"{kopf} in {merkmale}" if merkmale else kopf
        if bestand > 0:
            saetze.append(f"{kopf} ist lieferbar, Bestand {bestand} Stück.")
        elif a.get("nachfolger"):
            saetze.append(f"{kopf} ist nicht mehr lieferbar; als Nachfolger können wir "
                          f"{a['nachfolger']} anbieten.")
        else:
            saetze.append(f"{kopf} ist derzeit nicht lieferbar.")
    return saetze


def veredelung(ex: dict, systemdaten: dict) -> list[str]:
    v = systemdaten.get("veredelung")
    if not v:
        return []
    art = ART_VEREDELUNG.get(v.get("art"), v.get("art") or "Veredelung")
    stand = STATUS_VEREDELUNG.get(v.get("status"), f"steht auf {v.get('status')}")
    saetze = [f"Ihr Veredelungsauftrag {v.get('auftrag')} ({art}) {stand}."]
    maschine = systemdaten.get("maschine") or {}
    ende = v.get("geplantes_ende")
    if maschine.get("maschine") and ende:
        saetze.append(f"Die Arbeit läuft auf Maschine {maschine['maschine']}, geplantes Ende ist der {ende}.")
    elif ende:
        saetze.append(f"Geplantes Ende ist der {ende}.")
    if maschine.get("zustand") == "stoerung":
        saetze.append(f"Maschine {maschine['maschine']} meldet derzeit eine Störung, das geplante Ende ist "
                      "dadurch gefährdet; wir melden uns unaufgefordert, sobald wir mehr wissen.")
    if v.get("hinweis"):
        saetze.append(f"Hinweis aus der Produktion: {v['hinweis']}.")
    return saetze


def rechnung(ex: dict, systemdaten: dict) -> list[str]:
    r = systemdaten.get("rechnung")
    if not r:
        return []
    betrag = f"{r.get('betrag') or 0:.2f}".replace(".", ",")
    nummer = r.get("rechnungsnummer")
    if r.get("status") == "bezahlt":
        return [f"Die Rechnung {nummer} über {betrag} Euro ist bei uns als bezahlt verbucht."]
    saetze = [f"Die Rechnung {nummer} über {betrag} Euro ist am {r.get('faellig')} fällig."]
    if r.get("kostenstelle"):
        saetze.append(f"Als Kostenstelle ist {r['kostenstelle']} hinterlegt.")
    return saetze


def reklamation(ex: dict, systemdaten: dict) -> list[str]:
    return ["Das tut uns leid. Wir organisieren den Ersatz beziehungsweise die Abholung der "
            "beanstandeten Ware und melden uns mit einem Termin."]


def ruecksendung(ex: dict, systemdaten: dict) -> list[str]:
    return ["Einen Rücksendeschein senden wir Ihnen in einer gesonderten Mail zu; die Ware können "
            "Sie damit kostenfrei zurückgeben."]


BAUSTEINE = {
    "bestellstatus": bestellstatus,
    "verfuegbarkeit": verfuegbarkeit,
    "veredelung": veredelung,
    "rechnung": rechnung,
    "reklamation": reklamation,
    "ruecksendung": ruecksendung,
}
# Diese Kategorien brauchen Systemdaten. Bleiben sie ohne Satz, war ein System
# nicht erreichbar oder die Kennung unbekannt: dann der generische Satz.
BRAUCHT_SYSTEMDATEN = ("bestellstatus", "verfuegbarkeit", "veredelung", "rechnung")


def systemsaetze(ex: dict, systemdaten: dict) -> list[str]:
    """Fachsätze zu allen Kategorien der Mail, in der Reihenfolge der Anliegen."""
    saetze: list[str] = []
    generisch = False
    kategorien = dict.fromkeys(a.get("kategorie") for a in ex.get("anliegen") or [])
    for kategorie in kategorien:
        baustein = BAUSTEINE.get(kategorie)
        if baustein is None:
            continue  # angebot und sonstiges deckt der Zuständigkeitssatz ab
        neue = baustein(ex, systemdaten or {})
        if neue:
            saetze += neue
        elif kategorie in BRAUCHT_SYSTEMDATEN:
            generisch = True
    if generisch:
        saetze.append(GENERISCH)
    return saetze
