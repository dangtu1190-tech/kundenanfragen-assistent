"""Tests für app.cli, ohne Modellaufruf.

Geprüft wird nur das Zurücksetzen des Ticketbestands: der eigentliche Lauf
braucht ein Modell und wird deshalb hier nicht ausgeführt.
"""
import json
import shutil

from app import cli


def _daten_kopie(tmp_path, monkeypatch, inhalt):
    daten = tmp_path / "systemdaten"
    shutil.copytree("systeme/daten", daten)
    (daten / "tickets.json").write_text(json.dumps(inhalt, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SYSTEME_DATEN", str(daten))
    return daten / "tickets.json"


def test_setze_ticketbestand_zurueck(tmp_path, monkeypatch, capsys):
    pfad = _daten_kopie(tmp_path, monkeypatch, [{"ticket_id": "T-2026-0001"}])
    cli.setze_ticketbestand_zurueck()
    assert json.loads(pfad.read_text(encoding="utf-8")) == []
    assert "zurückgesetzt" in capsys.readouterr().out


def test_neu_setzt_ticketbestand_zurueck(tmp_path, monkeypatch, capsys):
    """--neu ohne SYSTEME_BASE_URL leert den Bestand vor der Verarbeitung."""
    pfad = _daten_kopie(tmp_path, monkeypatch, [{"ticket_id": "T-2026-0001"}])
    monkeypatch.delenv("SYSTEME_BASE_URL", raising=False)
    monkeypatch.setattr(cli, "lade_mails", lambda: [])
    assert cli.main(["--neu"]) == 0
    assert json.loads(pfad.read_text(encoding="utf-8")) == []


def test_neu_mit_externer_systemlandschaft_laesst_bestand_stehen(tmp_path, monkeypatch):
    """Mit SYSTEME_BASE_URL gehört die Datei einer anderen Instanz."""
    pfad = _daten_kopie(tmp_path, monkeypatch, [{"ticket_id": "T-2026-0001"}])
    monkeypatch.setenv("SYSTEME_BASE_URL", "http://systeme:8050")
    monkeypatch.setattr(cli, "lade_mails", lambda: [])
    assert cli.main(["--neu"]) == 0
    assert json.loads(pfad.read_text(encoding="utf-8")) == [{"ticket_id": "T-2026-0001"}]


def test_neu_mit_nur_laesst_bestand_stehen(tmp_path, monkeypatch):
    """--nur ist kein Komplettlauf: die Tickets der übrigen Mails bleiben."""
    pfad = _daten_kopie(tmp_path, monkeypatch, [{"ticket_id": "T-2026-0001"}])
    monkeypatch.delenv("SYSTEME_BASE_URL", raising=False)
    monkeypatch.setattr(cli, "lade_mails", lambda: [])
    assert cli.main(["--neu", "--nur", "m03"]) == 0
    assert json.loads(pfad.read_text(encoding="utf-8")) == [{"ticket_id": "T-2026-0001"}]
