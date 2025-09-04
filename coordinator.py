"""DataUpdateCoordinator for Weasley Clock."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from typing import Any
import hashlib
import os

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DEFAULT_UPDATE_INTERVAL_SECONDS, EVENT_IMAGE_CHANGED
from .weasley_clock import WeasleyClockGenerator

_LOGGER = logging.getLogger(__name__)


class WeasleyClockUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Weasley Clock data."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        update_interval = config_entry.data.get("update_interval_seconds", DEFAULT_UPDATE_INTERVAL_SECONDS)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        # Create the clock generator with config entry data
        self.generator = WeasleyClockGenerator(hass, config_entry.data)
        self._tracked_entities = set()
        self._setup_person_tracking()
        self._last_persons = set() # Initialize _last_persons
        self.data: dict[str, Any] = {} # Initialize self.data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            # Controlla se ci sono stati cambiamenti nelle posizioni degli utenti
            current_positions = await self.hass.async_add_executor_job(
                self.generator._get_user_positions
            )

            # Calcola un hash delle posizioni correnti
            positions_hash = hashlib.md5(str(sorted(current_positions.items())).encode()).hexdigest()

            # Se le posizioni non sono cambiate, non rigenerare l'immagine
            if hasattr(self, '_last_positions_hash') and self._last_positions_hash == positions_hash:
                _LOGGER.debug("User positions unchanged, skipping image regeneration")
                # Ensure data is not None if it was previously set
                return self.data if self.data is not None else {}

            # Salva l'hash delle posizioni correnti
            self._last_positions_hash = positions_hash

            # Genera l'immagine dell'orologio in executor
            image_path = await self.hass.async_add_executor_job(
                self.generator.generate_clock_image
            )
            current_time = dt_util.now()

            # Log del cambiamento
            changes = []
            if hasattr(self, '_last_positions'):
                for entity_id, new_zone in current_positions.items():
                    old_zone = self._last_positions.get(entity_id)
                    if old_zone != new_zone:
                        user_info = await self.hass.async_add_executor_job(
                            self.generator._get_user_info, entity_id
                        )
                        user_name = user_info.get('name', entity_id)
                        changes.append(f"{user_name}: {old_zone} → {new_zone}")
                        _LOGGER.info(f"Person {user_name} moved from {old_zone} to {new_zone}")

            self._last_positions = current_positions.copy()

            # Determina la ragione del cambiamento
            reason = "Zone changes: " + ", ".join(changes) if changes else "Periodic update"

            # Update coordinator data
            self.data = {
                "image_path": image_path,
                "last_changed": current_time,
                "last_reason": reason,
                "user_positions": current_positions,
                "image_changed": True # Assuming image changed if positions changed
            }

            # Fire event for image change
            self.hass.bus.async_fire(EVENT_IMAGE_CHANGED, {
                "image_path": image_path,
                "reason": reason,
                "timestamp": current_time.isoformat(),
                "web_url": image_path.replace('/config/www/', '/local/') if image_path and image_path.startswith('/config/www/') else image_path
            })
            _LOGGER.info(f"Weasley Clock image updated: {image_path}")

            _LOGGER.debug(f"Update completed: reason='{reason}'")
            return self.data

        except Exception as err:
            _LOGGER.error(f"Error updating Weasley Clock data: {err}")
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _setup_person_tracking(self) -> None:
        """Set up tracking for person entity changes."""
        @callback
        def person_state_changed(event):
            """Handle person state changes."""
            entity_id = event.data.get('entity_id', '')
            if not entity_id.startswith('person.'):
                return

            old_state = event.data.get('old_state')
            new_state = event.data.get('new_state')

            if old_state and new_state:
                old_zone = old_state.state
                new_zone = new_state.state

                if old_zone != new_zone:
                    friendly_name = new_state.attributes.get('friendly_name', entity_id)
                    _LOGGER.info(f"Person {friendly_name} moved from {old_zone} to {new_zone}")

                    # Trigger immediate update
                    self.hass.async_create_task(
                        self.async_request_refresh()
                    )

        # Track state changes for person entities only
        person_entities = [eid for eid in self.hass.states.async_entity_ids("person")]
        if person_entities:
            async_track_state_change_event(self.hass, person_entities, person_state_changed)


    async def _check_person_changes(self) -> None:
        """Check for new or removed person entities."""
        try:
            current_persons = set()
            for entity_id in self.hass.states.async_entity_ids('person'):
                current_persons.add(entity_id)

            # Check for new persons
            new_persons = current_persons - self._last_persons
            if new_persons:
                for person in new_persons:
                    state = self.hass.states.get(person)
                    friendly_name = state.attributes.get('friendly_name', person) if state else person
                    _LOGGER.info(f"New person entity detected: {friendly_name} ({person})")

                self._last_persons = current_persons

            # Check for removed persons
            removed_persons = self._last_persons - current_persons
            if removed_persons:
                for person in removed_persons:
                    _LOGGER.info(f"Person entity removed: {person}")

                self._last_persons = current_persons

        except Exception as e:
            _LOGGER.error(f"Error checking for person changes: {e}")

    async def async_generate_image(self, reason: str = "Manual update") -> str:
        """Generate clock image manually with reason."""
        try:
            # Store previous hash to detect changes
            previous_hash = getattr(self.generator, 'last_image_hash', None)

            # Generate new image
            image_path = await self.hass.async_add_executor_job(
                self.generator.generate_clock_image
            )

            # Check if image actually changed
            current_hash = getattr(self.generator, 'last_image_hash', None)
            image_changed = previous_hash != current_hash

            # Only update timestamp if image actually changed
            if image_changed:
                current_time = dt_util.now()

                # Update coordinator data
                self.data = {
                    "image_path": image_path,
                    "last_changed": current_time,
                    "last_reason": reason,
                    "image_changed": image_changed
                }

                # Fire event for image change
                self.hass.bus.async_fire(EVENT_IMAGE_CHANGED, {
                    "image_path": image_path,
                    "reason": reason,
                    "timestamp": current_time.isoformat()
                })

                _LOGGER.info(f"Manual image generation completed with changes: {reason}")
            else:
                # Keep existing timestamp if image didn't change
                # Ensure self.data is not None before accessing its attributes
                last_changed_time = self.data.get("last_changed") if self.data else None
                self.data = {
                    "image_path": image_path,
                    "last_changed": last_changed_time,
                    "last_reason": "No changes detected (manual generation)",
                    "image_changed": image_changed
                }

                _LOGGER.info(f"Manual image generation completed with no changes: {reason}")

            # Notify all listeners (sensors) of the update
            self.async_update_listeners()

            return image_path

        except Exception as err:
            _LOGGER.error(f"Error generating Weasley Clock image: {err}")
            raise