import json
import re
from datetime import date

import pytest

from app.extraktion import KATEGORIEN, Extraktion, ExtraktionsFehler, baue_prompt, extrahiere, parse_antwort
from app.llm_client import FakeClient, lade_konfig

GUELTIG = {
    "kunde": {"firma": "[FIRMA_1]", "kundennummer": "K-10234"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "bezug": {"bestellnummer": "B-2026-04711", "rechnungsnummer": None, "veredelungsauftrag": None},
    "artikel": [{"artikelnummer": "A-4305", "bezeichnung": "Warnschutzjacke", "groesse": "L",
                 "farbe": "gelb", "menge": 6}],
    "anliegen": [{"kategorie": "bestellstatus", "beschreibung": "Frage nach dem Liefertermin"}],
    "dringlichkeit": "hoch",
    "frist": "2026-09-18",
    "unklarheiten": [],
}


def test_parse_gueltig():
    e, hinweise = parse_antwort(json.dumps(GUELTIG))
    assert isinstance(e, Extraktion)
    assert e.anliegen[0].kategorie == "bestellstatus"
    assert e.bezug.bestellnummer == "B-2026-04711"
    assert e.artikel[0].menge == 6
    assert hinweise == []


def test_parse_mit_codeblock():
    e, _ = parse_antwort("```json\n" + json.dumps(GUELTIG) + "\n```")
    assert e.kunde.kundennummer == "K-10234"


def test_parse_ungueltiges_json():
    with pytest.raises(ExtraktionsFehler):
        parse_antwort("das ist kein json")


def test_parse_dringlichkeit_null_wird_mittel_mit_hinweis():
    """gpt-oss:20b lieferte im Vergleich null statt eines Enum-Werts."""
    e, hinweise = parse_antwort(json.dumps(dict(GUELTIG, dringlichkeit=None)))
    assert e.dringlichkeit == "mittel"
    assert any("dringlichkeit" in h for h in hinweise), hinweise


def test_parse_dringlichkeit_erfunden_wird_mittel_mit_hinweis():
    e, hinweise = parse_antwort(json.dumps(dict(GUELTIG, dringlichkeit="sehr hoch")))
    assert e.dringlichkeit == "mittel"
    assert "dringlichkeit 'sehr hoch' ungültig, auf 'mittel' gesetzt" in hinweise


def test_parse_anrede_aufzaehlung_wird_none():
    """Kleine Modelle kopieren die Aufzählung aus dem Schema wörtlich."""
    e, hinweise = parse_antwort(json.dumps(dict(GUELTIG, ansprechpartner={"anrede": "Herr|Frau", "name": "[NAME_1]"})))
    assert e.ansprechpartner.anrede is None
    assert e.ansprechpartner.name == "[NAME_1]"
    assert any("anrede" in h for h in hinweise), hinweise


def test_parse_kategorie_grossgeschrieben_wird_sonstiges():
    kaputt = dict(GUELTIG, anliegen=[{"kategorie": "Bestellstatus", "beschreibung": "x"}])
    e, hinweise = parse_antwort(json.dumps(kaputt))
    assert e.anliegen[0].kategorie == "sonstiges"
    assert any("kategorie" in h for h in hinweise), hinweise


def test_parse_frist_mit_zeitanteil_wird_datum():
    """Modelle hängen gern 'T00:00:00' an: das ist ein lesbares Datum, kein Fehler."""
    for roh in ("2026-09-18T00:00:00", "2026-09-18 09:00:00"):
        e, hinweise = parse_antwort(json.dumps(dict(GUELTIG, frist=roh)))
        assert e.frist == "2026-09-18", roh
        assert hinweise == [], roh


def test_parse_frist_als_text_wird_none():
    e, hinweise = parse_antwort(json.dumps(dict(GUELTIG, frist="nächste Woche")))
    assert e.frist is None
    assert any("frist" in h for h in hinweise), hinweise


def test_parse_toleriert_fehlende_optionale_felder():
    knapp = {"anliegen": [{"kategorie": "sonstiges", "beschreibung": "Werbung"}]}
    e, hinweise = parse_antwort(json.dumps(knapp))
    assert e.kunde.firma is None and e.bezug.rechnungsnummer is None
    assert e.artikel == [] and e.unklarheiten == []
    assert e.dringlichkeit == "mittel" and hinweise == []


def test_parse_beschreibung_fehlt_ist_ein_fehler():
    """Ein Anliegen ohne Beschreibung ist unbrauchbar: das faellt auf, statt still zu werden."""
    with pytest.raises(ExtraktionsFehler):
        parse_antwort(json.dumps(dict(GUELTIG, anliegen=[{"kategorie": "angebot"}])))


KENNUNGSPRAEFIXE = re.compile(r"K-1|B-2026|R-2026|V-2026|A-4")


def test_prompt_enthaelt_keine_beispielkennung():
    """Lehre aus dem Ollama-Vergleich: qwen2.5:14b setzte eine Beispielnummer
    aus dem Prompt als echten Wert ein."""
    assert KENNUNGSPRAEFIXE.search(baue_prompt(date(2026, 9, 14))) is None


def test_prompt_enthaelt_alle_kategorien():
    p = baue_prompt(date(2026, 9, 14))
    for kategorie in KATEGORIEN:
        assert kategorie in p, kategorie
    assert len(KATEGORIEN) == 8


def test_prompt_enthaelt_datum_und_regeln():
    p = baue_prompt(date(2026, 9, 14))
    assert "2026-09-14" in p and "Montag" in p
    assert "[NAME_1]" in p and "[FIRMA_1]" in p
    assert "buchstabengetreu" in p
    assert "Berufsbekleidung" in p
    assert "Vakuum" not in p and "Techniker" not in p
    assert "|" not in p  # keine a|b|c-Schreibweise, die Modelle woertlich kopieren
    # Das Modell sieht nur Text und kann Anhaenge nicht pruefen: der Prompt sagt das
    assert "immer ohne Anhänge" in p and "unklarheiten" in p
    # m09 traegt die Anfrage ueber den Zitaten, nicht darin
    assert "der ganze Verlauf" in p


def test_extrahiere_sendet_nur_uebergebenen_text():
    fake = FakeClient(GUELTIG)
    e, hinweise = extrahiere(fake, "Text mit [NAME_1]", date(2026, 9, 14))
    assert e.ansprechpartner.name == "[NAME_1]"
    assert fake.aufrufe == ["Text mit [NAME_1]"]
    assert hinweise == []


def test_konfig_standard_ist_ollama(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    k = lade_konfig(env_datei=None)
    assert k.provider == "ollama" and k.base_url == "http://localhost:11434/v1"
    assert k.model == "gpt-oss:20b" and k.api_key == "ollama"


def test_konfig_unbekannter_anbieter_faellt_auf_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "irgendwas")
    for name in ("LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "x")
    k = lade_konfig(env_datei=None)
    assert k.base_url == "https://api.openai.com/v1" and k.model == "gpt-4.1-mini"


def test_env_datei_quotes_und_kein_ueberschreiben(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('LLM_PROVIDER=ollama\nLLM_MODEL="qwen2.5:14b-instruct"\n# Kommentar\nLLM_API_KEY=\'abc\'\n',
                   encoding="utf-8")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    for name in ("LLM_MODEL", "LLM_API_KEY", "LLM_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    k = lade_konfig(env_datei=env)
    assert k.provider == "openai"                 # gesetzte Variable gewinnt
    assert k.model == "qwen2.5:14b-instruct"      # Quotes entfernt
    assert k.api_key == "abc"
