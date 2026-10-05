"""Device settings that can be changed in the web UI.

Saved settings (in OC_CONFIG_PATH) take precedence over OC_DEVICE_IP / OC_DEVICE_TOKEN from the
environment. The token never leaves the server again: the API only reports whether one is set.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, field_validator

TOKEN_PATTERN = re.compile(r"^[0-9a-f]{32}$")
HOST_PATTERN = re.compile(r"^[A-Za-z0-9.:-]{1,253}$")


class DeviceSettings(BaseModel):
    ip: str = ""
    token: str = ""
    show_debug: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.ip and self.token)


class SettingsUpdate(BaseModel):
    ip: str | None = None
    # Empty or missing keeps the stored token.
    token: str | None = None
    show_debug: bool | None = None

    @field_validator("ip")
    @classmethod
    def _check_ip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not HOST_PATTERN.fullmatch(value):
            raise ValueError("keine gültige IP-Adresse oder kein gültiger Hostname")
        return value

    @field_validator("token")
    @classmethod
    def _check_token(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        value = value.strip().lower()
        if not TOKEN_PATTERN.fullmatch(value):
            raise ValueError("der Token muss aus 32 Hex-Zeichen bestehen")
        return value


class SettingsView(BaseModel):
    """What the API returns: everything except the token itself."""

    ip: str
    token_set: bool
    token_hint: str | None
    show_debug: bool
    configured: bool

    @classmethod
    def of(cls, settings: DeviceSettings) -> SettingsView:
        return cls(
            ip=settings.ip,
            token_set=bool(settings.token),
            token_hint=f"…{settings.token[-4:]}" if settings.token else None,
            show_debug=settings.show_debug,
            configured=settings.configured,
        )


class SettingsStore:
    def __init__(self, path: Path | None, defaults: DeviceSettings) -> None:
        self._path = path
        self._defaults = defaults

    @classmethod
    def from_env(cls) -> SettingsStore:
        path = os.environ.get("OC_CONFIG_PATH")
        return cls(
            Path(path) if path else None,
            DeviceSettings(
                ip=os.environ.get("OC_DEVICE_IP", ""),
                token=os.environ.get("OC_DEVICE_TOKEN", "").lower(),
            ),
        )

    def load(self) -> DeviceSettings:
        if self._path is None or not self._path.exists():
            return self._defaults.model_copy()
        saved = json.loads(self._path.read_text(encoding="utf-8"))
        return self._defaults.model_copy(update=saved)

    def save(self, settings: DeviceSettings) -> None:
        if self._path is None:
            self._defaults = settings.model_copy()
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        # Contains the device token: readable by the service user only.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(settings.model_dump_json(indent=2))
        tmp.replace(self._path)

    def apply(self, update: SettingsUpdate) -> tuple[DeviceSettings, bool]:
        """Store the update; returns the new settings and whether the connection changed."""
        current = self.load()
        changes = update.model_dump(exclude_none=True)
        new = current.model_copy(update=changes)
        self.save(new)
        return new, (new.ip, new.token) != (current.ip, current.token)
