import json
from datetime import date

import pytest

from app.extraktion import Extraktion, ExtraktionsFehler, baue_prompt, extrahiere, parse_antwort
from app.llm_client import FakeClient, lade_konfig

GUELTIG = {
    "kunde": {"firma": "[FIRMA_1]"},
    "ansprechpartner": {"anrede": "Herr", "name": "[NAME_1]"},
    "anlage": {"typ": "VIM 30", "nummer": "VIM-3000-0917", "baujahr": 2017},
    "anliegen": [{"kategorie": "stoerung", "beschreibung": "Fehlercode F-217, Anlage steht"}],
    "dringlichkeit": "stillstand",
    "wunschzeitraum": {"von": "2026-09-14", "bis": None, "tageszeit": "egal"},
    "zustaendigkeit": "service",
    "unklarheiten": [],
}


def test_parse_gueltig():
    e = parse_antwort(json.dumps(GUELTIG))
    assert isinstance(e, Extraktion)
    assert e.anliegen[0].kategorie == "stoerung"


def test_parse_mit_codeblock():
    e = parse_antwort("```json\n" + json.dumps(GUELTIG) + "\n```")
    assert e.anlage.nummer == "VIM-3000-0917"


def test_parse_ungueltiges_json():
    with pytest.raises(ExtraktionsFehler):
        parse_antwort("das ist kein json")


def test_parse_falsche_kategorie():
    kaputt = dict(GUELTIG, anliegen=[{"kategorie": "reifen", "beschreibung": "x"}])
    with pytest.raises(ExtraktionsFehler):
        parse_antwort(json.dumps(kaputt))


def test_parse_toleriert_fehlende_optionale_felder():
    knapp = {"kunde": {"firma": None}, "ansprechpartner": {"anrede": None, "name": None}, "anlage": {"typ": None, "nummer": None},
             "anliegen": [], "dringlichkeit": "niedrig",
             "wunschzeitraum": {"von": None, "bis": None, "tageszeit": "egal"},
             "zustaendigkeit": "service", "unklarheiten": ["kein Anliegen erkennbar"]}
    e = parse_antwort(json.dumps(knapp))
    assert e.anlage.baujahr is None


def test_prompt_enthaelt_datum_und_platzhalterregel():
    p = baue_prompt(date(2026, 9, 14))
    assert "2026-09-14" in p and "[NAME_1]" in p
    assert "[FIRMA_1]" in p and "stillstand" in p and "Seriennummer" in p and "Autohaus" not in p
    assert "Montag" in p and "Monday" not in p
    # Befunde des Gesamt-Reviews: Stillstand nur bei stehender Produktion,
    # Anlagennummer ins Nummernfeld, Personenname ohne Firmenplatzhalter
    assert "Eine geplante Wartung ist kein Stillstand" in p
    assert "anlage.nummer" in p and "anlage.typ" in p
    assert "nur der Personenname" in p


def test_extrahiere_sendet_nur_uebergebenen_text():
    fake = FakeClient(GUELTIG)
    e = extrahiere(fake, "Text mit [NAME_1]", date(2026, 9, 14))
    assert e.ansprechpartner.name == "[NAME_1]"
    assert fake.aufrufe == ["Text mit [NAME_1]"]


def test_konfig_defaults_ollama(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    k = lade_konfig(env_datei=None)
    assert k.base_url == "http://localhost:11434/v1"
    assert k.api_key == "ollama"


def test_konfig_defaults_langdock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "x")
    k = lade_konfig(env_datei=None)
    assert k.provider == "langdock" and "langdock.com" in k.base_url and k.model == "gpt-5.1"


def test_env_datei_quotes_und_kein_ueberschreiben(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('LLM_PROVIDER=ollama\nLLM_MODEL="llama3.1:8b"\n# Kommentar\nLLM_API_KEY=\'abc\'\n', encoding="utf-8")
    monkeypatch.setenv("LLM_PROVIDER", "langdock")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    k = lade_konfig(env_datei=env)
    assert k.provider == "langdock"          # gesetzte Variable gewinnt
    assert k.model == "llama3.1:8b"          # Quotes entfernt
    assert k.api_key == "abc"
