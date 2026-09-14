"""Tests für den Modellaufruf selbst: abgeschnittene Antworten und Zusatzargumente.

Kein Netz: `LLMClient._client` wird durch ein Fake-Objekt ersetzt, das die
Aufrufargumente mitschreibt und eine vorgegebene Antwort zurückgibt.
"""
import sys
import types

import pytest

from app.llm_client import (
    STANDARD_NUM_CTX,
    STANDARD_ZEITLIMIT,
    AntwortAbgeschnitten,
    Konfig,
    LLMClient,
    num_ctx,
    zeitlimit,
)


class FakeNachricht:
    def __init__(self, content):
        self.content = content


class FakeWahl:
    def __init__(self, content, finish_reason):
        self.message = FakeNachricht(content)
        self.finish_reason = finish_reason


class FakeAntwort:
    def __init__(self, content, finish_reason):
        self.choices = [FakeWahl(content, finish_reason)]


class FakeCompletions:
    def __init__(self, content="{}", finish_reason="stop"):
        self.content = content
        self.finish_reason = finish_reason
        self.aufrufe: list[dict] = []

    def create(self, **kwargs):
        self.aufrufe.append(kwargs)
        return FakeAntwort(self.content, self.finish_reason)


class FakeOpenAI:
    def __init__(self, content="{}", finish_reason="stop"):
        self.completions = FakeCompletions(content, finish_reason)
        self.chat = self


def baue_client(konfig: Konfig, monkeypatch, **fake) -> tuple[LLMClient, FakeOpenAI]:
    """Client ohne echtes SDK: __init__ wird umgangen, _client ist der Fake."""
    client = LLMClient.__new__(LLMClient)
    client.konfig = konfig
    fake_client = FakeOpenAI(**fake)
    monkeypatch.setattr(client, "_client", fake_client, raising=False)
    return client, fake_client


OLLAMA = Konfig("ollama", "http://localhost:11434/v1", "gpt-oss:20b", "ollama")
OLLAMA_QWEN = Konfig("ollama", "http://localhost:11434/v1", "qwen2.5:14b-instruct", "ollama")
OPENAI = Konfig("openai", "https://api.openai.com/v1", "gpt-4.1-mini", "sk-echt")


def test_normale_antwort_kommt_durch(monkeypatch):
    client, _ = baue_client(OLLAMA, monkeypatch, content='{"a": 1}')
    assert client.frage_json("system", "user") == '{"a": 1}'


def test_leerer_inhalt_wird_leerer_string(monkeypatch):
    client, _ = baue_client(OLLAMA, monkeypatch, content=None)
    assert client.frage_json("system", "user") == ""


def test_abgeschnittene_antwort_ist_eigener_fehler(monkeypatch):
    """gpt-oss liefert bei vollem Kontextfenster einen leeren String. Ohne diese
    Ausnahme meldet die Pipeline 'Antwort ist kein JSON' und führt in die Irre."""
    client, _ = baue_client(OLLAMA, monkeypatch, content="", finish_reason="length")
    with pytest.raises(AntwortAbgeschnitten) as fehler:
        client.frage_json("system", "user")
    assert "abgeschnitten" in str(fehler.value)
    assert "num_ctx" in str(fehler.value)


def test_ollama_bekommt_num_ctx_und_reasoning_effort(monkeypatch):
    """reasoning_effort geht im Anfragekoerper mit, nicht als SDK-Schluesselwort.

    requirements.txt laesst openai ab 1.40 zu; benannt kennt create() den
    Parameter erst in neueren Fassungen, mit einer aelteren erlaubten Version
    waere der Aufruf ein TypeError. Im Koerper kommt er immer durch.
    """
    monkeypatch.delenv("LLM_NUM_CTX", raising=False)
    client, fake = baue_client(OLLAMA, monkeypatch)
    client.frage_json("system", "user")
    argumente = fake.completions.aufrufe[0]
    assert argumente["extra_body"] == {"options": {"num_ctx": STANDARD_NUM_CTX},
                                       "reasoning_effort": "low"}
    assert "reasoning_effort" not in argumente


