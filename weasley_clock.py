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
from datetime import datetime

from homeassistant.core import HomeAssistant
from .const import (
    DEFAULT_CLOCK_WIDTH, DEFAULT_CLOCK_HEIGHT, DEFAULT_OUTER_RADIUS,
    DEFAULT_INNER_RADIUS, MIN_USER_IMAGE_RADIUS, MAX_USER_IMAGE_RADIUS,
    DEFAULT_UPDATE_INTERVAL_SECONDS, DEFAULT_OUTPUT_PATH, MIN_FONT_SIZE,
    MAX_FONT_SIZE, DEFAULT_TEXT_COLOR, DEFAULT_TEXT_OUTLINE_COLOR,
    DEFAULT_LABEL_RADIUS_OFFSET, DEFAULT_CLOCK_STYLE, DEFAULT_MARGIN,
    DEFAULT_ORNAMENT_COLOR, DEFAULT_OVAL_COLOR, DEFAULT_BORDER_COLOR,
    REDUCTION_FACTOR_USER, REDUCTION_FACTOR_FONT, DEFAULT_HAND_BASE_WIDTH,
    DEFAULT_HAND_TIP_WIDTH, DEFAULT_CENTER_RADIUS, DEFAULT_INNER_CENTER_RADIUS,
    DEFAULT_CENTER_DOT_RADIUS, DEFAULT_BAND_OUTER_OFFSET,
    DEFAULT_BAND_INNER_OFFSET, DEFAULT_MIN_TIP_VISIBLE, DEFAULT_USER_SPACING,
    DEFAULT_FRAME_WIDTH, DEFAULT_HAND_LENGTH_OFFSET,
    DEFAULT_PLACEHOLDER_MIN_FONT_SIZE, DEFAULT_PLACEHOLDER_FONT_RATIO)

_LOGGER = logging.getLogger(__name__)

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


