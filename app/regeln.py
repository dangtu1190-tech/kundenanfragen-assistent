"""Zuständigkeit und Dringlichkeit als Code, nicht als Modellentscheidung.

Zwei Gründe: die Zuordnung ist eine Organisationsregel des Versenders, kein
Sprachverständnis, und sie muss nachvollziehbar dieselbe bleiben, egal welches
Modell die Extraktion geliefert hat. Das Modell darf die Dringlichkeit nur
vorschlagen; eine nahe Frist oder eine Reklamation heben sie hier auf hoch.
"""
from datetime import date, timedelta

# Erste zutreffende Kategorie gewinnt; alles andere landet im Kundenservice.
RANGFOLGE = ["reklamation", "veredelung", "angebot", "rechnung"]
ZUSTAENDIGKEIT = {
    "reklamation": "kundenservice",
    "veredelung": "veredelung",
    "angebot": "vertrieb",
    "rechnung": "buchhaltung",
}
STANDARD_ZUSTAENDIGKEIT = "kundenservice"
FRIST_WERKTAGE = 3


def zustaendigkeit(kategorien: list[str]) -> str:
    """Zuständige Abteilung aus den Kategorien der Anliegen."""
    for kategorie in RANGFOLGE:
        if kategorie in kategorien:
            return ZUSTAENDIGKEIT[kategorie]
    return STANDARD_ZUSTAENDIGKEIT


def werktage_bis(heute: date, frist: date) -> int:
    """Werktage (Mo bis Fr) von heute bis zur Frist; heute zählt nicht mit.

    Eine Frist heute oder in der Vergangenheit ergibt 0.
    """
    tage = 0
    tag = heute
    while tag < frist:
        tag += timedelta(days=1)
        if tag.weekday() < 5:
            tage += 1
    return tage


def _frist_datum(wert) -> date | None:
    try:
        return date.fromisoformat(wert) if wert else None
    except (TypeError, ValueError):
        return None


def dringlichkeit(ex: dict, heute: date) -> tuple[str, str | None]:
    """Endgültige Dringlichkeit und ihr Grund (None, wenn keine Regel griff)."""
    frist = _frist_datum(ex.get("frist"))
    if frist is not None and werktage_bis(heute, frist) <= FRIST_WERKTAGE:
        return "hoch", f"Frist {ex['frist']} liegt innerhalb von {FRIST_WERKTAGE} Werktagen"
    kategorien = [a.get("kategorie") for a in ex.get("anliegen") or []]
    if "reklamation" in kategorien:
        return "hoch", "Reklamation"
    return ex.get("dringlichkeit") or "mittel", None
