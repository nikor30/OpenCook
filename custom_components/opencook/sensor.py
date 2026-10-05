"""Sensors for the cooker's live state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import RUNNING_STATUSES, STATUS_OPTIONS
from .coordinator import OpenCookConfigEntry
from .entity import OpenCookEntity

type StateValue = str | int | datetime | None


def _status(data: dict[str, Any]) -> str | None:
    if not data.get("reachable"):
        return "offline"
    label = (data.get("status_label") or "").lower()
    return label if label in STATUS_OPTIONS else None


def _remaining(data: dict[str, Any]) -> int | None:
    return data.get("remaining_s") if data.get("reachable") else None


def _finishes_at(data: dict[str, Any]) -> datetime | None:
    remaining = _remaining(data)
    updated_at = dt_util.parse_datetime(data.get("updated_at") or "")
    if _status(data) not in RUNNING_STATUSES or not remaining or updated_at is None:
        return None
    return updated_at + timedelta(seconds=remaining)


def _mode(data: dict[str, Any]) -> str | None:
    label = data.get("mode_label")
    return label.lower() if label and data.get("reachable") else None


@dataclass(frozen=True, kw_only=True)
class OpenCookSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], StateValue]


SENSORS: tuple[OpenCookSensorDescription, ...] = (
    OpenCookSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[*STATUS_OPTIONS, "offline"],
        value_fn=_status,
    ),
    OpenCookSensorDescription(
        key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=_remaining,
    ),
    OpenCookSensorDescription(
        key="finishes_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_finishes_at,
    ),
    OpenCookSensorDescription(
        key="recipe",
        value_fn=lambda data: data.get("cook_name"),
    ),
    OpenCookSensorDescription(
        key="recipe_id",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("cook_id"),
    ),
    OpenCookSensorDescription(
        key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_mode,
    ),
    OpenCookSensorDescription(
        key="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("fault"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenCookConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(OpenCookSensor(entry.runtime_data, desc) for desc in SENSORS)


class OpenCookSensor(OpenCookEntity, SensorEntity):
    entity_description: OpenCookSensorDescription

    def __init__(self, coordinator: Any, description: OpenCookSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateValue:
        return self.entity_description.value_fn(self.coordinator.data)
