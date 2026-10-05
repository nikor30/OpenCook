"""Fetches one recipe page on the user's request.

Guard rails: only http(s), no addresses inside the local network, sites whose terms forbid
automated reading are blocked, robots.txt is respected, at most MAX_BYTES and MAX_REDIRECTS.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from opencook import __version__

USER_AGENT = f"OpenCook/{__version__} (+https://github.com/nikor30/OpenCook; private recipe import)"
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5
TIMEOUT_S = 10.0

# Their terms of use forbid automated reading of the site (see CLAUDE.md, 2026-10-05).
BLOCKED_DOMAINS: dict[str, str] = {
    "rezeptwelt.de": "Thermomix Rezeptwelt, Nutzungsbedingungen § 2 Abs. 2",
    "mixbuch.app": "MixBuch, AGB § 9",
    "cookidoo.de": "Cookidoo, Nutzungsbedingungen",
    "cookidoo.at": "Cookidoo, Nutzungsbedingungen",
    "cookidoo.ch": "Cookidoo, Nutzungsbedingungen",
    "cookidoo.international": "Cookidoo, Nutzungsbedingungen",
}

Resolver = Callable[[str], Awaitable[list[str]]]


class ImportRefusedError(ValueError):
    """The page may not or cannot be fetched; the message is shown to the user."""


async def resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


def blocked_reason(host: str) -> str | None:
    host = host.lower().rstrip(".")
    for domain, reason in BLOCKED_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return reason
    return None


async def _check_url(url: str, resolver: Resolver) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ImportRefusedError("Bitte eine vollständige Adresse mit https:// angeben.")
    if reason := blocked_reason(parts.hostname):
        raise ImportRefusedError(
            f"{parts.hostname} erlaubt kein automatisches Auslesen ({reason}). "
            "Kopiere den Rezepttext und nutze „Text einfügen“."
        )
    try:
        addresses = await resolver(parts.hostname)
    except OSError as err:
        raise ImportRefusedError(f"{parts.hostname} wurde nicht gefunden.") from err
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ImportRefusedError("Adressen im lokalen Netz werden nicht abgerufen.")


async def _get(client: httpx.AsyncClient, url: str, resolver: Resolver) -> httpx.Response:
    for _ in range(MAX_REDIRECTS + 1):
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
            # aiter_bytes() already decoded gzip/brotli; keep only the charset information.
            headers = {"content-type": response.headers.get("content-type", "text/html")}
            return httpx.Response(
                response.status_code, headers=headers, content=body, request=response.request
            )
    raise ImportRefusedError("Zu viele Weiterleitungen.")


async def _allowed_by_robots(client: httpx.AsyncClient, url: str, resolver: Resolver) -> bool:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        response = await _get(client, robots_url, resolver)
    except (httpx.HTTPError, ImportRefusedError):
        return True  # no readable robots.txt: no restrictions
    if response.status_code >= 400:
        return True
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


async def fetch_page(
    url: str,
    client: httpx.AsyncClient | None = None,
    resolver: Resolver = resolve,
) -> str:
    url = url.strip()
    own_client = client is None
    client = client or httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=TIMEOUT_S,
        follow_redirects=False,
    )
    try:
        await _check_url(url, resolver)
        if not await _allowed_by_robots(client, url, resolver):
            raise ImportRefusedError("Die Seite verbietet den Abruf durch Programme (robots.txt).")
        try:
            response = await _get(client, url, resolver)
        except httpx.HTTPError as err:
            raise ImportRefusedError(f"Die Seite konnte nicht geladen werden ({err}).") from err
        if response.status_code >= 400:
            raise ImportRefusedError(f"Die Seite antwortet mit Fehler {response.status_code}.")
        return response.text
    finally:
        if own_client:
            await client.aclose()
