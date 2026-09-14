"""Ein OpenAI-kompatibler Client, Basis-URL je Anbieter (Ollama lokal oder OpenAI).

Standard ist Ollama auf dem eigenen Rechner: kostenlos, kein Schlüssel, die
Mails verlassen die Maschine nicht. Jeder andere OpenAI-kompatible Anbieter
läuft über LLM_BASE_URL mit eigenem Schlüssel.

Konfiguration über Umgebungsvariablen LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL,
LLM_API_KEY, LLM_NUM_CTX; eine .env im Projektordner wird vorher eingelesen
(ohne Überschreiben gesetzter Variablen). FakeClient dient den Tests.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULTS = {
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "gpt-oss:20b", "api_key": "ollama"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4.1-mini"},
}

STANDARD_NUM_CTX = 8192


class AntwortAbgeschnitten(Exception):
    """Das Modell hat das Token- oder Kontextlimit erreicht, bevor es fertig war.

    Eigene Ausnahme, weil das Ergebnis sonst als 'Antwort ist kein JSON'
    erscheint: gpt-oss liefert bei einem vollen Kontextfenster einen leeren
    String, und genau diese Fehlermeldung führt bei der Suche in die Irre.
    """


def num_ctx() -> int:
    """Kontextfenster für Ollama aus LLM_NUM_CTX, Standard 8192.

    Bewusst hier und nicht als Feld in `Konfig`: `app.vergleich` baut je Modell
    eine neue `Konfig` aus einzelnen Feldern zusammen, ein zusätzliches Feld
    ginge dort beim Modellwechsel still verloren.
    """
    try:
        wert = int(os.getenv("LLM_NUM_CTX", STANDARD_NUM_CTX))
    except ValueError:
        return STANDARD_NUM_CTX
    return wert if wert > 0 else STANDARD_NUM_CTX


@dataclass
class Konfig:
    provider: str
    base_url: str
    model: str
    api_key: str

    @property
    def schluessel_gesetzt(self) -> bool:
        return bool(self.api_key) and self.api_key != "ollama"


def _lies_env_datei(pfad: Path) -> None:
    if not pfad or not pfad.is_file():
        return
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        k, v = zeile.split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


def lade_konfig(env_datei: Path | str | None = Path(__file__).resolve().parent.parent / ".env") -> Konfig:
    if env_datei:
        _lies_env_datei(Path(env_datei))
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    d = DEFAULTS.get(provider, DEFAULTS["openai"])
    return Konfig(
        provider=provider,
        base_url=os.getenv("LLM_BASE_URL", d["base_url"]),
        model=os.getenv("LLM_MODEL", d["model"]),
        api_key=os.getenv("LLM_API_KEY", d.get("api_key", "")),
    )


class LLMClient:
    """OpenAI-kompatibler Aufruf, für Ollama mit zwei zusätzlichen Angaben.

    `num_ctx` hebt das Kontextfenster über Ollamas Standard von 4096 Token.
    Mit 4096 verbrauchte gpt-oss:20b bei einer vagen Mail den gesamten Rest des
    Fensters im Reasoning-Kanal und lieferte einen leeren String
    (`finish_reason=length`). `reasoning_effort` hält denselben Kanal kurz und
    geht nur an gpt-oss; andere Modelle kennen den Parameter nicht als Begriff.
    Beides wurde am 14.09.2026 gegen Ollama 0.34.0 geprüft und akzeptiert.
    """

    def __init__(self, konfig: Konfig):
        from openai import OpenAI  # Import hier, damit Tests ohne Netz kein SDK brauchen
        self.konfig = konfig
        self._client = OpenAI(api_key=konfig.api_key or "leer", base_url=konfig.base_url)

    def _zusatzargumente(self) -> dict:
        """Anbieterspezifische Zusätze; für alles außer Ollama leer."""
        if self.konfig.provider != "ollama":
            return {}
        zusatz: dict = {"extra_body": {"options": {"num_ctx": num_ctx()}}}
        if self.konfig.model.startswith("gpt-oss"):
            zusatz["reasoning_effort"] = "low"
        return zusatz

    def frage_json(self, system: str, user: str) -> str:
        nachrichten = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        zusatz = self._zusatzargumente()
        try:
            antwort = self._client.chat.completions.create(
                model=self.konfig.model, messages=nachrichten, temperature=0,
                response_format={"type": "json_object"}, **zusatz,
            )
        except Exception as e:  # Anbieter ohne response_format: ohne Zwang erneut
            if "response_format" not in str(e) and "json_object" not in str(e):
                raise
            antwort = self._client.chat.completions.create(
                model=self.konfig.model, messages=nachrichten, temperature=0, **zusatz,
            )
        wahl = antwort.choices[0]
        if getattr(wahl, "finish_reason", None) == "length":
            raise AntwortAbgeschnitten(
                "Antwort abgeschnitten (Token- oder Kontextlimit erreicht): "
                "num_ctx/OLLAMA_CONTEXT_LENGTH erhöhen")
        return wahl.message.content or ""


class FakeClient:
    """Liefert eine feste Antwort; merkt sich jeden gesendeten User-Text."""

    def __init__(self, antwort):
        self.antwort = json.dumps(antwort, ensure_ascii=False) if isinstance(antwort, dict) else antwort
        self.aufrufe: list[str] = []
        self.konfig = Konfig("fake", "", "fake", "")

    def frage_json(self, system: str, user: str) -> str:
        self.aufrufe.append(user)
        return self.antwort
