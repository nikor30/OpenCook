"""Binary sensors: is the cooker online, is it cooking."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenCookConfigEntry
from .entity import OpenCookEntity

# Status 1 = cooking, 3 = paused (docs/protocol/xiaomi-c3os.md)
RUNNING_STATUS_CODES = {1, 3}


@dataclass(frozen=True, kw_only=True)
class OpenCookBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[OpenCookBinarySensorDescription, ...] = (
    OpenCookBinarySensorDescription(
        key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: bool(data.get("reachable")),
    ),
    OpenCookBinarySensorDescription(
        key="running",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda data: (
            bool(data.get("reachable")) and data.get("status") in RUNNING_STATUS_CODES
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenCookConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(OpenCookBinarySensor(entry.runtime_data, desc) for desc in BINARY_SENSORS)


class OpenCookBinarySensor(OpenCookEntity, BinarySensorEntity):
    entity_description: OpenCookBinarySensorDescription

    def __init__(self, coordinator: Any, description: OpenCookBinarySensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
