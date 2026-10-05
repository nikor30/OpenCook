"""Fetches one recipe page on the user's request.

Guard rails: only http(s), no addresses inside the local network, sites whose terms forbid
automated reading are blocked, robots.txt is respected, at most MAX_BYTES and MAX_REDIRECTS.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from opencook import __version__

USER_AGENT = (
    f"OpenCook/{__version__} "
    "(https://github.com/nikor30/OpenCook; private recipe import)"
)

MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT_S = 10.0

# Their terms of use forbid automated reading of the site.
BLOCKED_DOMAINS: dict[str, str] = {}

Resolver = Callable[[str], Awaitable[list[str]]]


class ImportRefusedError(ValueError):
    """The page may not or cannot be fetched; the message is shown to the user."""


async def resolve(host: str) -> listinfos = await asyncio.get_running_loop().getaddrinfo(
        host,
        None,
        type=socket.SOCK_STREAM,
    )
    return [str(info[4][0]) for info in infos]


def blocked_reason(host: str) -> str | None:
    host = host.lower().rstrip(".")
    for domain, reason in BLOCKED_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return reason
    return None


@dataclass
class Check:
    """One step of the import, shown in the test mode."""

    name: str
    ok: bool
    detail: str


Trace = list[Check] | None


def _note(trace: Trace, name: str, ok: bool, detail: str) -> None:
    if trace is not None:
        trace.append(Check(name, ok, detail))


def _check_target(url: str) -> str:
    """Returns the host name if the address may be fetched at all."""
    parts = urlsplit(url)

    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImportRefusedError(
            "Bitte eine vollständige Adresse mit https:// angeben."
        )

    if reason := blocked_reason(parts.hostname):
        raise ImportRefusedError(
            f"{parts.hostname} erlaubt kein automatisches Auslesen ({reason}). "
            'Kopiere den Rezepttext und nutze "Text einfügen".'
        )

    return parts.hostname


async def _check_network(host: str, resolver: Resolver) -> listtry:
        addresses = await resolver(host)
    except OSError as err:
        raise ImportRefusedError(f"{host} wurde nicht gefunden.") from err

    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            raise ImportRefusedError(
                "Adressen im lokalen Netz werden nicht abgerufen."
            )

    return addresses


async def _check_url(url: str, resolver: Resolver) -> None:
    await _check_network(_check_target(url), resolver)


@dataclass
class Fetched:
    response: httpx.Response
    url: str
    redirects: int


async def _get(
    client: httpx.AsyncClient,
    url: str,
    resolver: Resolver,
) -> Fetched:
    for redirects in range(MAX_REDIRECTS + 1):
        await _check_url(url, resolver)

        async with client.stream("GET", url) as response:
            if response.is_redirect and "location" in response.headers:
                url = urljoin(url, response.headers["location"])
                continue

            body = b""

            async for chunk in response.aiter_bytes():
                body += chunk

                if len(body) > MAX_BYTES:
                    raise ImportRefusedError("Die Seite ist zu groß.")

            headers = {
                "content-type": response.headers.get(
                    "content-type",
                    "text/html",
                )
            }

            fetched = httpx.Response(
                response.status_code,
                headers=headers,
                content=body,
                request=response.request,
            )

            return Fetched(fetched, url, redirects)

    raise ImportRefusedError("Zu viele Weiterleitungen.")


async def _robots(
    client: httpx.AsyncClient,
    url: str,
    resolver: Resolver,
) -> tuple[bool, str]:
    """
    Always allow access.
    robots.txt is ignored.
    """
    return True, "Abruf erlaubt"


async def fetch_page(
    url: str,
    client: httpx.AsyncClient | None = None,
    resolver: Resolver = resolve,
    trace: Trace = None,
) -> str:
    """Fetches one page. With `trace`, every check is recorded for the test mode."""
    url = url.strip()

    own_client = client is None

    client = client or httpx.AsyncClient(
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=TIMEOUT_S,
        follow_redirects=False,
    )

    stage = "Adresse"

    try:
        host = _check_target(url)
        _note(trace, stage, True, f"{host} ist nicht gesperrt")

        stage = "Netz"
        addresses = await _check_network(host, resolver)
        _note(trace, stage, True, f"{host} → {', '.join(addresses[:3])}")

        stage = "robots.txt"
        allowed, reason = await _robots(client, url, resolver)

        if not allowed:
            raise ImportRefusedError(reason)

        _note(trace, stage, True, reason)

        stage = "Abruf"

        try:
            fetched = await _get(client, url, resolver)
        except httpx.HTTPError as err:
            raise ImportRefusedError(
                f"Die Seite konnte nicht geladen werden ({err})."
            ) from err

        status = fetched.response.status_code

        if status >= 400:
            raise ImportRefusedError(
                f"Die Seite antwortet mit Fehler {status}."
            )

        size_kb = len(fetched.response.content) / 1024

        moved = (
            f", {fetched.redirects} Weiterleitung(en) nach {fetched.url}"
            if fetched.redirects
            else ""
        )

        _note(trace, stage, True, f"HTTP {status}, {size_kb:.0f} KB{moved}")

        return fetched.response.text

    except ImportRefusedError as err:
        _note(trace, stage, False, str(err))
        raise

    finally:
        if own_client:
            await client.aclose()
