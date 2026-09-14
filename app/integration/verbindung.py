"""Gemeinsame HTTP-Hilfsfunktionen für die Systemadapter.

Kapselt Zeitlimit, einen Wiederholungsversuch bei Verbindungsfehlern und
die Abbildung auf SystemNichtErreichbar bzw. None bei 404.
"""
import asyncio

import httpx

from systeme.main import app as systeme_app

ZEITLIMIT = 3.0


class SystemNichtErreichbar(Exception):
    """Ein Fachsystem war auch nach dem Wiederholungsversuch nicht erreichbar."""

    def __init__(self, system: str, grund: str):
        super().__init__(f"{system}: {grund}")
        self.system = system
        self.grund = grund


class _SyncAsgiTransport(httpx.BaseTransport):
    """Synchrone Bruecke auf httpx.ASGITransport, der nur async arbeitet."""

    def __init__(self, app):
        self._asgi = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        async def _anfrage() -> httpx.Response:
            antwort = await self._asgi.handle_async_request(request)
            inhalt = await antwort.aread()
            return httpx.Response(antwort.status_code, headers=antwort.headers, content=inhalt, request=request)

        return asyncio.run(_anfrage())


def baue_client(base_url: str | None = None) -> httpx.Client:
    """Baut den HTTP-Client für die Systemlandschaft.

    Ohne base_url wird die Mock-App in-process über ASGITransport
    angesprochen, sonst per echtem HTTP gegen base_url.
    """
    if base_url is None:
        return httpx.Client(transport=_SyncAsgiTransport(systeme_app), base_url="http://systeme", timeout=ZEITLIMIT)
    return httpx.Client(base_url=base_url, timeout=ZEITLIMIT)


def _sende(anfrage, client: httpx.Client, system: str):
    fehler: Exception | None = None
    for _ in range(2):
        try:
            antwort = anfrage(client)
            break
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            fehler = exc
        except httpx.RequestError as exc:
            raise SystemNichtErreichbar(system, str(exc)) from exc
    else:
        raise SystemNichtErreichbar(system, str(fehler)) from fehler
    if antwort.status_code == 404:
        return None
    if antwort.status_code >= 500:
        raise SystemNichtErreichbar(system, f"Serverfehler {antwort.status_code}")
    antwort.raise_for_status()
    return antwort.json()


def _get(client, system, pfad, params=None):
    return _sende(lambda c: c.get(pfad, params=params), client, system)


def _post(client, system, pfad, json=None):
    return _sende(lambda c: c.post(pfad, json=json), client, system)


def _patch(client, system, pfad, json=None):
    return _sende(lambda c: c.patch(pfad, json=json), client, system)