def test_num_ctx_aus_umgebung(monkeypatch):
    monkeypatch.setenv("LLM_NUM_CTX", "16384")
    client, fake = baue_client(OLLAMA_QWEN, monkeypatch)
    client.frage_json("system", "user")
    assert fake.completions.aufrufe[0]["extra_body"] == {"options": {"num_ctx": 16384}}


@pytest.mark.parametrize("wert", ["keine Zahl", "0", "-5"])
def test_unbrauchbares_num_ctx_faellt_auf_standard(monkeypatch, wert):
    monkeypatch.setenv("LLM_NUM_CTX", wert)
    assert num_ctx() == STANDARD_NUM_CTX


def test_reasoning_effort_nur_fuer_gpt_oss(monkeypatch):
    """qwen kennt den Parameter nicht als Begriff; num_ctx braucht es trotzdem."""
    client, fake = baue_client(OLLAMA_QWEN, monkeypatch)
    client.frage_json("system", "user")
    argumente = fake.completions.aufrufe[0]
    assert "reasoning_effort" not in argumente
    assert "reasoning_effort" not in argumente["extra_body"]
    assert argumente["extra_body"] == {"options": {"num_ctx": num_ctx()}}


def test_openai_bekommt_keine_ollama_zusaetze(monkeypatch):
    client, fake = baue_client(OPENAI, monkeypatch)
    client.frage_json("system", "user")
    argumente = fake.completions.aufrufe[0]
    assert "extra_body" not in argumente
    assert "reasoning_effort" not in argumente
    assert argumente["response_format"] == {"type": "json_object"}


def test_response_format_fallback_behaelt_zusaetze(monkeypatch):
    """Anbieter ohne response_format: zweiter Versuch ohne Zwang, aber mit num_ctx."""
    client, fake = baue_client(OLLAMA, monkeypatch)
    echt = fake.completions.create
    versuche = {"n": 0}

    def create(**kwargs):
        versuche["n"] += 1
        if versuche["n"] == 1:
            raise ValueError("response_format wird nicht unterstützt")
        return echt(**kwargs)

    fake.completions.create = create
    client.frage_json("system", "user")
    argumente = fake.completions.aufrufe[-1]
    assert "response_format" not in argumente
    assert argumente["extra_body"] == {"options": {"num_ctx": num_ctx()},
                                       "reasoning_effort": "low"}


def test_anderer_fehler_wird_durchgereicht(monkeypatch):
    client, fake = baue_client(OLLAMA, monkeypatch)

    def create(**kwargs):
        raise RuntimeError("Verbindung abgelehnt")

    fake.completions.create = create
    with pytest.raises(RuntimeError):
        client.frage_json("system", "user")


def test_zeitlimit_standard(monkeypatch):
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    assert zeitlimit() == STANDARD_ZEITLIMIT


def test_zeitlimit_aus_umgebung(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT", "30")
    assert zeitlimit() == 30.0


@pytest.mark.parametrize("wert", ["keine Zahl", "0", "-5"])
def test_unbrauchbares_zeitlimit_faellt_auf_standard(monkeypatch, wert):
    monkeypatch.setenv("LLM_TIMEOUT", wert)
    assert zeitlimit() == STANDARD_ZEITLIMIT


def test_client_bekommt_zeitlimit(monkeypatch):
    """Ohne eigenes Zeitlimit haengt ein Aufruf bis zum SDK-Standard (600 s).

    LLMClient importiert OpenAI erst in __init__ aus dem Modul openai; hier
    wird genau dieses Modul durch eine Attrappe ersetzt, die die
    Konstruktorargumente mitschreibt.
    """
    monkeypatch.setenv("LLM_TIMEOUT", "45")
    gesehen = {}

    class FakeSDK:
        def __init__(self, **kwargs):
            gesehen.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=FakeSDK))
    LLMClient(OPENAI)
    assert gesehen["timeout"] == 45.0
    assert gesehen["base_url"] == OPENAI.base_url
