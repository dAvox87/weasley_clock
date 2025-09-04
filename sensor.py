
"""Sensor platform for Weasley Clock integration."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Weasley Clock sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = [
        WeasleyClockLastChangedSensor(coordinator),
        WeasleyClockImagePathSensor(coordinator),
    ]
    
    async_add_entities(entities)


class WeasleyClockBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Weasley Clock sensors."""
    
    def __init__(self, coordinator):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, "weasley_clock")},
            name="Weasley Clock",
            manufacturer="Weasley Clock",
            model="Magical Family Clock",
            sw_version="1.0.0",
        )


class WeasleyClockLastChangedSensor(WeasleyClockBaseSensor):
    """Sensor for tracking when the Weasley Clock last changed."""
    
    _attr_name = "Last Changed"
    _attr_unique_id = f"{DOMAIN}_last_changed"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-time-twelve"
    
    @property
    def native_value(self) -> datetime | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("last_changed")
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "reason": self.coordinator.data.get("last_reason"),
            "image_path": self.coordinator.data.get("image_path"),
        }


class WeasleyClockImagePathSensor(WeasleyClockBaseSensor):
    """Sensor for tracking the current clock image path."""
    
    _attr_name = "Image Path"
    _attr_unique_id = f"{DOMAIN}_image_path"
    _attr_icon = "mdi:image"
    
    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("image_path")
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        image_path = self.coordinator.data.get("image_path", "")
        web_url = image_path.replace('/config/www/', '/local/') if image_path.startswith('/config/www/') else image_path
        
        return {
            "web_url": web_url,
            "last_updated": self.coordinator.data.get("last_changed"),
            "reason": self.coordinator.data.get("last_reason"),
        }
