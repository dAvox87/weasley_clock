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
        self.width = 448
        self.height = 448
        # Center will be calculated dynamically based on zone optimization
        self.center_x = None
        self.center_y = None
        # Calculate radius based on the smaller dimension to use full available space
        min_dimension = min(self.width, self.height)
        self.outer_radius = int(
            (min_dimension - 40) // 2)  # Leave 20px margin on each side
        self.inner_radius = max(40, self.outer_radius //
                                6)  # Scale inner radius proportionally
        # Use default configuration (no file loading in event loop)
        if config_data:
            self.config = self._build_config_from_entry(config_data)
        else:
            self.config = self._get_default_config()
        self.last_image_hash = None  # Track image changes

    def _get_default_config(self):
        """Get minimal default configuration - everything else managed via config flow."""
        return {
            "auto_discover_users": True,
            "auto_update_enabled": True,
            "update_interval_seconds": 30,
            "output_path": '/config/www/weasley_clock.png',
            "zone_mapping": {},
            "zones": {},  # Empty - populated by config flow
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

            # Draw decorative zone labels on the light band
            self._draw_zone_label(draw, zone_label, zone_angles.get(zone, 0),
                                  text_color)

        # Draw ornamental center piece
        self._draw_ornamental_center(draw, border_color, ornament_color)

    def _draw_zone_label(self, draw: ImageDraw.Draw, text: str, angle: float,
                         text_color: str) -> None:
        """Draw zone labels positioned correctly."""
        # Load font
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        except:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            except:
                font = ImageFont.load_default()

        # Position labels in the light band
        label_radius = self.outer_radius - 30

        # Calculate label position
        x = self.center_x + label_radius * math.cos(angle)
        y = self.center_y + label_radius * math.sin(angle)

        # Get text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Center the text
        x -= text_width // 2
        y -= text_height // 2

        # Draw text with shadow for better readability
        draw.text((x + 1, y + 1), text, font=font, fill='black')  # Shadow
        draw.text((x, y), text, font=font, fill=text_color)

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
                    image_path = user_config.get('image_path', '')
                    user_name = user_config.get('name', 'User')

                    # Calculate position first
                    img_radius = max(image_size) // 2

                    if len(users) == 1:
                        # Single user - position maintaining always 15px of visible tip
                        min_tip_visible = 15
                        distance_from_tip = img_radius + min_tip_visible
                        img_x = x - distance_from_tip * math.cos(angle)
                        img_y = y - distance_from_tip * math.sin(angle)
                    else:
                        # Multiple users - position along hand maintaining always visible tip
                        min_tip_visible = 15
                        base_distance = img_radius + min_tip_visible + (
                            i * (img_radius * 2 + 10))

                        # Calculate position along hand line
                        img_x = x - base_distance * math.cos(angle)
                        img_y = y - base_distance * math.sin(angle)

                    # Always draw golden oval frame first
                    self._draw_golden_oval_frame(draw, img_x, img_y,
                                                 image_size)
                    self._load_user_image(
                        image_path, size=image_size) if image_path else None
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
                                f"Pasted user image for {user_name} at ({final_x}, {final_y})"
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

    def _draw_ornamental_hand(self, draw: ImageDraw.Draw, angle: float,
                              x: float, y: float, hand_color: str,
                              ornament_color: str) -> None:
        """Draw ornamental clock hand like the original Weasley Clock with clear arrow tip."""
        # Draw main hand shaft - thicker and more elegant
        shaft_width = 4
        shaft_length = math.sqrt(
            (x - self.center_x)**2 +
            (y - self.center_y)**2) - 20  # Leave space for arrow

        # Calculate shaft end point (before arrow)
        shaft_end_x = self.center_x + shaft_length * math.cos(angle)
        shaft_end_y = self.center_y + shaft_length * math.sin(angle)

        # Draw shaft as thick line
        for offset in range(-shaft_width // 2, shaft_width // 2 + 1):
            offset_x = offset * math.sin(angle)
            offset_y = -offset * math.cos(angle)
            draw.line([
                self.center_x + offset_x, self.center_y + offset_y,
                shaft_end_x + offset_x, shaft_end_y + offset_y
            ],
                      fill=hand_color,
                      width=2)

        # Draw clear, well-defined arrowhead at the tip
        arrow_length = 20

        # Calculate arrow points with clear separation
        tip_x = x
        tip_y = y

        # Arrow base points - make arrow more pronounced
        base_angle1 = angle + (2 * math.pi / 3)  # 120 degrees
        base_angle2 = angle - (2 * math.pi / 3)  # -120 degrees

        base1_x = tip_x + arrow_length * math.cos(base_angle1)
        base1_y = tip_y + arrow_length * math.sin(base_angle1)
        base2_x = tip_x + arrow_length * math.cos(base_angle2)
        base2_y = tip_y + arrow_length * math.sin(base_angle2)

        # Draw sharp, distinct arrowhead
        arrow_points = [(tip_x, tip_y), (base1_x, base1_y), (base2_x, base2_y)]
        draw.polygon(arrow_points,
                     fill=hand_color,
                     outline=ornament_color,
                     width=3)

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

    def _draw_user_placeholder(self, draw: ImageDraw.Draw, center_x: float,
                               center_y: float, image_size: tuple,
                               user_name: str) -> None:
        """Draw a placeholder with user initials when no image is available."""
        # Create initials from user name
        initials = ''.join(
            [word[0].upper() for word in user_name.split()[:2] if word])
        if not initials:
            initials = 'U'  # Fallback to 'U' for User

        # Load font for initials
        try:
            font_size = image_size[0] // 3  # Scale font to image size
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                font_size)
        except:
            try:
                font_size = image_size[0] // 3
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    font_size)
            except:
                font = ImageFont.load_default()

        # Calculate text position to center it
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = center_x - text_width // 2
        text_y = center_y - text_height // 2

        # Draw background circle for initials (slightly smaller than oval)
        circle_radius = min(image_size) // 2 - 2
        circle_x1 = center_x - circle_radius
        circle_y1 = center_y - circle_radius
        circle_x2 = center_x + circle_radius
        circle_y2 = center_y + circle_radius

        # Draw circle with user-friendly color
        draw.ellipse([circle_x1, circle_y1, circle_x2, circle_y2],
                     fill='#87CEEB',
                     outline='#4682B4',
                     width=2)

        # Draw initials
        draw.text((text_x, text_y), initials, font=font, fill='#2F4F4F')

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


def generate_weasley_clock(hass, call):
    """Service call handler for generating Weasley Clock image."""
    try:
        # Get the first Weasley Clock config entry
        config_entry = None
        for entry in hass.config_entries.async_entries('weasley_clock'):
            config_entry = entry
            break

        if not config_entry:
            _LOGGER.error("Weasley Clock config entry not found.")
            return

        # Create generator with config entry data
        generator = WeasleyClockGenerator(hass, config_entry.data)
        result_path = generator.generate_clock_image(force_regeneration=True)

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
