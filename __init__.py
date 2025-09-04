
"""
Weasley Clock Custom Component for Home Assistant
Generates dynamic clock face images showing user positions across zones
"""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SERVICE_GENERATE_IMAGE
from .coordinator import WeasleyClockUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Weasley Clock from a config entry."""
    _LOGGER.info("Setting up Weasley Clock integration")
    
    # Create coordinator
    coordinator = WeasleyClockUpdateCoordinator(hass, entry)
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def generate_image_service(call):
        """Handle the generate_image service call."""
        reason = call.data.get("reason", "Service call")
        await coordinator.async_generate_image(reason)
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_IMAGE,
        generate_image_service
    )
    _LOGGER.info("✅ Service weasley_clock.generate_image registered")
    
    # Generate initial clock image
    await coordinator.async_generate_image("Home Assistant startup")
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_GENERATE_IMAGE)
    
    return unload_ok


# Backward compatibility removed - use config flow only
