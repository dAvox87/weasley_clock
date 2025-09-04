"""
Weasley Clock Generator
Generates dynamic clock face images showing family member positions across different zones
"""
from __future__ import annotations

import math
import os
import logging
import hashlib
from io import BytesIO
from typing import Dict, List, Tuple, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as err:
    _LOGGER.error("PIL (Pillow) is required for image generation: %s", err)
    raise

try:
    import requests
except ImportError:
    _LOGGER.warning("requests library not available, URL images will not work")
    requests = None

from homeassistant.core import HomeAssistant
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class WeasleyClockGenerator:

    def __init__(self, hass: HomeAssistant, config_data: dict = None):
        """Initialize the Weasley Clock generator with Home Assistant instance."""
        self.hass = hass
        self.width = 400
        self.height = 448
        # Center will be calculated dynamically based on zone optimization
        self.center_x = None
        self.center_y = None
        self.outer_radius = 180
        self.inner_radius = 40
        # Use default configuration (no file loading in event loop)
        if config_data:
            self.config = self._build_config_from_entry(config_data)
        else:
            self.config = self._get_default_config()
        self.last_image_hash = None  # Track image changes

    def _get_default_config(self):
        """Get configuration from file or return defaults."""
        # Try to load from config file first
        config_path_yaml = "/config/custom_components/weasley_clock/config.yaml"

        default_config = {
            "auto_discover_users": True,
            "auto_update_enabled": True,
            "update_interval_seconds": 30,
            "output_path": '/config/www/weasley_clock.png',
            "zone_mapping": {},
            "zones": {
                "home": {
                    "label": "Casa",
                    "color": "#4CAF50"
                },
                "work": {
                    "label": "Lavoro",
                    "color": "#2196F3"
                },
                "school": {
                    "label": "Scuola",
                    "color": "#FF9800"
                },
                "gym": {
                    "label": "Palestra",
                    "color": "#9C27B0"
                },
                "shopping": {
                    "label": "Shopping",
                    "color": "#F44336"
                },
                "traveling": {
                    "label": "Viaggio",
                    "color": "#795548"
                },
                "unknown": {
                    "label": "Sconosciuto",
                    "color": "#607D8B"
                }
            },
            "clock_style": {
                "background_color": '#D2B48C',
                "border_color": '#8B4513',
                "text_color": '#654321',
                "hand_color": '#2F1B14',
                "oval_color": '#F5DEB3',
                "ornament_color": '#CD853F'
            },
            "user_filters": {
                "excluded_users": [],
                "included_users": [],
                "exclude_local_only": False
            }
        }

        # The config.yaml loading is now removed as per the config flow implementation.
        # The configuration is now managed entirely through the Home Assistant config entry.

        return default_config

    def _build_config_from_entry(self, config_data: dict) -> dict:
        """Build configuration from config entry data."""
        config = {
            "auto_discover_users":
            config_data.get("auto_discover_users", True),
            "auto_update_enabled":
            config_data.get("auto_update_enabled", True),
            "update_interval_seconds":
            config_data.get("update_interval_seconds", 30),
            "output_path":
            config_data.get("output_path", '/config/www/weasley_clock.png'),
            "zone_mapping":
            config_data.get("zone_mapping", {}),
            "zones":
            config_data.get(
                "zones", {
                    "home": {
                        "label": "Casa",
                        "color": "#4CAF50"
                    },
                    "work": {
                        "label": "Lavoro",
                        "color": "#2196F3"
                    },
                    "school": {
                        "label": "Scuola",
                        "color": "#FF9800"
                    },
                    "gym": {
                        "label": "Palestra",
                        "color": "#9C27B0"
                    },
                    "shopping": {
                        "label": "Shopping",
                        "color": "#F44336"
                    },
                    "traveling": {
                        "label": "Viaggio",
                        "color": "#795548"
                    },
                    "unknown": {
                        "label": "Sconosciuto",
                        "color": "#607D8B"
                    }
                }),
            "clock_style": {
                "background_color": '#D2B48C',
                "border_color": '#8B4513',
                "text_color": '#654321',
                "hand_color": '#2F1B14',
                "oval_color": '#F5DEB3',
                "ornament_color": '#CD853F'
            },
            "user_filters":
            config_data.get(
                "user_filters", {
                    "excluded_users": [],
                    "selected_users": [],
                    "exclude_local_only": False
                })
        }
        return config

    def _get_all_person_entities(self) -> Dict[str, Dict]:
        """Get all person entities from Home Assistant automatically."""
        person_entities = {}

        # Get all entities from Home Assistant
        try:
            # Get all states from Home Assistant
            if hasattr(self.hass.states, 'async_all'):
                all_states = self.hass.states.async_all()
                # async_all() returns a list of state objects, not tuples
                for state in all_states:
                    entity_id = state.entity_id
                    if entity_id.startswith('person.'):
                        # Extract person information from Home Assistant
                        attributes = getattr(state, 'attributes', {})
                        entity_picture = attributes.get('entity_picture', '')
                        person_info = {
                            'name':
                            attributes.get(
                                'friendly_name',
                                entity_id.split('.')[1].replace('_',
                                                                ' ').title()),
                            'image_path':
                            entity_picture,
                            'zone':
                            state.state
                        }
                        person_entities[entity_id] = person_info
                        _LOGGER.debug(
                            f"Found person entity: {entity_id} - {person_info['name']} in {person_info['zone']}, image: {entity_picture or 'none'}"
                        )
            else:
                # Fallback for testing: use entity_ids method
                for entity_id in self.hass.states.async_entity_ids():
                    if entity_id.startswith('person.'):
                        state = self.hass.states.get(entity_id)
                        if state:
                            attributes = getattr(state, 'attributes', {})
                            entity_picture = attributes.get(
                                'entity_picture', '')
                            person_info = {
                                'name':
                                attributes.get(
                                    'friendly_name',
                                    entity_id.split('.')[1].replace(
                                        '_', ' ').title()),
                                'image_path':
                                entity_picture,
                                'zone':
                                state.state
                            }
                            person_entities[entity_id] = person_info
                            _LOGGER.debug(
                                f"Found person entity: {entity_id} - {person_info['name']} in {person_info['zone']}, image: {entity_picture or 'none'}"
                            )
        except Exception as e:
            _LOGGER.error(f"Error getting person entities: {e}")
            # Fallback to empty dict if discovery fails
            return {}

        return person_entities

    def _apply_user_filters(
            self, person_entities: Dict[str, Dict]) -> Dict[str, Dict]:
        """Apply user filters to exclude unwanted users."""
        user_filters = self.config.get('user_filters', {})
        filtered_entities = {}

        _LOGGER.info(f"Applying user filters. Config: {user_filters}")
        _LOGGER.info(f"Found person entities: {list(person_entities.keys())}")

        # Se è specificata una lista di utenti inclusi, usa SOLO quelli (logica corretta)
        included_users = user_filters.get('selected_users', [])
        _LOGGER.info(f"Selected users from config: {included_users}")

        if included_users:
            for entity_id in included_users:
                if entity_id in person_entities:
                    filtered_entities[entity_id] = person_entities[entity_id]
                    _LOGGER.info(f"Including selected user: {entity_id}")
                else:
                    _LOGGER.warning(
                        f"Selected user {entity_id} not found in discovered entities"
                    )
            _LOGGER.info(
                f"After user selection: {len(filtered_entities)} users")
            return filtered_entities

        # Se non ci sono utenti selezionati specifici, applica filtri di esclusione tradizionali
        excluded_users = user_filters.get('excluded_users', [])
        exclude_local_only = user_filters.get('exclude_local_only', False)

        for entity_id, person_info in person_entities.items():
            # Salta utenti nella lista di esclusione manuale
            if entity_id in excluded_users:
                _LOGGER.debug(f"Excluding user from blacklist: {entity_id}")
                continue

            # Se abilitato, esclude utenti che sembrano essere solo locali/dispositivi di sistema
            if exclude_local_only:
                # Verifica se l'utente ha un'immagine personalizzata (indica utente reale)
                has_custom_image = person_info.get('image_path', '') != ''

                # Verifica se il nome sembra un dispositivo/sistema (contiene numeri, underscore, ecc.)
                name = person_info.get('name', '')
                seems_device = (
                    '_' in name.lower() or any(char.isdigit() for char in name)
                    or name.lower()
                    in ['device', 'system', 'admin', 'guest', 'unknown']
                    or len(name) < 3)

                # Se non ha immagine personalizzata E sembra un dispositivo, escludilo
                if not has_custom_image and seems_device:
                    _LOGGER.debug(
                        f"Excluding local/device user: {entity_id} - {name}")
                    continue

            # Aggiungi l'utente se passa tutti i filtri
            filtered_entities[entity_id] = person_info
            _LOGGER.debug(
                f"Including filtered user: {entity_id} - {person_info['name']}"
            )

        _LOGGER.info(
            f"User filtering: {len(person_entities)} found, {len(filtered_entities)} included after filtering"
        )
        return filtered_entities

    def _calculate_dynamic_center(self, zone_count: int) -> Tuple[int, int]:
        """Calculate the center position based on zone optimization for fixed image size."""
        if zone_count <= 3:
            # Quarter circle: posiziona il centro in basso a destra per mostrare il quadrante superiore sinistro
            center_x = self.width - 80  # Molto spostato a destra
            center_y = self.height - 80  # Molto spostato in basso
        elif zone_count <= 6:
            # Half circle: centro in basso per mostrare la metà superiore dell'orologio
            center_x = self.width // 2  # Centro orizzontalmente
            center_y = self.height - 100  # Spostato molto in basso
        else:
            # Full circle: centro tradizionale al centro dell'immagine
            center_x = self.width // 2
            center_y = self.height // 2

        return center_x, center_y

    def _get_display_optimization(self, zone_count: int) -> Dict:
        """Determine the optimal display configuration based on zone count."""
        if zone_count <= 3:
            # Quarter circle - show 90 degrees
            return {
                'arc_degrees': 90,
                'start_angle': -45,  # Start 45 degrees before top
                'display_type': 'quarter'
            }
        elif zone_count <= 6:
            # Half circle - show 180 degrees
            return {
                'arc_degrees': 180,
                'start_angle': -90,  # Start 90 degrees before top
                'display_type': 'half'
            }
        else:
            # Full circle - show 360 degrees
            return {
                'arc_degrees': 360,
                'start_angle': 0,
                'display_type': 'full'
            }

    def _get_user_positions(self) -> Dict[str, str]:
        """Get current positions of all tracked users."""
        positions = {}

        # Check if we should use automatic discovery or manual configuration
        if self.config.get('auto_discover_users', True):
            # Automatically discover all person entities
            person_entities = self._get_all_person_entities()
            # Apply filters
            filtered_person_entities = self._apply_user_filters(
                person_entities)
            for entity_id, info in filtered_person_entities.items():
                raw_zone = info['zone']
                mapped_zone = self._map_zone_name(raw_zone)
                positions[entity_id] = mapped_zone
                _LOGGER.debug(
                    f"Auto-discovered user {entity_id} is in zone: {raw_zone} -> {mapped_zone}"
                )
        else:
            # Use manual configuration
            # This part is less relevant now with config flow managing users directly
            # but kept for potential fallback or older configurations.
            # A more robust solution would involve getting user lists from config entry data.
            for entity_id in self.config.get('users', {}):
                try:
                    state = self.hass.states.get(entity_id)
                    if state:
                        raw_zone = state.state
                        mapped_zone = self._map_zone_name(raw_zone)
                        positions[entity_id] = mapped_zone
                        _LOGGER.debug(
                            f"Configured user {entity_id} is in zone: {raw_zone} -> {mapped_zone}"
                        )
                    else:
                        _LOGGER.warning(f"Entity {entity_id} not found")
                        positions[entity_id] = 'unknown'
                except Exception as e:
                    _LOGGER.error(
                        f"Error getting position for {entity_id}: {e}")
                    positions[entity_id] = 'unknown'

        return positions

    def _map_zone_name(self, ha_zone: str) -> str:
        """Map Home Assistant zone names to display names using zone_mapping configuration."""
        zone_mapping = self.config.get('zone_mapping', {})
        mapped_name = zone_mapping.get(ha_zone, ha_zone)

        # If no mapping found, use the zone name as-is but clean it up
        if mapped_name == ha_zone:
            # Clean up zone name: replace underscores with spaces and title case
            mapped_name = ha_zone.replace('_', ' ').title()

        return mapped_name

    def _calculate_zone_angles(self, zones: List[str]) -> Dict[str, float]:
        """Calculate angles for each zone segment across the full circle."""
        zone_angles = {}
        zone_count = len(zones)

        if zone_count == 0:
            return zone_angles

        if zone_count == 1:
            # Single zone - put it at the top (12 o'clock)
            # Nel sistema matematico standard: -90° = 12 o'clock
            zone_angles[zones[0]] = math.radians(-90)
        else:
            # Always distribute zones across the full 360-degree circle
            angle_step = 360.0 / zone_count

            for i, zone in enumerate(zones):
                # Partendo dalle 12 o'clock (-90° nel sistema matematico)
                # e andando in senso orario
                angle_degrees = -90 + (i * angle_step)
                zone_angles[zone] = math.radians(angle_degrees)

        return zone_angles

    def _draw_arc_segment(self, draw: ImageDraw.Draw, start_angle: float,
                          end_angle: float, inner_radius: int,
                          outer_radius: int, fill_color: str,
                          border_color: str) -> None:
        """Draw an arc segment (partial circle) instead of full circle."""
        # Create points for the arc segment
        points = []

        # Number of points to create smooth arc
        num_points = max(20, int(abs(end_angle - start_angle) * 20))

        # Outer arc points
        for i in range(num_points + 1):
            angle = start_angle + (end_angle - start_angle) * i / num_points
            x = self.center_x + outer_radius * math.cos(angle)
            y = self.center_y + outer_radius * math.sin(angle)
            points.append((x, y))

        # Inner arc points (reverse order)
        for i in range(num_points, -1, -1):
            angle = start_angle + (end_angle - start_angle) * i / num_points
            x = self.center_x + inner_radius * math.cos(angle)
            y = self.center_y + inner_radius * math.sin(angle)
            points.append((x, y))

        # Draw the filled segment
        if len(points) > 2:
            draw.polygon(points,
                         fill=fill_color,
                         outline=border_color,
                         width=3)

    def _draw_clock_face(self, img: Image.Image, draw: ImageDraw.Draw,
                         zones: List[str]) -> None:
        """Draw the wooden clock face like the original Weasley Clock."""
        style = self.config.get('clock_style', {})
        bg_color = style.get('background_color',
                             '#D2B48C')  # Wood color only for the clock circle
        border_color = style.get('border_color', '#8B4513')
        text_color = style.get('text_color', '#654321')
        ornament_color = style.get('ornament_color', '#CD853F')

        # Draw only the circular clock face with wood texture, leaving external area transparent
        draw.ellipse([
            self.center_x - self.outer_radius, self.center_y -
            self.outer_radius, self.center_x + self.outer_radius,
            self.center_y + self.outer_radius
        ],
                     fill=bg_color,
                     outline=border_color,
                     width=4)

        # Add ornamental border ring
        ornament_radius = self.outer_radius - 15
        draw.ellipse([
            self.center_x - ornament_radius, self.center_y - ornament_radius,
            self.center_x + ornament_radius, self.center_y + ornament_radius
        ],
                     fill=None,
                     outline=ornament_color,
                     width=3)

        # Draw continuous light band around the perimeter for text readability
        band_outer_radius = self.outer_radius - 15
        band_inner_radius = self.outer_radius - 45

        # Draw the continuous light band
        draw.ellipse([
            self.center_x - band_outer_radius, self.center_y -
            band_outer_radius, self.center_x + band_outer_radius,
            self.center_y + band_outer_radius
        ],
                     fill=(245, 245, 220, 255),
                     outline=(101, 67, 33, 255),
                     width=2)

        # Draw inner circle to create the band effect
        draw.ellipse([
            self.center_x - band_inner_radius, self.center_y -
            band_inner_radius, self.center_x + band_inner_radius,
            self.center_y + band_inner_radius
        ],
                     fill=bg_color,
                     outline=None)

        # Draw zone labels in ornamental style on the light band
        zone_angles = self._calculate_zone_angles(zones)
        for zone in zones:
            zone_config = self.config['zones'].get(zone, {})
            zone_label = zone_config.get('label', zone.title())

            # Draw decorative zone labels on the light band
            self._draw_ornamental_zone_label(img, draw, zone_label,
                                             zone_angles.get(zone, 0),
                                             text_color, ornament_color)

        # Draw ornamental center piece
        self._draw_ornamental_center(draw, border_color, ornament_color)

    def _draw_ornamental_center(self, draw: ImageDraw.Draw, border_color: str,
                                ornament_color: str) -> None:
        """Draw ornamental center piece like the original Weasley Clock."""
        # Draw main center circle
        center_radius = 20
        draw.ellipse([
            self.center_x - center_radius, self.center_y - center_radius,
            self.center_x + center_radius, self.center_y + center_radius
        ],
                     fill=border_color,
                     outline=ornament_color,
                     width=3)

        # Draw smaller inner circle for detail
        inner_radius = 12
        draw.ellipse([
            self.center_x - inner_radius, self.center_y - inner_radius,
            self.center_x + inner_radius, self.center_y + inner_radius
        ],
                     fill=ornament_color,
                     outline=border_color,
                     width=2)

        # Draw decorative center dot
        dot_radius = 4
        draw.ellipse([
            self.center_x - dot_radius, self.center_y - dot_radius,
            self.center_x + dot_radius, self.center_y + dot_radius
        ],
                     fill=border_color,
                     outline=None)

    def _draw_ornamental_zone_label(self, img: Image.Image,
                                    draw: ImageDraw.Draw, text: str,
                                    angle: float, text_color: str,
                                    ornament_color: str) -> None:
        """Draw zone labels with curved text following the clock face curvature."""
        # Load simple, readable font
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font = ImageFont.load_default()

        # Position labels clearly inside the clock face
        label_radius = self.outer_radius - 30

        # Draw text following the exact curvature of the clock face
        self._draw_curved_zone_text(draw, text, angle, label_radius, font,
                                    text_color, img)

    def _draw_simple_zone_text(self, draw: ImageDraw.Draw, text: str,
                               angle: float, radius: int,
                               font: ImageFont.FreeTypeFont,
                               text_color: str) -> None:
        """Draw zone text with rotation following the clock face direction."""
        if not text:
            return

        # Apply simple abbreviation for long zone names
        abbreviated_text = self._abbreviate_zone_text(text)

        # Calculate position around the circle
        text_x = self.center_x + radius * math.cos(angle)
        text_y = self.center_y + radius * math.sin(angle)

        # Convert angle to degrees for text rotation following the quadrant
        angle_degrees = math.degrees(angle)
        normalized_angle = (angle_degrees + 360) % 360

        # Determine rotation to follow the clock quadrant direction
        if 90 <= normalized_angle <= 270:
            # Bottom half: rotate to keep text readable (not upside down)
            rotation_degrees = angle_degrees - 90
        else:
            # Top half: normal rotation perpendicular to radius
            rotation_degrees = angle_degrees + 90

        # Get text dimensions
        bbox = draw.textbbox((0, 0), abbreviated_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Create temporary image for rotated text
        canvas_size = max(text_width, text_height) + 40
        text_img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Draw background rectangle on temporary image
        padding = 4
        bg_x = (canvas_size - text_width) // 2 - padding
        bg_y = (canvas_size - text_height) // 2 - padding
        bg_w = text_width + 2 * padding
        bg_h = text_height + 2 * padding

        text_draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
                            fill=(245, 245, 220, 220),
                            outline=None)

        # Draw text centered on temporary image
        text_draw.text(((canvas_size - text_width) // 2,
                        (canvas_size - text_height) // 2),
                       abbreviated_text,
                       fill='#2F1B14',
                       font=font)

        # Rotate the entire text image
        rotated_text = text_img.rotate(-rotation_degrees, expand=True)

        # Calculate final position to center the rotated text
        final_x = int(text_x - rotated_text.width // 2)
        final_y = int(text_y - rotated_text.height // 2)

        # This method now only handles non-rotated text for backwards compatibility
        # The rotated version is handled by _draw_rotated_zone_text

    def _abbreviate_zone_text(self, text: str) -> str:
        """Smart zone text abbreviation."""
        if not text:
            return text

        # Convert to uppercase
        text = text.upper()

        # If short enough, return as-is
        if len(text) <= 6:
            return text

        # Smart abbreviation for common zone patterns
        if ' ' in text:
            # Multi-word zones: take first letters of each word + vowels from first word
            words = text.split()
            if len(words) == 2:
                # Two words: abbreviated form
                first_word = words[0]
                second_word = words[1]

                # Take first part of first word + first letter of second
                if len(first_word) >= 4:
                    result = first_word[:4] + second_word[0]
                else:
                    result = first_word + ' ' + second_word[0]

                return result[:6]
            else:
                # More than two words: first letters
                return ''.join(word[0] for word in words[:6])
        else:
            # Single word: intelligent truncation
            if len(text) <= 8:
                return text
            else:
                # Keep consonants and some vowels for readability
                truncated = text[:6]
                return truncated

    def _draw_rotated_zone_text(self, main_img: Image.Image,
                                draw: ImageDraw.Draw, text: str, angle: float,
                                radius: int, font: ImageFont.FreeTypeFont,
                                text_color: str) -> None:
        """Draw zone text with simple rotation following the clock face direction."""
        if not text:
            return

        # Apply abbreviation for long zone names
        abbreviated_text = self._abbreviate_zone_text(text)

        # Calculate position around the circle
        text_x = self.center_x + radius * math.cos(angle)
        text_y = self.center_y + radius * math.sin(angle)

        # Convert angle to degrees for rotation
        angle_degrees = math.degrees(angle)
        normalized_angle = (angle_degrees + 360) % 360

        # Determine rotation: normal for top half, inverted for bottom half
        if 90 <= normalized_angle <= 270:
            # Bottom half: rotate to keep text readable (not upside down)
            rotation_degrees = angle_degrees - 90
        else:
            # Top half: normal rotation perpendicular to radius
            rotation_degrees = angle_degrees + 90

        # Get text dimensions
        bbox = draw.textbbox((0, 0), abbreviated_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Create temporary image for rotated text
        canvas_size = max(text_width, text_height) + 40
        text_img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Draw background rectangle
        padding = 4
        bg_x = (canvas_size - text_width) // 2 - padding
        bg_y = (canvas_size - text_height) // 2 - padding
        bg_w = text_width + 2 * padding
        bg_h = text_height + 2 * padding

        text_draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
                            fill=(245, 245, 220, 220),
                            outline=None)

        # Draw text centered
        text_draw.text(((canvas_size - text_width) // 2,
                        (canvas_size - text_height) // 2),
                       abbreviated_text,
                       fill='#2F1B14',
                       font=font)

        # Rotate the text image
        rotated_text = text_img.rotate(-rotation_degrees, expand=True)

        # Calculate final position to center the rotated text
        final_x = int(text_x - rotated_text.width // 2)
        final_y = int(text_y - rotated_text.height // 2)

        # Paste rotated text onto main image
        main_img.paste(rotated_text, (final_x, final_y), rotated_text)

    def _draw_rotated_readable_zone_text(self, main_img: Image.Image,
                                         draw: ImageDraw.Draw, text: str,
                                         angle: float, radius: int,
                                         font: ImageFont.FreeTypeFont,
                                         text_color: str) -> None:
        """Draw zone text rotated to follow the circle but ALWAYS readable from left to right."""
        if not text:
            return

        # Apply abbreviation for long zone names
        abbreviated_text = self._abbreviate_zone_text(text)

        # Calculate position around the circle
        text_x = self.center_x + radius * math.cos(angle)
        text_y = self.center_y + radius * math.sin(angle)

        # Convert angle to degrees
        angle_degrees = math.degrees(angle)
        normalized_angle = (angle_degrees + 360) % 360

        # Calculate rotation: follow the circle but NEVER make text upside down
        if 90 < normalized_angle < 270:
            # Bottom half: flip text 180° so it's readable from left to right
            rotation_degrees = angle_degrees + 180
        else:
            # Top half: use normal angle
            rotation_degrees = angle_degrees

        # Apply ±90° adjustment and check if it would make text upside down
        test_rotation = rotation_degrees + 90
        normalized_test = (test_rotation + 360) % 360

        if 90 < normalized_test < 270:
            # If +90° would make text upside down, use -90° instead
            rotation_degrees = rotation_degrees - 90
        else:
            # Otherwise use +90°
            rotation_degrees = rotation_degrees + 90

        # Get text dimensions
        bbox = draw.textbbox((0, 0), abbreviated_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Create temporary image for rotated text
        canvas_size = max(text_width, text_height) + 40
        text_img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Draw background rectangle
        padding = 4
        bg_x = (canvas_size - text_width) // 2 - padding
        bg_y = (canvas_size - text_height) // 2 - padding
        bg_w = text_width + 2 * padding
        bg_h = text_height + 2 * padding

        text_draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
                            fill=(245, 245, 220, 220),
                            outline=None)

        # Draw text centered
        text_draw.text(((canvas_size - text_width) // 2,
                        (canvas_size - text_height) // 2),
                       abbreviated_text,
                       fill='#2F1B14',
                       font=font)

        # Rotate the text image
        rotated_text = text_img.rotate(-rotation_degrees, expand=True)

        # Calculate final position to center the rotated text
        final_x = int(text_x - rotated_text.width // 2)
        final_y = int(text_y - rotated_text.height // 2)

        # Paste rotated text onto main image
        main_img.paste(rotated_text, (final_x, final_y), rotated_text)

    def _draw_straight_zone_text(self, draw: ImageDraw.Draw, text: str,
                                 angle: float, radius: int,
                                 font: ImageFont.FreeTypeFont,
                                 text_color: str) -> None:
        """Draw zone text rotated to follow the circle but always readable left-to-right."""
        if not text:
            return

        # Apply abbreviation for long zone names
        abbreviated_text = self._abbreviate_zone_text(text)

        # Calculate position around the circle
        text_x = self.center_x + radius * math.cos(angle)
        text_y = self.center_y + radius * math.sin(angle)

        # Convert angle to degrees
        angle_degrees = math.degrees(angle)
        normalized_angle = (angle_degrees + 360) % 360

        # Calculate rotation: follow the circle but keep text readable
        if 90 <= normalized_angle < 270:
            # Bottom half: add 180° to flip text so it's readable left-to-right
            rotation_degrees = angle_degrees + 180
        else:
            # Top half: use angle as-is for natural reading
            rotation_degrees = angle_degrees

        # Get text dimensions
        bbox = draw.textbbox((0, 0), abbreviated_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Create temporary image for rotated text
        canvas_size = max(text_width, text_height) + 40
        text_img = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        # Draw background rectangle
        padding = 4
        bg_x = (canvas_size - text_width) // 2 - padding
        bg_y = (canvas_size - text_height) // 2 - padding
        bg_w = text_width + 2 * padding
        bg_h = text_height + 2 * padding

        text_draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
                            fill=(245, 245, 220, 220),
                            outline=None)

        # Draw text centered
        text_draw.text(((canvas_size - text_width) // 2,
                        (canvas_size - text_height) // 2),
                       abbreviated_text,
                       fill='#2F1B14',
                       font=font)

        # Rotate the text image
        rotated_text = text_img.rotate(-rotation_degrees, expand=True)

        # Calculate final position to center the rotated text
        final_x = int(text_x - rotated_text.width // 2)
        final_y = int(text_y - rotated_text.height // 2)

        # Create main image reference for pasting
        if hasattr(draw, '_image'):
            main_img = draw._image
        else:
            # Fallback: we need to get the main image somehow
            # This is a PIL limitation, we might need to pass the main image
            # For now, we'll draw without rotation as fallback
            draw.rectangle([
                text_x - text_width / 2 - padding, text_y - text_height / 2 -
                padding, text_x + text_width / 2 + padding,
                text_y + text_height / 2 + padding
            ],
                           fill=(245, 245, 220, 220),
                           outline=None)
            draw.text((text_x - text_width / 2, text_y - text_height / 2),
                      abbreviated_text,
                      fill='#2F1B14',
                      font=font)
            return

        # Paste rotated text onto main image
        main_img.paste(rotated_text, (final_x, final_y), rotated_text)

    def _draw_curved_zone_text(self, draw: ImageDraw.Draw, text: str,
                               center_angle: float, radius: int,
                               font: ImageFont.FreeTypeFont, text_color: str,
                               main_img: Image.Image) -> None:
        """Draw text following the exact circular curvature of the clock face radius."""
        if not text:
            return

        # Get font metrics for precise calculations
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        # Calculate the angular spacing based on the actual radius and character width
        avg_char_width = text_width / len(text) if text else 1
        angular_spacing_per_char = avg_char_width / radius  # Radians per character

        # Calculate total arc length for the text
        total_arc_angle = angular_spacing_per_char * (len(text) - 1)

        # Start angle - center the text around the zone position
        start_angle = center_angle - total_arc_angle / 2

        # Draw continuous background for the entire text
        self._draw_curved_text_background(draw, text, start_angle,
                                          angular_spacing_per_char, radius,
                                          font)

        # Draw each character positioned along the circle
        for i, char in enumerate(text):
            if char == ' ':
                continue  # Skip spaces but keep their position

            # Calculate angle for this character
            char_angle = start_angle + (i * angular_spacing_per_char)

            # Position character on the circle
            char_x = self.center_x + radius * math.cos(char_angle)
            char_y = self.center_y + radius * math.sin(char_angle)

            # Simple rotation: sempre perpendicolare al raggio,
            # ma controllo se invertire per la parte bassa
            angle_degrees = math.degrees(char_angle)
            normalized_angle = (angle_degrees + 360) % 360

            if 90 <= normalized_angle <= 270:
                # Parte bassa: inverti la rotazione per evitare testo sottosopra
                rotation_degrees = angle_degrees - 90
            else:
                # Parte alta: rotazione normale
                rotation_degrees = angle_degrees + 90

            # Get character dimensions
            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_width = char_bbox[2] - char_bbox[0]
            char_height = char_bbox[3] - char_bbox[1]

            # Create temporary image for rotated character
            temp_size = max(char_width, char_height) + 20
            char_img = Image.new('RGBA', (temp_size, temp_size), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)

            # Draw character centered in temporary image
            char_draw.text(((temp_size - char_width) // 2,
                            (temp_size - char_height) // 2),
                           char,
                           fill='#2F1B14',
                           font=font)

            # Rotate character to follow circle tangent
            rotated_char = char_img.rotate(-rotation_degrees, expand=True)

            # Calculate final position
            final_x = int(char_x - rotated_char.width // 2)
            final_y = int(char_y - rotated_char.height // 2)

            # Paste rotated character onto main image
            main_img.paste(rotated_char, (final_x, final_y), rotated_char)

    def _draw_curved_text_background(self, draw: ImageDraw.Draw, text: str,
                                     start_angle: float,
                                     angular_spacing: float, radius: int,
                                     font: ImageFont.FreeTypeFont) -> None:
        """Draw a curved background that follows the text path around the circle."""
        if not text:
            return

        # Get font metrics for precise calculations
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        # Calculate the angular spacing based on the actual radius and character width
        avg_char_width = text_width / len(text) if text else 1
        angular_spacing_per_char = avg_char_width / radius  # Radians per character

        # Calculate total arc length for the text
        total_arc_angle = angular_spacing_per_char * (len(text) - 1)
        end_angle = start_angle + total_arc_angle

        # Calculate the points for the curved background
        inner_radius = radius - 12  # Background extends inward from text
        outer_radius = radius + 12  # Background extends outward from text

        # Number of points for smooth curve
        num_points = max(20, int(abs(end_angle - start_angle) * 20))

        # Create points for curved background polygon
        points = []

        # Outer arc points
        for i in range(num_points + 1):
            angle = start_angle + (end_angle - start_angle) * i / num_points
            x = self.center_x + outer_radius * math.cos(angle)
            y = self.center_y + outer_radius * math.sin(angle)
            points.append((x, y))

        # Inner arc points (reverse order)
        for i in range(num_points, -1, -1):
            angle = start_angle + (end_angle - start_angle) * i / num_points
            x = self.center_x + inner_radius * math.cos(angle)
            y = self.center_y + inner_radius * math.sin(angle)
            points.append((x, y))

        # Draw the curved background senza bordatura
        if len(points) > 3:
            draw.polygon(points, fill=(245, 245, 220, 200), outline=None)

    def _load_user_image(
        self, image_path: str, size: Tuple[int, int] = (30, 30)
    ) -> Optional[Image.Image]:
        """Load and resize user image from Home Assistant entity_picture or local path."""
        if not image_path:
            return self._create_default_user_image(size)

        try:
            # Log attempt to load image
            _LOGGER.debug(f"Attempting to load user image: {image_path}")

            if image_path.startswith('http'):
                # Download image from URL
                _LOGGER.debug(f"Loading image from URL: {image_path}")
                response = requests.get(image_path, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                _LOGGER.debug(f"Successfully loaded image from URL")

            elif image_path.startswith('/api/'):
                # Home Assistant API endpoint for entity_picture
                # These are served by Home Assistant's web server
                full_url = f"http://localhost:8123{image_path}"
                _LOGGER.debug(
                    f"Loading Home Assistant entity picture: {full_url}")

                # Get Home Assistant access token if available
                headers = {}
                if hasattr(self.hass, 'auth') and hasattr(
                        self.hass.auth, 'create_access_token'):
                    # This would be the proper way but might not be accessible
                    # For now, try without authentication for local access
                    pass

                response = requests.get(full_url, headers=headers, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                _LOGGER.debug(
                    f"Successfully loaded Home Assistant entity picture")

            elif image_path.startswith('/local/'):
                # Convert /local/ paths to /config/www/ paths
                local_path = image_path.replace('/local/', '/config/www/')
                _LOGGER.debug(
                    f"Converting local path: {image_path} -> {local_path}")

                if os.path.exists(local_path):
                    img = Image.open(local_path)
                    _LOGGER.debug(
                        f"Successfully loaded local image: {local_path}")
                else:
                    _LOGGER.warning(f"Local image not found: {local_path}")
                    return self._create_default_user_image(size)

            elif image_path.startswith('/config/'):
                # Direct Home Assistant config path
                _LOGGER.debug(f"Loading from config path: {image_path}")
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    _LOGGER.debug(f"Successfully loaded config image")
                else:
                    _LOGGER.warning(f"Config image not found: {image_path}")
                    return self._create_default_user_image(size)

            elif image_path.startswith('/'):
                # Other absolute paths
                _LOGGER.debug(f"Loading from absolute path: {image_path}")
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    _LOGGER.debug(f"Successfully loaded absolute path image")
                else:
                    _LOGGER.warning(
                        f"Absolute path image not found: {image_path}")
                    return self._create_default_user_image(size)
            else:
                # Relative path
                _LOGGER.debug(f"Loading from relative path: {image_path}")
                img = Image.open(image_path)
                _LOGGER.debug(f"Successfully loaded relative path image")

            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # Resize image
            img = img.resize(size, Image.Resampling.LANCZOS)

            # Create circular mask
            mask = Image.new('L', size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, size[0], size[1]], fill=255)

            # Apply mask to make image circular
            img.putalpha(mask)

            _LOGGER.debug(f"Image processed successfully: {image_path}")
            return img

        except Exception as e:
            _LOGGER.error(f"Error loading user image {image_path}: {e}")
            return self._create_default_user_image(size)

    def _create_default_user_image(
        self, size: Tuple[int, int] = (30, 30)) -> Image.Image:
        """Create a default user image when no image is available."""
        # Create a highly visible default image with bright colors and good contrast
        img = Image.new('RGBA', size, (0, 0, 0, 0))  # Transparent background
        draw = ImageDraw.Draw(img)

        # Draw bright golden circular background with thick dark border
        border_width = max(2, size[0] // 15)
        draw.ellipse(
            [0, 0, size[0] - 1, size[1] - 1],
            fill=(255, 215, 0, 255),  # Bright gold
            outline=(139, 69, 19, 255),
            width=border_width)

        # Draw person icon with high contrast
        center_x, center_y = size[0] // 2, size[1] // 2

        # Head (larger for visibility)
        head_radius = size[0] // 5
        draw.ellipse([
            center_x - head_radius, center_y - head_radius - size[1] // 8,
            center_x + head_radius, center_y + head_radius - size[1] // 8
        ],
                     fill=(139, 69, 19, 255))  # Dark brown for contrast

        # Body (larger for visibility)
        body_width = size[0] // 3
        body_height = size[1] // 3
        draw.ellipse([
            center_x - body_width, center_y + size[1] // 10,
            center_x + body_width, center_y + body_height + size[1] // 10
        ],
                     fill=(139, 69, 19, 255))  # Dark brown for contrast

        return img

    def _get_user_info(self, entity_id: str) -> Dict:
        """Get user information from Home Assistant or config."""
        # If auto-discovery is enabled, get info from Home Assistant
        if self.config.get('auto_discover_users', True):
            person_entities = self._get_all_person_entities()
            # Apply filters here as well, to get correct info even if user is filtered out for position display
            filtered_person_entities = self._apply_user_filters(
                person_entities)
            if entity_id in filtered_person_entities:
                return filtered_person_entities[entity_id]
            # If user is not found after filtering, try to get it from manual config as a fallback
            elif entity_id in self.config.get('users', {}):
                return self.config['users'][entity_id]
            else:
                return {
                    'name': entity_id.split('.')[1].replace('_', ' ').title(),
                    'image_path': ''
                }
        else:
            # Fall back to manual configuration (this part might be handled better by config flow data)
            return self.config.get('users', {}).get(
                entity_id, {
                    'name': entity_id.split('.')[1].replace('_', ' ').title(),
                    'image_path': ''
                })

    def _calculate_hand_positions(self, user_positions: Dict[str, str],
                                  zones: List[str]) -> Dict[str, Dict]:
        """Calculate positions for zone hands with multiple users per zone."""
        zone_angles = self._calculate_zone_angles(zones)
        zone_hands = {}

        # Group users by zone
        users_by_zone = {}
        for entity_id, zone in user_positions.items():
            if zone not in users_by_zone:
                users_by_zone[zone] = []
            users_by_zone[zone].append(entity_id)

        # Create one hand per zone with all users for that zone
        for zone, users in users_by_zone.items():
            if zone not in zone_angles:
                # Add unknown zone dynamically to the angles calculation
                _LOGGER.info(f"Adding unknown zone '{zone}' to clock display")
                # Add zone to the zones list for angle calculation
                if zone not in zones:  # Avoid adding duplicates
                    zones.append(zone)
                zone_angles = self._calculate_zone_angles(zones)

                # Add zone to config for styling (use unknown zone styling)
                if zone not in self.config['zones']:
                    # Check if we have a mapping for this zone
                    zone_mapping = self.config.get('zone_mapping', {})
                    display_name = zone_mapping.get(
                        zone,
                        zone.replace('_', ' ').title())

                    self.config['zones'][zone] = {
                        'label': display_name,
                        'color': '#696969'  # Default gray for unknown zones
                    }

            angle = zone_angles.get(zone, math.radians(
                -90))  # Default to top if zone not found in angles
            hand_length = self.outer_radius - 35

            # Calculate hand tip position
            hand_x = self.center_x + (hand_length * math.cos(angle))
            hand_y = self.center_y + (hand_length * math.sin(angle))

            # Get user info for all users in this zone
            user_configs = []
            for entity_id in users:
                user_configs.append({
                    'entity_id':
                    entity_id,
                    'user_config':
                    self._get_user_info(entity_id)
                })

            zone_hands[zone] = {
                'x': hand_x,
                'y': hand_y,
                'angle': angle,
                'users': user_configs
            }

        return zone_hands

    def _draw_user_hands(self, draw: ImageDraw.Draw, image: Image.Image,
                         zone_hands: Dict[str, Dict]) -> None:
        """Draw ornamental clock hands like the original Weasley Clock."""
        style = self.config.get('clock_style', {})
        hand_color = style.get('hand_color',
                               '#2F1B14')  # Dark brown/black like original
        ornament_color = style.get('ornament_color', '#CD853F')

        for zone, hand_data in zone_hands.items():
            x, y = hand_data['x'], hand_data['y']
            angle = hand_data['angle']
            users = hand_data['users']

            # Draw ornamental clock hand like original
            self._draw_ornamental_hand(draw, angle, x, y, hand_color,
                                       ornament_color)

            # Place user images in golden ovals like the original
            if users:
                image_size = (40, 40) if len(users) > 1 else (50, 50)

                for i, user_data in enumerate(users):
                    user_config = user_data['user_config']
                    image_path = user_config.get('image_path')

                    # Load user image - let _load_user_image handle all the path logic
                    user_img = self._load_user_image(image_path,
                                                     size=image_size)

                    if user_img:
                        # Calcola la dimensione dell'immagine per il calcolo della distanza
                        img_radius = max(image_size) // 2

                        if len(users) == 1:
                            # Singolo utente - posiziona mantenendo sempre 15px di punta visibile
                            min_tip_visible = 15
                            distance_from_tip = img_radius + min_tip_visible
                            img_x = x - distance_from_tip * math.cos(angle)
                            img_y = y - distance_from_tip * math.sin(angle)
                        else:
                            # Utenti multipli - posiziona lungo la lancetta mantenendo sempre la punta visibile
                            min_tip_visible = 15
                            base_distance = img_radius + min_tip_visible + (
                                i * (img_radius * 2 + 10))

                            # Calcola la posizione lungo la linea della lancetta
                            img_x = x - base_distance * math.cos(angle)
                            img_y = y - base_distance * math.sin(angle)

                        # Center the image at calculated position
                        final_x = int(img_x - user_img.width // 2)
                        final_y = int(img_y - user_img.height // 2)

                        # Draw golden oval frame like original
                        self._draw_golden_oval_frame(draw, img_x, img_y,
                                                     image_size)

                        # Paste user image with transparency
                        image.paste(user_img, (final_x, final_y), user_img)

    def _draw_ornamental_hand(self, draw: ImageDraw.Draw, angle: float,
                              x: float, y: float, hand_color: str,
                              ornament_color: str) -> None:
        """Draw ornamental clock hand like the original Weasley Clock."""
        # Draw main hand shaft - thicker and more elegant
        shaft_width = 6
        for offset in range(-shaft_width // 2, shaft_width // 2 + 1):
            offset_x = offset * math.sin(angle)
            offset_y = -offset * math.cos(angle)
            draw.line([
                self.center_x + offset_x, self.center_y + offset_y,
                x + offset_x, y + offset_y
            ],
                      fill=hand_color,
                      width=1)

        # Draw ornamental arrowhead like original
        arrow_length = 15
        arrow_width = 8

        # Calculate ornamental arrow points
        tip_x = x
        tip_y = y

        # Arrow base points
        base_angle1 = angle + math.pi / 2
        base_angle2 = angle - math.pi / 2

        base1_x = x - arrow_length * math.cos(angle) + arrow_width * math.cos(
            base_angle1)
        base1_y = y - arrow_length * math.sin(angle) + arrow_width * math.sin(
            base_angle1)
        base2_x = x - arrow_length * math.cos(angle) + arrow_width * math.cos(
            base_angle2)
        base2_y = y - arrow_length * math.sin(angle) + arrow_width * math.sin(
            base_angle2)

        # Draw elegant arrowhead
        arrow_points = [(tip_x, tip_y), (base1_x, base1_y), (base2_x, base2_y)]
        draw.polygon(arrow_points,
                     fill=hand_color,
                     outline=ornament_color,
                     width=2)

    def _draw_golden_oval_frame(self, draw: ImageDraw.Draw, center_x: float,
                                center_y: float, image_size: tuple) -> None:
        """Draw golden oval frame for user photos like the original."""
        style = self.config.get('clock_style', {})
        oval_color = style.get('oval_color', '#F5DEB3')
        ornament_color = style.get('ornament_color', '#CD853F')

        # Calculate oval dimensions slightly larger than image
        oval_width = image_size[0] + 8
        oval_height = image_size[1] + 8

        # Draw golden oval background
        oval_x1 = center_x - oval_width / 2
        oval_y1 = center_y - oval_height / 2
        oval_x2 = center_x + oval_width / 2
        oval_y2 = center_y + oval_height / 2

        draw.ellipse([oval_x1, oval_y1, oval_x2, oval_y2],
                     fill=oval_color,
                     outline=ornament_color,
                     width=3)

    def generate_clock_image(self, output_path: Optional[str] = None) -> str:
        """Generate the complete Weasley Clock image."""
        try:
            # Get current user positions
            user_positions = self._get_user_positions()

            # Show only zones that are actually used by configured users
            used_zones = set(user_positions.values())
            all_zones = list(used_zones)

            # If no zones found, show empty clock
            if not all_zones:
                all_zones = []

            # Always use center position for full clock display
            self.center_x, self.center_y = self.width // 2, self.height // 2

            # Create image with completely transparent background (white areas will be transparent)
            image = Image.new('RGBA', (self.width, self.height),
                              (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)

            # Draw clock face
            self._draw_clock_face(image, draw, all_zones)

            # Calculate and draw zone hands with users
            zone_hands = self._calculate_hand_positions(
                user_positions, all_zones)
            self._draw_user_hands(draw, image, zone_hands)

            # Save image
            if not output_path:
                output_path = self.config.get('output_path',
                                              '/config/www/weasley_clock.png')

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Keep RGBA mode to preserve transparency - no background conversion

            # Calculate hash of the image data to detect changes
            image_bytes = BytesIO()
            image.save(image_bytes, 'PNG', quality=95)
            image_bytes.seek(0)
            image_data = image_bytes.getvalue()
            current_hash = hashlib.md5(image_data).hexdigest()

            # Check if image actually changed
            if self.last_image_hash and current_hash == self.last_image_hash:
                _LOGGER.debug(f"Image unchanged, hash: {current_hash}")
                return output_path  # Return just the path for consistency
            else:
                self.last_image_hash = current_hash
                _LOGGER.debug(f"Image changed, new hash: {current_hash}")
                # Save the new image only if it changed
                image.save(output_path, 'PNG', quality=95)
                _LOGGER.info(f"Weasley Clock image updated: {output_path}")
                return output_path  # Return just the path for consistency

        except Exception as e:
            _LOGGER.error(f"Error generating Weasley Clock image: {e}")
            raise


def generate_weasley_clock(hass, call):
    """Service call handler for generating Weasley Clock image."""
    try:
        # Configuration is now managed through the config entry, not direct service data for paths.
        # For this service call, we might not need config_path and output_path directly if the
        # generator correctly reads the config from the config entry.
        # If specific overrides are needed, they could be passed here, but the intention is to
        # use the configured values.

        # Retrieve config entry ID for the Weasley Clock integration
        config_entry_id = None
        for entry in hass.config_entries.async_entries('weasley_clock'):
            config_entry_id = entry.entry_id
            break  # Assuming only one config entry for Weasley Clock

        if not config_entry_id:
            _LOGGER.error("Weasley Clock config entry not found.")
            # Optionally, use a default if no config entry is found, or raise an error.
            # For now, we'll proceed assuming the generator can use defaults.
            generator = WeasleyClockGenerator(hass)
        else:
            # Get the config data from the config entry
            config_entry = hass.config_entries.async_get_entry(config_entry_id)
            if config_entry and config_entry.data:
                generator = WeasleyClockGenerator(hass)
                # Update the generator's config with data from the entry
                generator.config = generator._build_config_from_entry(
                    config_entry.data)
            else:
                _LOGGER.error(
                    f"Could not retrieve data for Weasley Clock config entry {config_entry_id}."
                )
                generator = WeasleyClockGenerator(
                    hass)  # Use defaults if config is missing

        # The output path is now read from the generator's config, which is populated from the config entry.
        result_path = generator.generate_clock_image()

        # Update the timestamp sensor state
        current_time = datetime.now()
        timestamp_str = current_time.isoformat()

        hass.states.async_set(
            'sensor.weasley_clock_last_changed', timestamp_str, {
                'friendly_name': 'Weasley Clock Last Changed',
                'device_class': 'timestamp',
                'icon': 'mdi:clock-time-twelve',
                'reason': 'Manual service call',
                'image_path': result_path
            })

        # Update the image path sensor
        hass.states.async_set(
            'sensor.weasley_clock_image_path', result_path, {
                'friendly_name':
                'Weasley Clock Image Path',
                'icon':
                'mdi:image',
                'web_url':
                result_path.replace('/config/www/', '/local/')
                if result_path.startswith('/config/www/') else result_path,
                'last_updated':
                timestamp_str,
                'reason':
                'Manual service call'
            })

        # Fire event to notify that image was actually updated
        hass.bus.fire(
            'weasley_clock_image_changed', {
                'image_path':
                result_path,
                'timestamp':
                timestamp_str,
                'reason':
                'Manual service call',
                'sensor_timestamp':
                'sensor.weasley_clock_last_changed',
                'sensor_path':
                'sensor.weasley_clock_image_path',
                'web_url':
                result_path.replace('/config/www/', '/local/')
                if result_path.startswith('/config/www/') else result_path
            })

        _LOGGER.info("Weasley Clock image updated via service call")

    except Exception as e:
        _LOGGER.error(f"Error in generate_weasley_clock service: {e}")
