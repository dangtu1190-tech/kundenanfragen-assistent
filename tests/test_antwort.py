from app.antwort import baue_antwort

EX = {
    "kunde": {"firma": "Hartmann Wärmebehandlung GmbH"},
    "ansprechpartner": {"anrede": "Herr", "name": "Frank Lindemann"},
    "anlage": {"typ": "VKUQ 50", "nummer": "VK-5000-0231", "baujahr": 2015},
    "anliegen": [{"kategorie": "wartung", "beschreibung": "Jahreswartung"},
                 {"kategorie": "ersatzteil", "beschreibung": "zwei Heizelemente"}],
    "dringlichkeit": "mittel",
    "wunschzeitraum": {"von": "2026-09-21", "bis": "2026-09-25", "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": [],
}
TERMIN = {"datum": "2026-09-21", "techniker": "T4", "qualifikation": "mechanik", "hinweis": ""}
TEILE = [{"teil": "Heizelement Graphit", "status": "ab Lager"}]


def test_entwurf_mit_einsatz_und_ersatzteil():
    t = baue_antwort(EX, TERMIN, "Wartung", TEILE)
    assert t.startswith("Sehr geehrter Herr Lindemann,")
    assert "„Wartung“" in t
    assert "Für Ihre Anlage VKUQ 50 (VK-5000-0231) haben wir notiert:" in t
    assert "- Wartung: Jahreswartung" in t and "- Ersatzteil: zwei Heizelemente" in t
    assert "Servicetechnikers (Mechanik) am Montag, 21.09.2026" in t
    assert "Ersatzteil Heizelement Graphit: ab Lager" in t
    assert "[" not in t and t.rstrip().endswith("Ihr Serviceteam")


def test_entwurf_hinweis_und_unklarheit():
    ex = dict(EX, unklarheiten=["Anlagennummer fehlt"], anlage={"typ": None, "nummer": None, "baujahr": None})
    t = baue_antwort(ex, dict(TERMIN, hinweis="Im Wunschzeitraum ist kein passender Techniker frei, Vorschlag liegt außerhalb."), "x")
    assert "Für Ihre Anlage haben wir notiert:" in t
    assert "kein passender Techniker frei" in t and "Anlagennummer fehlt" in t


def test_entwurf_vertrieb_weiterleitung():
    ex = dict(EX, zustaendigkeit="vertrieb", anliegen=[{"kategorie": "angebot", "beschreibung": "zweiter Lötofen"}])
    t = baue_antwort(ex, None, "Neuanlage")
    assert "Vertrieb" in t and "weitergeleitet" in t and "- Angebot: zweiter Lötofen" in t
    assert "Einsatz" not in t.split("weitergeleitet")[0]


def test_entwurf_nur_ersatzteil_ohne_termin():
    ex = dict(EX, anliegen=[{"kategorie": "ersatzteil", "beschreibung": "Dichtung"}])
    t = baue_antwort(ex, None, "", [{"teil": "Dichtungssatz Kammertür", "status": "ab Lager"}])
    assert "vielen Dank für Ihre Anfrage." in t
    assert "Ersatzteil Dichtungssatz Kammertür: ab Lager" in t
    assert "Terminvorschlag" not in t and "melden uns" not in t
    assert "Angebot" in t  # Hinweis, dass ein Angebot folgt


def test_entwurf_ohne_namen_ohne_termin():
    ex = dict(EX, ansprechpartner={"anrede": None, "name": None}, anliegen=[{"kategorie": "stoerung", "beschreibung": "x"}])
    t = baue_antwort(ex, None, "x")
    assert t.startswith("Guten Tag,") and "melden uns" in t
