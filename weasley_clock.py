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

        # Use dimensions from config or fallback to constants
        if config_data:
            self.width = config_data.get('clock_width', DEFAULT_CLOCK_WIDTH)
            self.height = config_data.get('clock_height', DEFAULT_CLOCK_HEIGHT)
            self.config = self._build_config_from_entry(config_data)
        else:
            self.width = DEFAULT_CLOCK_WIDTH
            self.height = DEFAULT_CLOCK_HEIGHT
            self.config = self._get_default_config()

        # Calculate center coordinates
        self.center_x = self.width // 2
        self.center_y = self.height // 2

        # Calculate radii
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
            "auto_update_enabled": True,
            "update_interval_seconds": DEFAULT_UPDATE_INTERVAL_SECONDS,
            "output_path": f'{DEFAULT_OUTPUT_PATH}.png',
            "zone_mapping": {},
            "zones": {},
            "clock_style": DEFAULT_CLOCK_STYLE,
            "selected_users": [],
            "min_font_size": MIN_FONT_SIZE,
            "max_font_size": MAX_FONT_SIZE,
            "font_reduction_factor": REDUCTION_FACTOR_FONT
        }

    def _build_config_from_entry(self, config_data: dict) -> dict:
        """Build configuration from config entry data."""
        config = {
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
            "selected_users":
            config_data.get("selected_users", []),
            "min_font_size":
            config_data.get("min_font_size", MIN_FONT_SIZE),
            "max_font_size":
            config_data.get("max_font_size", MAX_FONT_SIZE),
            "font_reduction_factor":
            config_data.get("font_reduction_factor", REDUCTION_FACTOR_FONT)
        }
        return config

    def _get_tagged_person_entities(self) -> Dict[str, Dict]:
        """Get person entities with weasleyclock tag."""
        person_entities = {}
        selected_users = self.config.get('selected_users', [])

        try:
            if hasattr(self.hass.states, 'async_all'):
                all_states = self.hass.states.async_all()
                for state in all_states:
                    entity_id = state.entity_id
                    if entity_id.startswith('person.') and entity_id in selected_users:
                        attributes = getattr(state, 'attributes', {})
                        # Check for weasleyclock tag
                        tags = attributes.get('tags', [])
                        if 'weasleyclock' in tags:
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
                                f"Found tagged person entity: {entity_id} - {person_info['name']} in {person_info['zone']}"
                            )
            else:
                for entity_id in self.hass.states.async_entity_ids('person'):
                    if entity_id in selected_users:
                        state = self.hass.states.get(entity_id)
                        if state:
                            attributes = getattr(state, 'attributes', {})
                            tags = attributes.get('tags', [])
                            if 'weasleyclock' in tags:
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
                                    f"Found tagged person entity: {entity_id} - {person_info['name']} in {person_info['zone']}"
                                )
        except Exception as e:
            _LOGGER.error(f"Error getting tagged person entities: {e}")
            return {}

        return person_entities

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
            size = (MAX_USER_IMAGE_RADIUS * 2, MAX_USER_IMAGE_RADIUS * 2)

        if not image_path:
            return self._create_default_user_image(size)

        try:
            _LOGGER.debug(f"Attempting to load user image: {image_path}")

            if image_path.startswith('http'):
                _LOGGER.debug(f"Loading image from URL: {image_path}")
                response = requests.get(image_path, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                _LOGGER.debug(f"Successfully loaded image from URL")

            elif image_path.startswith('/api/'):
                full_url = f"http://localhost:8123{image_path}"
                _LOGGER.debug(
                    f"Loading Home Assistant entity picture: {full_url}")
                response = requests.get(full_url, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
                _LOGGER.debug(
                    f"Successfully loaded Home Assistant entity picture")

            elif image_path.startswith('/local/'):
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
                _LOGGER.debug(f"Loading from config path: {image_path}")
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    _LOGGER.debug(f"Successfully loaded config image")
                else:
                    _LOGGER.warning(f"Config image not found: {image_path}")
                    return self._create_default_user_image(size)

            elif image_path.startswith('/'):
                _LOGGER.debug(f"Loading from absolute path: {image_path}")
                if os.path.exists(image_path):
                    img = Image.open(image_path)
                    _LOGGER.debug(f"Successfully loaded absolute path image")
                else:
                    _LOGGER.warning(
                        f"Absolute path image not found: {image_path}")
                    return self._create_default_user_image(size)
            else:
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

            # Apply mask
            img.putalpha(mask)

            _LOGGER.debug(f"Image processed successfully: {image_path}")
            return img

        except Exception as e:
            _LOGGER.error(f"Error loading user image {image_path}: {e}")
            return self._create_default_user_image(size)

    def _create_default_user_image(
        self, size: Tuple[int, int] = (30, 30)) -> Image.Image:
        """Create a default user image when no image is available."""
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        border_width = max(2, size[0] // 15)
        draw.ellipse(
            [0, 0, size[0] - 1, size[1] - 1],
            fill=(255, 215, 0, 255),
            outline=(139, 69, 19, 255),
            width=border_width)

        center_x, center_y = size[0] // 2, size[1] // 2

        head_radius = size[0] // 5
        draw.ellipse([
            center_x - head_radius, center_y - head_radius - size[1] // 8,
            center_x + head_radius, center_y + head_radius - size[1] // 8
        ],
                     fill=(139, 69, 19, 255))

        body_width = size[0] // 3
        body_height = size[1] // 3
        draw.ellipse([
            center_x - body_width, center_y + size[1] // 10,
            center_x + body_width, center_y + body_height + size[1] // 10
        ],
                     fill=(139, 69, 19, 255))

        return img

    def _get_user_positions(self) -> Dict[str, str]:
        """Get current positions of all tracked users."""
        positions = {}

        # Get tagged person entities
        person_entities = self._get_tagged_person_entities()
        
        for entity_id, info in person_entities.items():
            raw_zone = info['zone']
            mapped_zone = self._map_zone_name(raw_zone)
            positions[entity_id] = mapped_zone
            _LOGGER.debug(
                f"Tagged user {entity_id} is in zone: {raw_zone} -> {mapped_zone}"
            )

        return positions

    def _map_zone_name(self, ha_zone: str) -> str:
        """Map Home Assistant zone names to display names."""
        zone_mapping = self.config.get('zone_mapping', {})
        mapped_name = zone_mapping.get(ha_zone, ha_zone)

        if mapped_name == ha_zone:
            mapped_name = ha_zone.replace('_', ' ').title()

        return mapped_name

    def _calculate_zone_angles(self, zones: List[str]) -> Dict[str, float]:
        """Calculate angles for each zone segment across the full circle."""
        zone_angles = {}
        zone_count = len(zones)

        if zone_count == 0:
            return zone_angles

        if zone_count == 1:
            zone_angles[zones[0]] = math.radians(-90)
        else:
            angle_step = 360.0 / zone_count

            for i, zone in enumerate(zones):
                angle_degrees = -90 + (i * angle_step)
                zone_angles[zone] = math.radians(angle_degrees)

        return zone_angles

    def _draw_clock_face(self, img: Image.Image, draw: ImageDraw.Draw,
                         zones: List[str]) -> None:
        """Draw the wooden clock face."""
        self.image = img

        style = self.config.get('clock_style', {})
        bg_color = style.get('background_color', '#D2B48C')
        border_color = style.get('border_color', '#8B4513')
        text_color = style.get('text_color', '#654321')
        ornament_color = style.get('ornament_color', '#CD853F')

        # Draw main circle
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

        # Draw light band
        band_outer_radius = self.outer_radius - DEFAULT_BAND_OUTER_OFFSET
        band_inner_radius = self.outer_radius - DEFAULT_BAND_INNER_OFFSET

        draw.ellipse([
            self.center_x - band_outer_radius, self.center_y -
            band_outer_radius, self.center_x + band_outer_radius,
            self.center_y + band_outer_radius
        ],
                     fill=(245, 245, 220, 255),
                     outline=(101, 67, 33, 255),
                     width=2)

        draw.ellipse([
            self.center_x - band_inner_radius, self.center_y -
            band_inner_radius, self.center_x + band_inner_radius,
            self.center_y + band_inner_radius
        ],
                     fill=bg_color,
                     outline=None)

        # Draw zone labels
        zone_angles = self._calculate_zone_angles(zones)
        _LOGGER.debug(f"Drawing {len(zones)} zones: {zones}")
        
        for zone in zones:
            zone_config = self.config['zones'].get(zone, {})
            zone_label = zone_config.get('label', zone.title())

            zone_mapping = self.config.get('zone_mapping', {})
            if zone in zone_mapping:
                zone_label = zone_mapping[zone]

            if not zone_label or zone_label == zone:
                zone_label = zone.replace('_', ' ').title()

            angle_degrees = math.degrees(zone_angles.get(zone, 0))
            _LOGGER.info(f"Zone '{zone}' -> label '{zone_label}' at {angle_degrees:.1f}°")

            self._draw_zone_label(draw, zone_label, zone_angles.get(zone, 0),
                                 text_color)

        # Draw ornamental center piece
        self._draw_ornamental_center(draw, border_color, ornament_color)

    def _draw_zone_label(self, draw: ImageDraw.Draw, text: str, angle: float,
                         text_color: str) -> None:
        """Draw zone labels curved along the circle arc."""
        font_size = self._calculate_optimal_font_size(text)

        font_paths = [
            "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]

        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                _LOGGER.debug(
                    f"Successfully loaded font: {font_path} at size {font_size}"
                )
                break
            except (OSError, IOError):
                continue

        if font is None:
            font = ImageFont.load_default()
            _LOGGER.warning(f"Using system default font as fallback")

        if not text_color:
            text_color = DEFAULT_TEXT_COLOR
        outline_color = DEFAULT_TEXT_OUTLINE_COLOR

        self._draw_curved_text(draw, text, angle, font, font_size, text_color,
                              outline_color)

    def _draw_curved_text(self, draw: ImageDraw.Draw, text: str,
                         center_angle: float, font, font_size: int,
                         text_color: str, outline_color: str) -> None:
        """Draw text curved along the circle arc."""
        if not text:
            return

        label_radius = self.outer_radius - DEFAULT_LABEL_RADIUS_OFFSET
        large_font_size = font_size

        large_font = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        for font_path in font_paths:
            try:
                large_font = ImageFont.truetype(font_path, large_font_size)
                _LOGGER.info(f"Loaded bold font: {font_path}")
                break
            except (OSError, IOError):
                continue
        
        if large_font is None:
            large_font = font

        center_degrees = math.degrees(center_angle) % 360
        if center_degrees < 0:
            center_degrees += 360

        if center_degrees >= 180 or center_degrees == 0:
            display_text = text  
        else:
            display_text = text[::-1]

        total_chars = len(display_text)
        degrees_per_char = 6
        total_degrees = (total_chars - 1) * degrees_per_char

        start_angle_degrees = center_degrees - (total_degrees / 2)

        for i, char in enumerate(display_text):
            char_angle_degrees = start_angle_degrees + (i * degrees_per_char)
            char_angle_radians = math.radians(char_angle_degrees)

            char_x = self.center_x + label_radius * math.cos(
                char_angle_radians)
            char_y = self.center_y + label_radius * math.sin(
                char_angle_radians)

            bbox = draw.textbbox((0, 0), char, font=large_font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]

            text_x = char_x - char_width // 2
            text_y = char_y - char_height // 2

            outline_thickness = 2
            for dx in range(-outline_thickness, outline_thickness + 1):
                for dy in range(-outline_thickness, outline_thickness + 1):
                    if dx != 0 or dy != 0:
                        draw.text((text_x + dx, text_y + dy),
                                 char,
                                 font=large_font,
                                 fill='white')

            draw.text((text_x, text_y), char, font=large_font, fill='#1A0F0A')

    def _draw_ornamental_center(self, draw: ImageDraw.Draw, border_color: str,
                               ornament_color: str) -> None:
        """Draw ornamental center piece."""
        center_radius = DEFAULT_CENTER_RADIUS
        draw.ellipse([
            self.center_x - center_radius, self.center_y - center_radius,
            self.center_x + center_radius, self.center_y + center_radius
        ],
                     fill=border_color,
                     outline=ornament_color,
                     width=3)

        inner_radius = DEFAULT_INNER_CENTER_RADIUS
        draw.ellipse([
            self.center_x - inner_radius, self.center_y - inner_radius,
            self.center_x + inner_radius, self.center_y + inner_radius
        ],
                     fill=ornament_color,
                     outline=border_color,
                     width=2)

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

        # Create one hand per zone
        for zone, users in users_by_zone.items():
            if zone not in zone_angles:
                _LOGGER.info(f"Adding unknown zone '{zone}' to clock display")
                if zone not in zones:
                    zones.append(zone)
                zone_angles = self._calculate_zone_angles(zones)

                if zone not in self.config['zones']:
                    zone_mapping = self.config.get('zone_mapping', {})
                    original_zone = None
                    for orig_key, mapped_value in zone_mapping.items():
                        if mapped_value == zone:
                            original_zone = orig_key
                            break

                    display_name = zone.replace('_', ' ').title()

                    self.config['zones'][zone] = {
                        'label': display_name,
                        'color': '#696969'
                    }

            angle = zone_angles.get(zone, math.radians(
                -90))
            hand_length = self.outer_radius - DEFAULT_HAND_LENGTH_OFFSET

            hand_x = self.center_x + (hand_length * math.cos(angle))
            hand_y = self.center_y + (hand_length * math.sin(angle))

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
        """Draw ornamental clock hands."""
        style = self.config.get('clock_style', {})
        hand_color = style.get('hand_color', '#2F1B14')
        ornament_color = style.get('ornament_color', '#CD853F')

        for zone, hand_data in zone_hands.items():
            x, y = hand_data['x'], hand_data['y']
            angle = hand_data['angle']
            users = hand_data['users']

            self._draw_ornamental_hand(draw, angle, x, y, hand_color,
                                      ornament_color)

            if users:
                image_radius = self._calculate_user_image_radius(len(users))
                image_size = (image_radius * 2, image_radius * 2)

                for i, user_data in enumerate(users):
                    user_config = user_data['user_config']
                    image_path = user_config.get('image_path', '')
                    user_name = user_config.get('name', 'User')

                    img_radius = image_radius

                    if len(users) == 1:
                        distance_from_tip = img_radius + DEFAULT_MIN_TIP_VISIBLE
                        img_x = x - distance_from_tip * math.cos(angle)
                        img_y = y - distance_from_tip * math.sin(angle)
                    else:
                        base_distance = img_radius + DEFAULT_MIN_TIP_VISIBLE + (
                            i * (img_radius * 2 + DEFAULT_USER_SPACING))

                        img_x = x - base_distance * math.cos(angle)
                        img_y = y - base_distance * math.sin(angle)

                    self._draw_golden_oval_frame(draw, img_x, img_y,
                                                image_size)

                    user_img = self._load_user_image(image_path,
                                                    size=image_size)

                    if user_img:
                        final_x = int(img_x - user_img.width // 2)
                        final_y = int(img_y - user_img.height // 2)

                        if (final_x >= 0 and final_y >= 0
                                and final_x + user_img.width <= image.width
                                and final_y + user_img.height <= image.height):
                            image.paste(user_img, (final_x, final_y), user_img)
                            _LOGGER.debug(
                                f"Pasted user image for {user_name}"
                            )
                        else:
                            _LOGGER.warning(
                                f"User image for {user_name} would be outside bounds"
                            )
                            self._draw_user_placeholder(
                                draw, img_x, img_y, image_size, user_name)
                    else:
                        _LOGGER.debug(
                            f"No image found for {user_name}, drawing placeholder"
                        )
                        self._draw_user_placeholder(draw, img_x, img_y,
                                                   image_size, user_name)

    def _calculate_user_image_radius(self, user_count: int) -> int:
        """Calculate optimal user image radius based on number of users."""
        imageradius = int(MAX_USER_IMAGE_RADIUS *
                         (1 - (user_count - 1) * REDUCTION_FACTOR_USER))
        return imageradius if imageradius >= MIN_USER_IMAGE_RADIUS else MIN_USER_IMAGE_RADIUS

    def generate_clock_image(self,
                            output_path: Optional[str] = None,
                            force_regeneration: bool = False) -> str:
        """Generate the complete Weasley Clock image."""
        try:
            # Get user positions
            user_positions = self._get_user_positions()

            # Show only zones that are actually used
            used_zones = set(user_positions.values())
            all_zones = list(used_zones)

            if not all_zones:
                all_zones = []

            self.center_x, self.center_y = self.width // 2, self.height // 2

            # Create transparent image
            image = Image.new('RGBA', (self.width, self.height),
                             (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)

            # Draw clock face
            self._draw_clock_face(image, draw, all_zones)

            # Calculate and draw hands
            zone_hands = self._calculate_hand_positions(
                user_positions, all_zones)
            self._draw_user_hands(draw, image, zone_hands)

            # Save image
            if not output_path:
                output_path = self.config.get('output_path',
                                             '/config/www/weasley_clock.png')

            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Calculate hash
            image_bytes = BytesIO()
            image.save(image_bytes, 'PNG', quality=95)
            image_bytes.seek(0)
            image_data = image_bytes.getvalue()
            current_hash = hashlib.md5(image_data).hexdigest()

            # Check if image changed
            if not force_regeneration and self.last_image_hash and current_hash == self.last_image_hash:
                _LOGGER.debug(f"Image unchanged, hash: {current_hash}")
                return output_path
            else:
                self.last_image_hash = current_hash
                if force_regeneration:
                    _LOGGER.info(
                        f"Force regeneration requested: {output_path}"
                    )
                else:
                    _LOGGER.debug(f"Image changed, new hash: {current_hash}")
                image.save(output_path, 'PNG', quality=95)
                _LOGGER.info(f"Weasley Clock image updated: {output_path}")
                return output_path

        except Exception as e:
            _LOGGER.error(f"Error generating Weasley Clock image: {e}")
            raise

    def _draw_ornamental_hand(self, draw: ImageDraw.Draw, angle: float,
                             tip_x: float, tip_y: float, hand_color: str,
                             ornament_color: str) -> None:
        """Draw ornamental clock hand."""
        base_x = self.center_x
        base_y = self.center_y

        hand_length = math.sqrt((tip_x - base_x)**2 + (tip_y - base_y)**2)

        base_width = DEFAULT_HAND_BASE_WIDTH
        tip_width = DEFAULT_HAND_TIP_WIDTH

        perp_angle = angle + math.pi / 2

        base_left_x = base_x + (base_width / 2) * math.cos(perp_angle)
        base_left_y = base_y + (base_width / 2) * math.sin(perp_angle)
        base_right_x = base_x - (base_width / 2) * math.cos(perp_angle)
        base_right_y = base_y - (base_width / 2) * math.sin(perp_angle)

        tip_left_x = tip_x + (tip_width / 2) * math.cos(perp_angle)
        tip_left_y = tip_y + (tip_width / 2) * math.sin(perp_angle)
        tip_right_x = tip_x - (tip_width / 2) * math.cos(perp_angle)
        tip_right_y = tip_y - (tip_width / 2) * math.sin(perp_angle)

        hand_points = [
            (base_left_x, base_left_y),
            (tip_left_x, tip_left_y),
            (tip_x, tip_y),
            (tip_right_x, tip_right_y),
            (base_right_x, base_right_y)
        ]

        draw.polygon(hand_points,
                    fill=hand_color,
                    outline=ornament_color,
                    width=2)

        center_radius = DEFAULT_CENTER_RADIUS // 3
        draw.ellipse([
            base_x - center_radius, base_y - center_radius,
            base_x + center_radius, base_y + center_radius
        ],
                     fill=ornament_color,
                     outline=hand_color,
                     width=1)

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

        draw.ellipse([
            center_x - radius - frame_width, center_y - radius - frame_width,
            center_x + radius + frame_width, center_y + radius + frame_width
        ],
                     fill=None,
                     outline=DEFAULT_ORNAMENT_COLOR,
                     width=frame_width)

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
        """Draw user placeholder with initials."""
        radius = image_size[0] // 2

        draw.ellipse([
            center_x - radius, center_y - radius, center_x + radius,
            center_y + radius
        ],
                     fill=DEFAULT_ORNAMENT_COLOR,
                     outline=DEFAULT_BORDER_COLOR,
                     width=2)

        initials = ''.join(
            [word[0].upper() for word in user_name.split() if word][:2])

        font_size = max(DEFAULT_PLACEHOLDER_MIN_FONT_SIZE,
                       int(radius * DEFAULT_PLACEHOLDER_FONT_RATIO))
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                font_size)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = center_x - text_width // 2
        text_y = center_y - text_height // 2

        draw.text((text_x, text_y),
                 initials,
                 font=font,
                 fill=DEFAULT_TEXT_COLOR)

    def _calculate_optimal_font_size(self, text: str) -> int:
        """Calculate optimal font size based on text length."""
        text_length = len(text)

        max_font_size = self.config.get("max_font_size", MAX_FONT_SIZE)
        min_font_size = self.config.get("min_font_size", MIN_FONT_SIZE)
        reduction_factor = self.config.get("font_reduction_factor",
                                          REDUCTION_FACTOR_FONT)

        if text_length <= 4:
            calculated_size = max_font_size
        else:
            reduction_groups = (text_length - 1) // 4
            total_reduction = reduction_factor * reduction_groups
            calculated_size = int(max_font_size * (1 - total_reduction))

        final_size = calculated_size if calculated_size >= min_font_size else min_font_size

        _LOGGER.debug(
            f"Font size calculation for '{text}': {calculated_size} -> {final_size}"
        )

        return final_size
