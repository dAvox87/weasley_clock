import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class WeasleyClockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weasley Clock."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self.config_data = {}

    async def async_step_user(self,
                              user_input: dict[str, Any] | None = None
                              ) -> FlowResult:
        """Handle the initial step."""
        
        # Check if already configured - only allow one instance (unless we're reconfiguring)
        existing_entries = self._async_current_entries()
        if existing_entries and not self.context.get("source") == config_entries.SOURCE_RECONFIGURE:
            return self.async_abort(reason="single_instance_allowed")
        
        errors = {}

        if user_input is not None:
            try:
                # Validate update interval
                interval = user_input.get("update_interval_seconds", 30)
                if interval < 10:
                    errors["update_interval_seconds"] = "interval_too_small"
                elif interval > 300:
                    errors["update_interval_seconds"] = "interval_too_large"
                
                # Validate clock dimensions
                width = user_input.get("clock_width", 400)
                height = user_input.get("clock_height", 448)
                if width < 200 or height < 200:
                    errors["base"] = "dimensions_too_small"
                elif width > 800 or height > 800:
                    errors["base"] = "dimensions_too_large"
                
                if not errors:
                    self.config_data.update(user_input)
                    return await self.async_step_select_users()
                    
            except Exception as e:
                _LOGGER.error(f"Error in user step: {e}")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Optional("auto_update_enabled", default=True):
            bool,
            vol.Optional("update_interval_seconds", default=30):
            vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional("clock_width", default=400):
            vol.All(vol.Coerce(int), vol.Range(min=200, max=800)),
            vol.Optional("clock_height", default=448):
            vol.All(vol.Coerce(int), vol.Range(min=200, max=800)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "setup_info": "🏠 L'orologio Weasley mostra la posizione dei membri della famiglia in tempo reale, proprio come nei film di Harry Potter!"
            }
        )

    async def async_step_select_users(self,
                                      user_input: dict[str, Any] | None = None
                                      ) -> FlowResult:
        """Select users with weasleyclock tag and add tag to them."""
        errors = {}

        if user_input is not None:
            try:
                # Get selected users
                selected_users = []
                
                # Collect all person entities and check which ones are selected
                try:
                    person_entity_ids = self.hass.states.async_entity_ids("person")
                except Exception:
                    person_entity_ids = []

                for entity_id in person_entity_ids:
                    checkbox_key = f"include_{entity_id}"
                    if user_input.get(checkbox_key, False):
                        selected_users.append(entity_id)

                if not selected_users:
                    errors["base"] = "no_users_selected"
                else:
                    # Add weasleyclock tag to selected users
                    for entity_id in selected_users:
                        try:
                            # Get current tags
                            state = self.hass.states.get(entity_id)
                            if state:
                                current_tags = state.attributes.get('tags', [])
                                if 'weasleyclock' not in current_tags:
                                    current_tags = list(current_tags) if current_tags else []
                                    current_tags.append('weasleyclock')
                                    # Update person entity with new tag
                                    self.hass.states.async_set(
                                        entity_id,
                                        state.state,
                                        {**state.attributes, 'tags': current_tags}
                                    )
                                    _LOGGER.info(f"Added weasleyclock tag to {entity_id}")
                        except Exception as e:
                            _LOGGER.error(f"Error adding tag to {entity_id}: {e}")

                    self.config_data["selected_users"] = selected_users
                    return await self.async_step_zones()
                    
            except Exception as e:
                _LOGGER.error(f"Error in select_users step: {e}")
                errors["base"] = "unknown"

        # Get all person entities
        person_entities = []
        
        try:
            person_entity_ids = self.hass.states.async_entity_ids("person")
        except Exception:
            person_entity_ids = []

        for entity_id in person_entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                if state and state.attributes:
                    friendly_name = state.attributes.get(
                        "friendly_name",
                        entity_id.split('.')[1].replace('_', ' ').title())
                    entity_picture = state.attributes.get("entity_picture", "")
                    current_zone = state.state
                    
                    # Check if already has weasleyclock tag
                    has_tag = 'weasleyclock' in state.attributes.get('tags', [])

                    person_entities.append((entity_id, friendly_name,
                                          current_zone, entity_picture, has_tag))
            except Exception as e:
                _LOGGER.warning(
                    f"Error processing person entity {entity_id}: {e}")
                continue

        # Create dynamic schema with checkboxes
        schema_dict = {}
        
        for entity_id, friendly_name, zone, picture, has_tag in person_entities:
            # Pre-select if already has tag
            schema_dict[vol.Optional(f"include_{entity_id}",
                                     default=has_tag)] = bool

        data_schema = vol.Schema(schema_dict)

        # Create user info
        user_info = []
        user_info.append("👥 **Seleziona gli utenti da tracciare con l'orologio:**")
        user_info.append("")
        for entity_id, name, zone, picture, has_tag in person_entities:
            pic_info = "📷" if picture else "❌"
            tag_info = "✅ Tag presente" if has_tag else "❌ Nessun tag"
            user_info.append(f"{pic_info} **{name}**")
            user_info.append(f"    📍 Attualmente: {zone}")
            user_info.append(f"    🆔 ID: {entity_id}")
            user_info.append(f"    🏷️ {tag_info}")
            user_info.append("")

        return self.async_show_form(
            step_id="select_users",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "discovered_users": "\n".join(user_info),
                "selection_help": "✅ **Seleziona gli utenti da tracciare**\n🏷️ Il tag 'weasleyclock' verrà aggiunto automaticamente",
            },
        )

    async def async_step_zones(self,
                               user_input: dict[str, Any] | None = None
                               ) -> FlowResult:
        """Configure zones with locked IDs and inline name configuration."""
        errors = {}

        if user_input is not None:
            try:
                # Collect zone configurations
                zone_configs = []
                
                # Get discovered zones from selected users
                discovered_zones = set()
                zones_usage = {}

                try:
                    person_entity_ids = self.hass.states.async_entity_ids("person")
                except Exception:
                    person_entity_ids = []

                for entity_id in person_entity_ids:
                    try:
                        state = self.hass.states.get(entity_id)
                        if state and 'weasleyclock' in state.attributes.get('tags', []):
                            zone = state.state
                            discovered_zones.add(zone)
                    except Exception:
                        continue

                # Get zone entities
                try:
                    zone_entity_ids = self.hass.states.async_entity_ids("zone")
                except Exception:
                    zone_entity_ids = []

                for entity_id in zone_entity_ids:
                    try:
                        state = self.hass.states.get(entity_id)
                        if state:
                            zone_name = entity_id.replace('zone.', '')
                            discovered_zones.add(zone_name)
                    except Exception:
                        continue

                # Add basic zones
                basic_zones = ['home', 'not_home', 'unknown']
                for basic_zone in basic_zones:
                    discovered_zones.add(basic_zone)

                # Build priority list
                zone_priority = []
                for zone in ['home', 'not_home']:
                    if zone in discovered_zones:
                        zone_priority.append(zone)
                
                for zone in sorted(discovered_zones):
                    if zone not in zone_priority:
                        zone_priority.append(zone)

                actual_zones = zone_priority
                
                # Process zone names from user input
                i = 0
                for zone_id in actual_zones:
                    zone_name = user_input.get(f"zone_{i}_name", "").strip()
                    if zone_name:
                        zone_configs.append({
                            "id": zone_id,
                            "name": zone_name
                        })
                    i += 1

                if not zone_configs:
                    errors["base"] = "zones_required"
                elif len(zone_configs) < 2:
                    errors["base"] = "minimum_zones_required"
                else:
                    self.config_data["zones"] = {"zone_configs": zone_configs}
                    return await self.async_step_appearance()
                    
            except Exception as e:
                _LOGGER.error(f"Error in zones step: {e}")
                errors["base"] = "unknown"

        # Discover zones from users with weasleyclock tag
        discovered_zones = set()
        zones_usage = {}

        try:
            person_entity_ids = self.hass.states.async_entity_ids("person")
        except Exception:
            person_entity_ids = []

        for entity_id in person_entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                if state and 'weasleyclock' in state.attributes.get('tags', []):
                    zone = state.state
                    friendly_name = state.attributes.get(
                        "friendly_name",
                        entity_id.split('.')[1].replace('_', ' ').title())

                    discovered_zones.add(zone)
                    if zone not in zones_usage:
                        zones_usage[zone] = []
                    zones_usage[zone].append(friendly_name)
            except Exception as e:
                _LOGGER.warning(
                    f"Error processing person entity {entity_id}: {e}")
                continue

        # Get zones defined in Home Assistant
        try:
            zone_entity_ids = self.hass.states.async_entity_ids("zone")
        except Exception:
            zone_entity_ids = []

        for entity_id in zone_entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                if state and state.attributes:
                    zone_name = entity_id.replace('zone.', '')
                    discovered_zones.add(zone_name)
            except Exception as e:
                _LOGGER.warning(
                    f"Error processing zone entity {entity_id}: {e}")
                continue

        # Add basic zones
        basic_zones = ['home', 'not_home', 'unknown']
        for basic_zone in basic_zones:
            discovered_zones.add(basic_zone)

        # Prepare suggested zones with priority
        zone_priority = []
        for zone in ['home', 'not_home']:
            if zone in discovered_zones:
                zone_priority.append(zone)
        
        for zone in sorted(discovered_zones):
            if zone not in zone_priority:
                zone_priority.append(zone)
        
        if not zone_priority:
            zone_priority = ["home", "work", "school", "gym"]

        # Create dynamic schema
        schema_dict = {}
        actual_zones = zone_priority
        
        for i, zone in enumerate(actual_zones):
            display_name = zone.replace('_', ' ').title()
            if zone == 'not_home':
                display_name = 'Fuori Casa'
            elif zone == 'home':
                display_name = 'Casa'

            field_label = f"📍 {zone} → Nome visualizzato"
            schema_dict[vol.Required(f"zone_{i}_name", default=display_name, description=field_label)] = selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT
                ))

        data_schema = vol.Schema(schema_dict)

        # Create zone table
        zone_table = []
        zone_table.append(f"📋 **Configurazione Zone** ({len(actual_zones)} zone trovate):")
        zone_table.append("")
        zone_table.append("| **ID Zona (fisso)** | **Nome Personalizzato** | **Utenti Attuali** |")
        zone_table.append("|---------------------|-------------------------|-------------------|")
        
        for i, zone in enumerate(actual_zones):
            display_name = zone.replace('_', ' ').title()
            if zone == 'not_home':
                display_name = 'Fuori Casa'
            elif zone == 'home':
                display_name = 'Casa'
            
            users_in_zone = zones_usage.get(zone, [])
            users_info = ', '.join(users_in_zone) if users_in_zone else "Nessuno"
            
            zone_table.append(f"| **`{zone}`** | {display_name} | {users_info} |")
        
        zone_table.append("")
        zone_table.append("🎨 **I colori sono assegnati automaticamente**")
        zone_table.append("⚠️ **Servono almeno 2 zone per creare l'orologio**")
        zone_table.append("📌 **Gli ID zone sono quelli di Home Assistant e NON possono essere modificati**")

        return self.async_show_form(
            step_id="zones",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "discovered_zones": "\n".join(zone_table),
                "zones_help": "✏️ **Modifica i nomi nei campi sopra**\n📌 **Gli ID zone (come 'home', 'work', ecc.) sono fissi e corrispondono a Home Assistant**",
            },
        )

    async def async_step_appearance(self,
                                    user_input: dict[str, Any] | None = None
                                    ) -> FlowResult:
        """Configure appearance settings."""
        errors = {}

        if user_input is not None:
            try:
                output_path = user_input.get("output_path", "").strip()
                if not output_path:
                    errors["output_path"] = "path_required"
                elif not output_path.endswith(".png"):
                    errors["output_path"] = "invalid_extension"
                else:
                    self.config_data.update(user_input)

                    # Build final config
                    final_config = self._build_final_config()

                    # Validate the final configuration
                    if not self._validate_config(final_config):
                        errors["base"] = "invalid_config"
                    else:
                        # Check if we're reconfiguring an existing entry
                        if self.context.get("source") == config_entries.SOURCE_RECONFIGURE:
                            reconfigure_entry = self._get_reconfigure_entry()
                            return self.async_update_reload_and_abort(
                                reconfigure_entry,
                                data_updates=final_config,
                                reason="reconfigure_successful"
                            )
                        else:
                            return self.async_create_entry(
                                title=f"{NAME} - {len(final_config.get('zones', {}).get('zone_configs', []))} zone",
                                data=final_config,
                            )
                        
            except Exception as e:
                _LOGGER.error(f"Error in appearance step: {e}")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required("output_path",
                         default="/config/www/weasley_clock.png"):
            str,
            vol.Optional("min_font_size", default=14):
            vol.All(vol.Coerce(int), vol.Range(min=8, max=20)),
            vol.Optional("max_font_size", default=38):
            vol.All(vol.Coerce(int), vol.Range(min=20, max=60)),
            vol.Optional("font_reduction_factor", default=0.15):
            vol.All(vol.Coerce(float), vol.Range(min=0.05, max=0.30)),
        })

        return self.async_show_form(
            step_id="appearance",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "final_step": "🎨 **Configurazione finale!**\n\n📁 L'immagine dell'orologio sarà salvata nel percorso specificato\n✏️ Puoi usare qualsiasi percorso valido (es: `/config/www/mio_orologio.png`)\n🎯 Assicurati che la cartella esista in Home Assistant",
            }
        )

    def _build_final_config(self) -> dict[str, Any]:
        """Build the final configuration dictionary."""
        config = {
            "auto_update_enabled":
            self.config_data.get("auto_update_enabled", True),
            "update_interval_seconds":
            self.config_data.get("update_interval_seconds", 30),
            "clock_width":
            self.config_data.get("clock_width", 400),
            "clock_height":
            self.config_data.get("clock_height", 448),
            "output_path":
            self.config_data.get("output_path",
                                 "/config/www/weasley_clock.png"),
            "min_font_size":
            self.config_data.get("min_font_size", 14),
            "max_font_size":
            self.config_data.get("max_font_size", 38),
            "font_reduction_factor":
            self.config_data.get("font_reduction_factor", 0.15),
            "selected_users":
            self.config_data.get("selected_users", []),
        }

        # Parse zones from new structure
        zones = {}
        zone_mapping = {}
        if "zones" in self.config_data and "zone_configs" in self.config_data[
                "zones"]:
            # Default colors for zones
            default_colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#795548", "#607D8B", "#FFC107"]
            
            for i, zone_config in enumerate(self.config_data["zones"]["zone_configs"]):
                zone_id = zone_config["id"]
                default_color = default_colors[i % len(default_colors)]
                zones[zone_id] = {
                    "label": zone_config["name"],
                    "color": default_color
                }
                zone_mapping[zone_id] = zone_config["name"]

        config["zones"] = zones
        config["zone_mapping"] = zone_mapping

        return config

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration of the component."""
        reconfigure_entry = self._get_reconfigure_entry()
        if not reconfigure_entry:
            return self.async_abort(reason="no_entry_to_reconfigure")
        
        # Load existing configuration data
        self.config_data = reconfigure_entry.data.copy()
        
        # Start from the beginning with existing data pre-filled
        return await self.async_step_user(user_input)
    
    def _get_reconfigure_entry(self):
        """Get the config entry being reconfigured."""
        return self.hass.config_entries.async_get_entry(self.context["entry_id"])

    def _validate_config(self, config: dict[str, Any]) -> bool:
        """Validate the final configuration."""
        try:
            # Validate required fields
            required_fields = ["selected_users", "zones"]
            for field in required_fields:
                if field not in config:
                    _LOGGER.error(f"Missing required field: {field}")
                    return False

            # Validate zones configuration
            if not isinstance(config["zones"], dict) or len(config["zones"]) < 2:
                _LOGGER.error("At least 2 zones are required")
                return False

            # Validate dimensions
            if config.get("clock_width", 0) < 200 or config.get(
                    "clock_height", 0) < 200:
                _LOGGER.error("Clock dimensions too small")
                return False

            # Validate output path
            output_path = config.get("output_path", "")
            if not output_path.endswith(".png"):
                _LOGGER.error("Invalid output path")
                return False

            return True
        except Exception as e:
            _LOGGER.error(f"Config validation error: {e}")
            return False
