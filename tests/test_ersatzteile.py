from app.ersatzteile import hinweise

KATALOG = [
    {"begriffe": ["heizelement", "heizstab"], "teil": "Heizelement Graphit", "status": "ab Lager"},
    {"begriffe": ["vorpumpe", "vakuumpumpe"], "teil": "Vorvakuumpumpe", "status": "Lieferzeit ca. 3 Wochen"},
]


def test_treffer_und_fallback():
    ex = {"anliegen": [
        {"kategorie": "ersatzteil", "beschreibung": "zwei Heizelemente für den Ofen"},
        {"kategorie": "ersatzteil", "beschreibung": "Dichtung für die Tür"},
        {"kategorie": "wartung", "beschreibung": "Jahreswartung"},
    ]}
    h = hinweise(ex, KATALOG)
    assert h == [{"teil": "Heizelement Graphit", "status": "ab Lager"},
                 {"teil": "Dichtung für die Tür", "status": "Verfügbarkeit wird geprüft"}]


def test_ohne_ersatzteil_leer():
    assert hinweise({"anliegen": [{"kategorie": "wartung", "beschreibung": "x"}]}, KATALOG) == []
    assert hinweise({}, KATALOG) == []