class WeasleyClockGenerator:

    def __init__(self, hass: HomeAssistant, config_data: dict = None):
        """Initialize the Weasley Clock generator with Home Assistant instance."""
        self.hass = hass

        # Usa le dimensioni dalla configurazione o le costanti come fallback
        if config_data:
            self.width = config_data.get('clock_width', DEFAULT_CLOCK_WIDTH)
            self.height = config_data.get('clock_height', DEFAULT_CLOCK_HEIGHT)
            self.config = self._build_config_from_entry(config_data)
        else:
            self.width = DEFAULT_CLOCK_WIDTH
            self.height = DEFAULT_CLOCK_HEIGHT
            self.config = self._get_default_config()

        # Calculate center coordinates from dimensions
        self.center_x = self.width // 2
        self.center_y = self.height // 2

        # Usa costanti per il calcolo dei raggi
        min_dimension = min(self.width, self.height)
        margin = DEFAULT_MARGIN
        self.outer_radius = config_data.get(
            'outer_radius', int((min_dimension - margin) //
                                2)) if config_data else DEFAULT_OUTER_RADIUS
        self.inner_radius = config_data.get(
            'inner_radius', max(DEFAULT_INNER_RADIUS, self.outer_radius //
                                6)) if config_data else DEFAULT_INNER_RADIUS

        self.last_image_hash = None

    def _get_default_config(self):
        """Get minimal default configuration using constants."""
        return {
            "auto_discover_users": True,
            "auto_update_enabled": True,
            "update_interval_seconds": DEFAULT_UPDATE_INTERVAL_SECONDS,
            "output_path": f'{DEFAULT_OUTPUT_PATH}.png',
            "zone_mapping": {},
            "zones": {},
            "clock_style": DEFAULT_CLOCK_STYLE,
            "user_filters": {
                "excluded_users": [],
                "included_users": [],
                "exclude_local_only": False
            },
            "min_font_size": MIN_FONT_SIZE,
            "max_font_size": MAX_FONT_SIZE,
            "font_reduction_factor": REDUCTION_FACTOR_FONT
        }

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
            config_data.get("zones", {}),
            "clock_style":
            config_data.get("clock_style", DEFAULT_CLOCK_STYLE),
            "user_filters":
            config_data.get(
                "user_filters", {
                    "excluded_users": [],
                    "selected_users": [],
                    "exclude_local_only": False
                }),
            "min_font_size":
            config_data.get("min_font_size", MIN_FONT_SIZE),
            "max_font_size":
            config_data.get("max_font_size", MAX_FONT_SIZE),
            "font_reduction_factor":
            config_data.get("font_reduction_factor", REDUCTION_FACTOR_FONT)
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

    def _apply_user_filters(self, users_data: Dict[str,
                                                   Dict]) -> Dict[str, Dict]:
        """Apply user filters: show ONLY selected users, no autodiscovery extras."""
        config_filters = self.config.get('user_filters', {})

        # If no filters are present, return all users
        if not config_filters:
            return users_data

        # Get filter lists
        included_users = config_filters.get('included_users', [])
        selected_users = config_filters.get('selected_users',
                                            [])  # From config flow
        excluded_users = config_filters.get('excluded_users', [])
        exclude_local_only = config_filters.get('exclude_local_only', False)

        # Use selected_users if present (from config flow), otherwise use included_users
        target_users = selected_users if selected_users else included_users

        filtered_data = {}

        # Se ci sono utenti specificatamente selezionati, mostra SOLO quelli (nessuna autodiscovery extra)
        if target_users:
            # Modalità selezione specifica: mostra SOLO gli utenti selezionati
            for user_id in target_users:
                # Controlla anche che l'utente non sia escluso
                if user_id in users_data and user_id not in excluded_users:
                    filtered_data[user_id] = users_data[user_id]
                    _LOGGER.debug(
                        f"Added specifically selected user: {user_id}")

            _LOGGER.info(
                f"Specific selection mode: {len(target_users)} users selected, {len(filtered_data)} found"
            )
            return filtered_data  # IMPORTANTE: termina qui quando ci sono utenti selezionati
        else:
            # Modalità autodiscovery completa: includi tutti tranne quelli esclusi
            for user_id, user_info in users_data.items():
                should_include = True

                # Applica filtro exclude_local_only
                if exclude_local_only and user_info.get('zone') == 'home':
                    should_include = False

                # Non includere utenti specificatamente esclusi
                if user_id in excluded_users:
                    should_include = False
                    _LOGGER.debug(f"Excluding user: {user_id}")

                if should_include:
                    filtered_data[user_id] = user_info
                    _LOGGER.debug(f"Added discovered user: {user_id}")

            _LOGGER.info(
                f"Full autodiscovery mode: {len(users_data)} discovered, {len(excluded_users)} excluded, {len(filtered_data)} final result"
            )

        return filtered_data

    def _get_user_info(self, entity_id: str) -> Dict:
        """Get user information from Home Assistant entity."""
        try:
            state = self.hass.states.get(entity_id)
            if state:
                attributes = getattr(state, 'attributes', {})
                return {
                    'name':
                    attributes.get(
                        'friendly_name',
                        entity_id.split('.')[1].replace('_', ' ').title()),
                    'image_path':
                    attributes.get('entity_picture', ''),
                    'zone':
                    state.state
                }
            else:
                return {
                    'name': entity_id.split('.')[1].replace('_', ' ').title(),
                    'image_path': '',
                    'zone': 'unknown'
                }
        except Exception as e:
            _LOGGER.error(f"Error getting user info for {entity_id}: {e}")
            return {
                'name': entity_id.split('.')[1].replace('_', ' ').title(),
                'image_path': '',
                'zone': 'unknown'
            }

    def _load_user_image(
            self,
            image_path: str,
            size: Tuple[int, int] = None) -> Optional[Image.Image]:
        """Load and resize user image from Home Assistant entity_picture or local path."""
        if size is None:
            # Usa MAX_USER_IMAGE_RADIUS come fallback per singoli utenti
            size = (MAX_USER_IMAGE_RADIUS * 2, MAX_USER_IMAGE_RADIUS * 2)

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

    def _draw_clock_face(self, img: Image.Image, draw: ImageDraw.Draw,
                         zones: List[str]) -> None:
        """Draw the wooden clock face like the original Weasley Clock."""
        # Salva il riferimento all'immagine per il testo curvato
        self.image = img

        style = self.config.get('clock_style', {})
        bg_color = style.get('background_color', '#D2B48C')
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
        ornament_radius = self.outer_radius - DEFAULT_BAND_OUTER_OFFSET
        draw.ellipse([
            self.center_x - ornament_radius, self.center_y - ornament_radius,
            self.center_x + ornament_radius, self.center_y + ornament_radius
        ],
                     fill=None,
                     outline=ornament_color,
                     width=3)

        # Draw continuous light band around the perimeter for text readability
        band_outer_radius = self.outer_radius - DEFAULT_BAND_OUTER_OFFSET
        band_inner_radius = self.outer_radius - DEFAULT_BAND_INNER_OFFSET

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
        _LOGGER.error(f"ZONE DEBUG: Disegnando {len(zones)} zone: {zones}")  # Uso ERROR per vedere nei log
        
        for zone in zones:
            # Get the proper zone configuration
            zone_config = self.config['zones'].get(zone, {})
            zone_label = zone_config.get('label', zone.title())

            # Apply zone mapping if available
            zone_mapping = self.config.get('zone_mapping', {})
            if zone in zone_mapping:
                zone_label = zone_mapping[zone]

            # Clean up the label
            if not zone_label or zone_label == zone:
                zone_label = zone.replace('_', ' ').title()

            angle_degrees = math.degrees(zone_angles.get(zone, 0))
            _LOGGER.info(f"DEBUG: Zona '{zone}' -> label '{zone_label}' a {angle_degrees:.1f}°")

            # Draw decorative zone labels on the light band with curved text
            self._draw_zone_label(draw, zone_label, zone_angles.get(zone, 0),
                                  text_color)

        # Draw ornamental center piece
        self._draw_ornamental_center(draw, border_color, ornament_color)

    def _draw_text_along_arc(self, draw: ImageDraw.Draw, text: str,
                             center_x: float, center_y: float, radius: int,
                             start_angle: float, font: ImageFont.FreeTypeFont,
                             color: str, main_img: Image.Image) -> None:
        """Disegna il testo lungo un arco, sempre leggibile dall'esterno"""

        # Normalizza l'angolo tra 0 e 360
        angle_deg = start_angle % 360
        if angle_deg < 0:
            angle_deg += 360

        # Usa sempre un raggio fisso vicino al bordo esterno per uniformità
        # Posiziona il testo leggermente all'esterno del cerchio delle zone
        text_radius = radius + 25

        # Calcola la posizione del testo usando l'angolo corretto
        text_x = center_x + text_radius * math.cos(math.radians(angle_deg))
        text_y = center_y + text_radius * math.sin(math.radians(angle_deg))

        # Determina la rotazione del testo per essere sempre leggibile dall'esterno
        # Il testo deve essere tangente al cerchio
        if 90 <= angle_deg <= 270:  # Parte inferiore del cerchio
            # Per la metà inferiore, ruota il testo per renderlo leggibile dal basso
            text_rotation = angle_deg + 90
            # Inverti l'ordine dei caratteri per la leggibilità
            text = text[::-1]
        else:  # Parte superiore del cerchio
            # Per la metà superiore, ruota il testo normalmente
            text_rotation = angle_deg - 90

        # Crea un'immagine temporanea per il testo
        temp_img = Image.new('RGBA', (200, 50), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)

        # Disegna il testo centrato nell'immagine temporanea
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        temp_draw.text(((200 - text_width) // 2, (50 - text_height) // 2),
                       text,
                       font=font,
                       fill=color)

        # Ruota l'immagine temporanea
        rotated_temp = temp_img.rotate(-text_rotation, expand=True)

        # Incolla l'immagine ruotata centrata sulla posizione calcolata
        paste_x = int(text_x - rotated_temp.width // 2)
        paste_y = int(text_y - rotated_temp.height // 2)

        if (paste_x >= 0 and paste_y >= 0
                and paste_x + rotated_temp.width <= main_img.width
                and paste_y + rotated_temp.height <= main_img.height):
            main_img.paste(rotated_temp, (paste_x, paste_y), rotated_temp)

    def _draw_zone_label(self, draw: ImageDraw.Draw, text: str, angle: float,
                         text_color: str) -> None:
        """Draw zone labels curved along the circle arc, always readable from outside."""

        # Calcola la dimensione del font ottimale per il testo
        font_size = self._calculate_optimal_font_size(text)

        # Font migliori per schermi, in ordine di preferenza
        font_paths = [
            "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/roboto/RobotoCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
            "/usr/share/fonts/truetype/inter/Inter-Bold.ttf"
        ]

        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                _LOGGER.debug(
                    f"Successfully loaded font: {font_path} at size {font_size} for text '{text}'"
                )
                break
            except (OSError, IOError):
                continue

        if font is None:
            # Fallback con dimensione calcolata
            font = ImageFont.load_default()
            _LOGGER.warning(
                f"Using system default font as fallback for text '{text}' (calculated size: {font_size})"
            )

        # Se text_color non è fornito, usa il default
        if not text_color:
            text_color = DEFAULT_TEXT_COLOR
        outline_color = DEFAULT_TEXT_OUTLINE_COLOR

        # Disegna il testo curvato lungo l'arco
        self._draw_curved_text(draw, text, angle, font, font_size, text_color,
                               outline_color)

    def _draw_curved_text(self, draw: ImageDraw.Draw, text: str,
                          center_angle: float, font, font_size: int,
                          text_color: str, outline_color: str) -> None:
        """Draw text curved along the circle arc - SIMPLE DEGREE-BY-DEGREE POSITIONING."""

        if not text:
            return

        # Raggio fisso per le label (nella banda chiara)
        label_radius = self.outer_radius - DEFAULT_LABEL_RADIUS_OFFSET

        # USA LA DIMENSIONE CONFIGURATA DALL'UTENTE (non forzare minimo)
        large_font_size = font_size  # Rispetta sempre la configurazione utente

        # Cerca font bold/extra-bold per text più deciso
        large_font = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraBold.ttf",  # Più pesante
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 
            "/usr/share/fonts/truetype/roboto/Roboto-Black.ttf",         # Più pesante  
            "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        for font_path in font_paths:
            try:
                large_font = ImageFont.truetype(font_path, large_font_size)
                _LOGGER.info(f"Loaded bold font: {font_path} at size {large_font_size}")
                break
            except (OSError, IOError):
                continue
        
        if large_font is None:
            large_font = font
            _LOGGER.warning(f"No bold font found, using default for size {large_font_size}")

        # LOGICA COERENTE PER L'INTERA PAROLA:
        # Controlla SOLO il centro della parola per decidere orientamento
        # Dalle 9 alle 3 (270° a 90°): testo normale "Casa"
        # Dalle 3 alle 9 (90° a 270°): testo invertito "asacretneC"

        center_degrees = math.degrees(center_angle) % 360
        if center_degrees < 0:
            center_degrees += 360

        # Determina orientamento per L'INTERA parola basato solo sul centro
        # SISTEMA COORDINATE: 0°=3ore, 90°=6ore, 180°=9ore, 270°=12ore
        # Dalle 9 alle 3 = da 180° a 0° (passando per 270°=alto) - testo normale
        # Dalle 3 alle 9 = da 0° a 180° (passando per 90°=basso) - testo invertito
        
        if center_degrees >= 180 or center_degrees == 0:  # Dalle 9 alle 3 - testo normale
            display_text = text  
            _LOGGER.error(f"TESTO DEBUG '{text}' a {center_degrees:.1f}° → NORMALE '{display_text}'")
        else:  # Dalle 3 alle 9 (0° < angolo < 180°) - inverti testo
            display_text = text[::-1] 
            _LOGGER.error(f"TESTO DEBUG '{text}' a {center_degrees:.1f}° → INVERTITO '{display_text}'")

        # Calcolo semplice: gradi per lettera
        total_chars = len(display_text)
        degrees_per_char = 6  # 6 gradi tra ogni lettera
        total_degrees = (total_chars - 1) * degrees_per_char

        # Angolo di partenza: centro parola - metà span
        start_angle_degrees = center_degrees - (total_degrees / 2)

        # Posiziona ogni lettera lungo l'arco - SOLO COORDINATE X,Y
        for i, char in enumerate(display_text):
            # Angolo di questa lettera
            char_angle_degrees = start_angle_degrees + (i * degrees_per_char)
            char_angle_radians = math.radians(char_angle_degrees)

            # SOLO coordinate X,Y - NESSUNA rotazione
            char_x = self.center_x + label_radius * math.cos(
                char_angle_radians)
            char_y = self.center_y + label_radius * math.sin(
                char_angle_radians)

            # Disegna la lettera direttamente sulla posizione calcolata
            # Calcola dimensioni per centrare
            bbox = draw.textbbox((0, 0), char, font=large_font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]

            # Centra il carattere sulla posizione calcolata
            text_x = char_x - char_width // 2
            text_y = char_y - char_height // 2

            # Outline bianco SPESSO per massima visibilità e bold più deciso
            outline_thickness = 2  # Più spesso per bold deciso
            for dx in range(-outline_thickness, outline_thickness + 1):
                for dy in range(-outline_thickness, outline_thickness + 1):
                    if dx != 0 or dy != 0:
                        draw.text((text_x + dx, text_y + dy),
                                  char,
                                  font=large_font,
                                  fill='white')

            # Carattere principale
            draw.text((text_x, text_y), char, font=large_font, fill='#1A0F0A')

    def _draw_ornamental_center(self, draw: ImageDraw.Draw, border_color: str,
                                ornament_color: str) -> None:
        """Draw ornamental center piece like the original Weasley Clock."""
        # Draw main center circle
        center_radius = DEFAULT_CENTER_RADIUS
        draw.ellipse([
            self.center_x - center_radius, self.center_y - center_radius,
            self.center_x + center_radius, self.center_y + center_radius
        ],
                     fill=border_color,
                     outline=ornament_color,
                     width=3)

        # Draw smaller inner circle for detail
        inner_radius = DEFAULT_INNER_CENTER_RADIUS
        draw.ellipse([
            self.center_x - inner_radius, self.center_y - inner_radius,
            self.center_x + inner_radius, self.center_y + inner_radius
        ],
                     fill=ornament_color,
                     outline=border_color,
                     width=2)

        # Draw decorative center dot
        dot_radius = DEFAULT_CENTER_DOT_RADIUS
        draw.ellipse([
            self.center_x - dot_radius, self.center_y - dot_radius,
            self.center_x + dot_radius, self.center_y + dot_radius
        ],
                     fill=border_color,
                     outline=None)

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
                    # CORREZIONE: Usa il nome della zona mappata per la visualizzazione
                    zone_mapping = self.config.get('zone_mapping', {})

                    # Cerca il mapping inverso - trova la chiave originale che mappa a questa zona
                    original_zone = None
                    for orig_key, mapped_value in zone_mapping.items():
                        if mapped_value == zone:
                            original_zone = orig_key
                            break

                    # Se non trova mapping inverso, usa il nome della zona pulito
                    display_name = zone.replace('_', ' ').title()

                    self.config['zones'][zone] = {
                        'label': display_name,
                        'color': '#696969'  # Default gray for unknown zones
                    }

            angle = zone_angles.get(zone, math.radians(
                -90))  # Default to top if zone not found in angles
            hand_length = self.outer_radius - DEFAULT_HAND_LENGTH_OFFSET

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
        hand_color = style.get('hand_color', '#2F1B14')
        ornament_color = style.get('ornament_color', '#CD853F')

        for zone, hand_data in zone_hands.items():
            x, y = hand_data['x'], hand_data['y']
            angle = hand_data['angle']
            users = hand_data['users']

            # Draw ornamental clock hand like original
            self._draw_ornamental_hand(draw, angle, x, y, hand_color,
                                       ornament_color)

            # Place user images with dynamic sizing
            if users:
                # Calcola la dimensione dinamica delle immagini utente
                image_radius = self._calculate_user_image_radius(len(users))
                image_size = (image_radius * 2, image_radius * 2)

                for i, user_data in enumerate(users):
                    user_config = user_data['user_config']
                    image_path = user_config.get('image_path', '')
                    user_name = user_config.get('name', 'User')

                    # Calculate position first
                    img_radius = image_radius

                    if len(users) == 1:
                        # Single user - position maintaining always 15px of visible tip
                        distance_from_tip = img_radius + DEFAULT_MIN_TIP_VISIBLE
                        img_x = x - distance_from_tip * math.cos(angle)
                        img_y = y - distance_from_tip * math.sin(angle)
                    else:
                        # Multiple users - position along hand maintaining always visible tip
                        base_distance = img_radius + DEFAULT_MIN_TIP_VISIBLE + (
                            i * (img_radius * 2 + DEFAULT_USER_SPACING))

                        # Calculate position along hand line
                        img_x = x - base_distance * math.cos(angle)
                        img_y = y - base_distance * math.sin(angle)

                    # Always draw golden oval frame first
                    self._draw_golden_oval_frame(draw, img_x, img_y,
                                                 image_size)

                    # Try to load user image
                    user_img = self._load_user_image(image_path,
                                                     size=image_size)

                    if user_img:
                        # User has image - draw it
                        final_x = int(img_x - user_img.width // 2)
                        final_y = int(img_y - user_img.height // 2)

                        # Ensure coordinates are within image bounds
                        if (final_x >= 0 and final_y >= 0
                                and final_x + user_img.width <= image.width
                                and final_y + user_img.height <= image.height):
                            image.paste(user_img, (final_x, final_y), user_img)
                            _LOGGER.debug(
                                f"Pasted user image for {user_name} at ({final_x}, {final_y}) with radius {image_radius}"
                            )
                        else:
                            _LOGGER.warning(
                                f"User image for {user_name} would be outside bounds, drawing placeholder"
                            )
                            self._draw_user_placeholder(
                                draw, img_x, img_y, image_size, user_name)
                    else:
                        # No image available - draw placeholder with initials
                        _LOGGER.debug(
                            f"No image found for {user_name}, drawing placeholder"
                        )
                        self._draw_user_placeholder(draw, img_x, img_y,
                                                    image_size, user_name)

    def _calculate_user_image_radius(self, user_count: int) -> int:
        """Calculate optimal user image radius based on number of users in the same zone."""
        imageradius = int(MAX_USER_IMAGE_RADIUS *
                          (1 - (user_count - 1) * REDUCTION_FACTOR_USER))
        return imageradius if imageradius >= MIN_USER_IMAGE_RADIUS else MIN_USER_IMAGE_RADIUS

    def generate_clock_image(self,
                             output_path: Optional[str] = None,
                             force_regeneration: bool = False) -> str:
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

            # Check if image actually changed (skip if force_regeneration is True)
            if not force_regeneration and self.last_image_hash and current_hash == self.last_image_hash:
                _LOGGER.debug(f"Image unchanged, hash: {current_hash}")
                return output_path  # Return just the path for consistency
            else:
                self.last_image_hash = current_hash
                if force_regeneration:
                    _LOGGER.info(
                        f"Force regeneration requested, updating image: {output_path}"
                    )
                else:
                    _LOGGER.debug(f"Image changed, new hash: {current_hash}")
                # Save the new image (always save if force_regeneration is True)
                image.save(output_path, 'PNG', quality=95)
                _LOGGER.info(f"Weasley Clock image updated: {output_path}")
                return output_path  # Return just the path for consistency

        except Exception as e:
            _LOGGER.error(f"Error generating Weasley Clock image: {e}")
            raise

    def _draw_ornamental_hand(self, draw: ImageDraw.Draw, angle: float,
                              tip_x: float, tip_y: float, hand_color: str,
                              ornament_color: str) -> None:
        """Draw ornamental clock hand like the original Weasley Clock."""
        # Calculate hand base position (at center)
        base_x = self.center_x
        base_y = self.center_y

        # Calculate hand length
        hand_length = math.sqrt((tip_x - base_x)**2 + (tip_y - base_y)**2)

        # Hand width parameters
        base_width = DEFAULT_HAND_BASE_WIDTH
        tip_width = DEFAULT_HAND_TIP_WIDTH

        # Calculate perpendicular direction for hand width
        perp_angle = angle + math.pi / 2

        # Calculate hand outline points
        # Base points (wider)
        base_left_x = base_x + (base_width / 2) * math.cos(perp_angle)
        base_left_y = base_y + (base_width / 2) * math.sin(perp_angle)
        base_right_x = base_x - (base_width / 2) * math.cos(perp_angle)
        base_right_y = base_y - (base_width / 2) * math.sin(perp_angle)

        # Tip points (narrower)
        tip_left_x = tip_x + (tip_width / 2) * math.cos(perp_angle)
        tip_left_y = tip_y + (tip_width / 2) * math.sin(perp_angle)
        tip_right_x = tip_x - (tip_width / 2) * math.cos(perp_angle)
        tip_right_y = tip_y - (tip_width / 2) * math.sin(perp_angle)

        # Draw main hand body (tapered rectangle)
        hand_points = [
            (base_left_x, base_left_y),
            (tip_left_x, tip_left_y),
            (tip_x, tip_y),  # Pointed tip
            (tip_right_x, tip_right_y),
            (base_right_x, base_right_y)
        ]

        draw.polygon(hand_points,
                     fill=hand_color,
                     outline=ornament_color,
                     width=2)

        # Draw ornamental details
        # Center circle at base - USA COSTANTE
        center_radius = DEFAULT_CENTER_RADIUS // 3  # Proporzionale al centro principale
        draw.ellipse([
            base_x - center_radius, base_y - center_radius,
            base_x + center_radius, base_y + center_radius
        ],
                     fill=ornament_color,
                     outline=hand_color,
                     width=1)

        # Decorative line along hand center
        mid_length = hand_length * 0.7
        mid_x = base_x + mid_length * math.cos(angle)
        mid_y = base_y + mid_length * math.sin(angle)
        draw.line([(base_x, base_y), (mid_x, mid_y)],
                  fill=ornament_color,
                  width=1)

    def _draw_golden_oval_frame(self, draw: ImageDraw.Draw, center_x: float,
                                center_y: float,
                                image_size: Tuple[int, int]) -> None:
        """Draw golden oval frame around user image."""
        radius = image_size[0] // 2
        frame_width = DEFAULT_FRAME_WIDTH

        # Outer golden circle
        draw.ellipse([
            center_x - radius - frame_width, center_y - radius - frame_width,
            center_x + radius + frame_width, center_y + radius + frame_width
        ],
                     fill=None,
                     outline=DEFAULT_ORNAMENT_COLOR,
                     width=frame_width)

        # Inner highlight circle
        draw.ellipse([
            center_x - radius - 1, center_y - radius - 1,
            center_x + radius + 1, center_y + radius + 1
        ],
                     fill=None,
                     outline=DEFAULT_OVAL_COLOR,
                     width=1)

    def _draw_user_placeholder(self, draw: ImageDraw.Draw, center_x: float,
                               center_y: float, image_size: Tuple[int, int],
                               user_name: str) -> None:
        """Draw user placeholder with initials when no image is available."""
        radius = image_size[0] // 2

        # Draw background circle
        draw.ellipse([
            center_x - radius, center_y - radius, center_x + radius,
            center_y + radius
        ],
                     fill=DEFAULT_ORNAMENT_COLOR,
                     outline=DEFAULT_BORDER_COLOR,
                     width=2)

        # Draw user initials
        initials = ''.join(
            [word[0].upper() for word in user_name.split() if word][:2])

        # Calculate font size for initials
        font_size = max(DEFAULT_PLACEHOLDER_MIN_FONT_SIZE,
                        int(radius * DEFAULT_PLACEHOLDER_FONT_RATIO))
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                font_size)
        except:
            font = ImageFont.load_default()

        # Get text size
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Draw initials centered
        text_x = center_x - text_width // 2
        text_y = center_y - text_height // 2

        draw.text((text_x, text_y),
                  initials,
                  font=font,
                  fill=DEFAULT_TEXT_COLOR)

    def _calculate_optimal_font_size(self, text: str) -> int:
        """Calculate optimal font size based on text length and available space using configured values."""
        text_length = len(text)

        # Use configured values instead of hardcoded constants
        max_font_size = self.config.get("max_font_size", MAX_FONT_SIZE)
        min_font_size = self.config.get("min_font_size", MIN_FONT_SIZE)
        reduction_factor = self.config.get("font_reduction_factor",
                                           REDUCTION_FACTOR_FONT)

        if text_length <= 4:
            calculated_size = max_font_size
        else:
            # Formula: riduzione progressiva per ogni gruppo di 4 caratteri
            reduction_groups = (text_length - 1) // 4
            total_reduction = reduction_factor * reduction_groups
            calculated_size = int(max_font_size * (1 - total_reduction))

        final_size = calculated_size if calculated_size >= min_font_size else min_font_size

        # Log font size calculation for debugging if needed
        _LOGGER.debug(
            f"Font size calculation for '{text}': {calculated_size} -> {final_size}"
        )

        return final_size
