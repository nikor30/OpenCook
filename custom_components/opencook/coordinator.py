"""Polls the OpenCook core's read-only state API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STATE_PATH, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type OpenCookConfigEntry = ConfigEntry[OpenCookCoordinator]


async def fetch_state(session: aiohttp.ClientSession, host: str, port: int) -> dict[str, Any]:
    async with asyncio.timeout(5):
        response = await session.get(f"http://{host}:{port}{STATE_PATH}")
        response.raise_for_status()
        data: dict[str, Any] = await response.json()
        return data


class OpenCookCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    config_entry: OpenCookConfigEntry

    def __init__(self, hass: HomeAssistant, entry: OpenCookConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._session = async_get_clientsession(hass)
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data[CONF_PORT]

    async def _async_update_data(self) -> dict[str, Any]:
        # The cooker itself being unreachable (standby) is a normal state reported by the API;
        # only a failing OpenCook core makes the entities unavailable.
        try:
            return await fetch_state(self._session, self._host, self._port)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise UpdateFailed(f"OpenCook core not reachable: {err}") from err
