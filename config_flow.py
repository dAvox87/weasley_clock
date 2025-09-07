
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

                    # Se auto discovery è disabilitata, vai alla configurazione manuale utenti
                    if not user_input.get("auto_discover_users", True):
                        return await self.async_step_manual_users()

                    # Se auto discovery è abilitata, vai alla configurazione filtri utenti
                    return await self.async_step_user_filters()
                    
            except Exception as e:
                _LOGGER.error(f"Error in user step: {e}")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Optional("auto_discover_users", default=True):
            bool,
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

    async def async_step_manual_users(self,
                                      user_input: dict[str, Any] | None = None
                                      ) -> FlowResult:
        """Configure manual users."""
        errors = {}

        if user_input is not None:
            try:
                users_config = user_input.get("users_config", "").strip()
                if not users_config:
                    errors["users_config"] = "users_required"
                else:
                    # Validate user configuration format
                    valid_users = 0
                    for line in users_config.split('\n'):
                        line = line.strip()
                        if line and ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 3:
                                entity_id, name, image_path = parts[0].strip(), parts[1].strip(), parts[2].strip()
                                if entity_id.startswith('person.') and name and image_path:
                                    valid_users += 1
                    
                    if valid_users == 0:
                        errors["users_config"] = "invalid_format"
                    else:
                        self.config_data["manual_users"] = user_input
                        return await self.async_step_zones()
                        
            except Exception as e:
                _LOGGER.error(f"Error in manual_users step: {e}")
                errors["base"] = "unknown"

        # Ottieni tutte le entità person disponibili con informazioni complete
        person_entities = []
        suggested_config = []

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

                    person_entities.append((entity_id, friendly_name,
                                            current_zone, entity_picture))

                    # Suggerisci configurazione precompilata
                    image_path = entity_picture if entity_picture else f"/config/www/images/{entity_id.split('.')[1]}.jpg"
                    suggested_config.append(
                        f"{entity_id},{friendly_name},{image_path}")
            except Exception as e:
                _LOGGER.warning(
                    f"Error processing person entity {entity_id}: {e}")
                continue

        # Pre-compila il campo con la configurazione suggerita
        default_config = "\n".join(suggested_config) if suggested_config else "person.esempio,Nome Persona,/config/www/images/esempio.jpg"

        data_schema = vol.Schema({
            vol.Required("users_config", default=default_config):
            selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT, 
                    multiline=True
                ))
        })

        # Crea informazioni dettagliate sugli utenti trovati
        persons_info = []
        if person_entities:
            persons_info.append("👥 **Utenti trovati nel sistema:**")
            for entity_id, name, zone, picture in person_entities:
                picture_info = f" 📷 {picture}" if picture else " ❌ Nessuna foto"
                persons_info.append(
                    f"• **{name}** ({entity_id})")
                persons_info.append(f"  📍 Attualmente: {zone}")
                persons_info.append(f"  {picture_info}")
        else:
            persons_info.append("❌ **Nessun utente person trovato nel sistema**")
            persons_info.append("Assicurati di aver configurato delle entità person in Home Assistant")

        return self.async_show_form(
            step_id="manual_users",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "available_persons": "\n".join(persons_info),
                "format_help": "📝 **Formato richiesto:** `entity_id,Nome Display,Percorso Immagine`\n\n✅ Il campo è già precompilato con tutti gli utenti trovati\n🖼️ Assicurati che le immagini esistano nel percorso specificato"
            },
        )

    async def async_step_user_filters(self,
                                      user_input: dict[str, Any] | None = None
                                      ) -> FlowResult:
        """Configure user filters when auto discovery is enabled."""
        errors = {}

        if user_input is not None:
            try:
                # Processa i checkbox degli utenti - deve gestire anche i valori di default
                included_users = []
                
                # Prima ottieni tutti gli utenti disponibili per controllare i default
                try:
                    person_entity_ids = self.hass.states.async_entity_ids("person")
                except Exception:
                    person_entity_ids = []

                person_entities = []
                for entity_id in person_entity_ids:
                    try:
                        state = self.hass.states.get(entity_id)
                        if state and state.attributes:
                            friendly_name = state.attributes.get(
                                "friendly_name",
                                entity_id.split('.')[1].replace('_', ' ').title())
                            entity_picture = state.attributes.get("entity_picture", "")
                            person_entities.append((entity_id, friendly_name, entity_picture))
                    except Exception:
                        continue

                # Processa ogni utente controllando sia user_input che default
                for entity_id, friendly_name, picture in person_entities:
                    checkbox_key = f"include_{entity_id}"
                    
                    # Calcola il valore di default (stesso algoritmo usato nello schema)
                    name_lower = friendly_name.lower()
                    seems_device = ('_' in name_lower
                                    or any(char.isdigit() for char in friendly_name)
                                    or name_lower in [
                                        'device', 'system', 'admin', 'guest', 'unknown'
                                    ] or len(friendly_name) < 3)
                    has_custom_image = bool(picture)
                    suggested_default = has_custom_image or not seems_device
                    
                    # Usa il valore da user_input se presente, altrimenti usa il default
                    is_selected = user_input.get(checkbox_key, suggested_default)
                    
                    if is_selected:
                        included_users.append(entity_id)

                if not included_users:
                    errors["base"] = "no_users_selected"
                else:
                    self.config_data["user_filters"] = {
                        "selected_users": included_users,
                        "exclude_local_only": user_input.get("exclude_local_only", True)
                    }
                    return await self.async_step_zones()
                    
            except Exception as e:
                _LOGGER.error(f"Error in user_filters step: {e}")
                errors["base"] = "unknown"

        # Scopri tutte le entità person nel sistema
        person_entities = []

        try:
            person_entity_ids = self.hass.states.async_entity_ids("person")
        except Exception:
            person_entity_ids = []

        if not person_entity_ids:
            # Nessun utente trovato, vai direttamente alle zone con messaggio
            return await self.async_step_zones()

        for entity_id in person_entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                if state and state.attributes:
                    friendly_name = state.attributes.get(
                        "friendly_name",
                        entity_id.split('.')[1].replace('_', ' ').title())
                    entity_picture = state.attributes.get("entity_picture", "")
                    current_zone = state.state

                    person_entities.append((entity_id, friendly_name,
                                            current_zone, entity_picture))
            except Exception as e:
                _LOGGER.warning(
                    f"Error processing person entity {entity_id}: {e}")
                continue

        # Crea schema dinamico con checkbox per ogni utente
        schema_dict = {}

        # Aggiungi opzione generale
        schema_dict[vol.Optional("exclude_local_only", default=True)] = bool

        # Aggiungi checkbox per ogni utente (includi di default quelli con foto)
        for entity_id, friendly_name, zone, picture in person_entities:
            # Determina se suggerire l'inclusione di default
            name_lower = friendly_name.lower()
            seems_device = ('_' in name_lower
                            or any(char.isdigit() for char in friendly_name)
                            or name_lower in [
                                'device', 'system', 'admin', 'guest', 'unknown'
                            ] or len(friendly_name) < 3)
            has_custom_image = bool(picture)
            suggested = has_custom_image or not seems_device

            schema_dict[vol.Optional(f"include_{entity_id}",
                                     default=suggested)] = bool

        data_schema = vol.Schema(schema_dict)

        # Crea informazioni per l'utente
        user_info = []
        user_info.append("👥 **Seleziona gli utenti da mostrare nell'orologio:**")
        user_info.append("")
        for entity_id, name, zone, picture in person_entities:
            pic_info = "📷" if picture else "❌"
            user_info.append(f"{pic_info} **{name}**")
            user_info.append(f"    📍 Attualmente: {zone}")
            user_info.append(f"    🆔 ID: {entity_id}")
            user_info.append("")

        return self.async_show_form(
            step_id="user_filters",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "discovered_users": "\n".join(user_info),
                "selection_help": "✅ **Gli utenti con foto sono pre-selezionati**\n📱 Disabilita 'Escludi utenti solo locali' se vuoi includere dispositivi che non escono mai di casa",
            },
        )

    async def async_step_zones(self,
                               user_input: dict[str, Any] | None = None
                               ) -> FlowResult:
        """Configure zones with locked IDs and inline name configuration."""
        errors = {}

        if user_input is not None:
            try:
                # Collect zone configurations using zone list from previous step
                zone_configs = []
                
                # Get discovered zones from previous processing
                discovered_zones = set()
                zones_usage = {}

                try:
                    person_entity_ids = self.hass.states.async_entity_ids("person")
                except Exception:
                    person_entity_ids = []

                for entity_id in person_entity_ids:
                    try:
                        state = self.hass.states.get(entity_id)
                        if state and state.attributes:
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

                actual_zones = zone_priority  # Supporta tutte le zone dinamicamente
                
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

        # Scopri automaticamente le zone utilizzate dalle persone nel sistema
        discovered_zones = set()
        zones_usage = {}

        try:
            person_entity_ids = self.hass.states.async_entity_ids("person")
        except Exception:
            person_entity_ids = []

        for entity_id in person_entity_ids:
            try:
                state = self.hass.states.get(entity_id)
                if state and state.attributes:
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

        # Ottieni anche le zone definite in Home Assistant
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

        # Aggiungi sempre le zone di base
        basic_zones = ['home', 'not_home', 'unknown']
        for basic_zone in basic_zones:
            discovered_zones.add(basic_zone)

        # Prepara zone suggerite con priorità a quelle più utilizzate
        zone_priority = []
        for zone in ['home', 'not_home']:
            if zone in discovered_zones:
                zone_priority.append(zone)
        
        for zone in sorted(discovered_zones):
            if zone not in zone_priority:
                zone_priority.append(zone)
        
        if not zone_priority:
            zone_priority = ["home", "work", "school", "gym"]

        # Crea schema dinamico con solo i nomi editabili
        # Gli ID zone saranno mostrati nelle description_placeholders
        schema_dict = {}
        actual_zones = zone_priority  # RIMUOVO IL LIMITE: mostra TUTTE le zone trovate
        
        for i, zone in enumerate(actual_zones):
            display_name = zone.replace('_', ' ').title()
            if zone == 'not_home':
                display_name = 'Fuori Casa'
            elif zone == 'home':
                display_name = 'Casa'

            # Mostra l'ID zona direttamente nel label del campo
            field_label = f"📍 {zone} → Nome visualizzato"
            schema_dict[vol.Required(f"zone_{i}_name", default=display_name, description=field_label)] = selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT
                ))

        data_schema = vol.Schema(schema_dict)

        # Crea tabella zone con ID fissi e nomi editabili - TUTTE LE ZONE
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
                "zones_help": "✏️ **Modifica i nomi nei campi sopra**\n📌 **Gli ID zone (come 'home', 'work', ecc.) sono fissi e corrispondono a Home Assistant**\n🔍 **Ogni campo mostra chiaramente l'ID zona corrispondente**"
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
                elif not output_path.startswith("/config/www/"):
                    errors["output_path"] = "invalid_path"
                elif not output_path.endswith(".png"):
                    errors["output_path"] = "invalid_extension"
                else:
                    self.config_data.update(user_input)

                    # Crea la configurazione finale
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
                "final_step": "🎨 **Configurazione finale completata!**\n\n📁 L'immagine dell'orologio sarà salvata nel percorso specificato\n🌐 Assicurati che il percorso inizi con `/config/www/` per essere accessibile via web\n🖼️ Il file deve avere estensione `.png`\n\n📝 **Configurazione Font Etichette Zone:**\n• Font Minimo: dimensione minima del testo delle zone\n• Font Massimo: dimensione massima del testo delle zone\n• Fattore Riduzione: quanto ridurre il font per testi lunghi (0.15 = 15% per ogni gruppo di 4 caratteri)"
            }
        )

    def _build_final_config(self) -> dict[str, Any]:
        """Build the final configuration dictionary."""
        config = {
            "auto_discover_users":
            self.config_data.get("auto_discover_users", True),
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
        }

        # Parse manual users if configured
        if not config[
                "auto_discover_users"] and "manual_users" in self.config_data:
            users_text = self.config_data["manual_users"].get(
                "users_config", "")
            users = {}
            for line in users_text.split('\n'):
                line = line.strip()
                if line and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        entity_id, name, image_path = parts[0].strip(
                        ), parts[1].strip(), parts[2].strip()
                        users[entity_id] = {
                            "name": name,
                            "image_path": image_path
                        }
            config["users"] = users

        # Parse user filters if auto discovery is enabled
        if config["auto_discover_users"] and "user_filters" in self.config_data:
            user_filters = {}

            # Get selected users from checkbox processing
            selected_users = self.config_data["user_filters"].get(
                "selected_users", [])
            if selected_users:
                user_filters["included_users"] = selected_users

            # Include exclude_local_only setting
            user_filters["exclude_local_only"] = self.config_data[
                "user_filters"].get("exclude_local_only", True)

            config["user_filters"] = user_filters

        # Parse zones from new structure
        zones = {}
        zone_mapping = {}
        if "zones" in self.config_data and "zone_configs" in self.config_data[
                "zones"]:
            # Colori predefiniti per le zone
            default_colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#795548", "#607D8B", "#FFC107"]
            
            for i, zone_config in enumerate(self.config_data["zones"]["zone_configs"]):
                zone_id = zone_config["id"]
                # Usa un colore dalla lista predefinita basato sull'indice
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
        # Get the entry being reconfigured
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
            required_fields = ["auto_discover_users", "zones"]
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
            if not output_path.startswith("/config/www/") or not output_path.endswith(".png"):
                _LOGGER.error("Invalid output path")
                return False

            return True
        except Exception as e:
            _LOGGER.error(f"Config validation error: {e}")
            return False
