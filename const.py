"""Constants for the Weasley Clock integration."""

DOMAIN = "weasley_clock"
NAME = "Weasley Clock"
SERVICE_GENERATE_IMAGE = "generate_image"
EVENT_IMAGE_CHANGED = "weasley_clock_image_changed"

# Update intervals
DEFAULT_UPDATE_INTERVAL_SECONDS = 30
MIN_UPDATE_INTERVAL_SECONDS = 10
MAX_UPDATE_INTERVAL_SECONDS = 300

# Default paths
DEFAULT_OUTPUT_PATH = "/config/www/weasley_clock"

# Clock dimensions
DEFAULT_CLOCK_WIDTH = 448
DEFAULT_CLOCK_HEIGHT = 448
DEFAULT_OUTER_RADIUS = 180
DEFAULT_INNER_RADIUS = 40
DEFAULT_MARGIN = 40

# Image sizes
MIN_USER_IMAGE_RADIUS = 15
MAX_USER_IMAGE_RADIUS = 30
REDUCTION_FACTOR_USER = 0.1

# Font sizes
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 18
REDUCTION_FACTOR_FONT = 0.15

# Text rendering constants
DEFAULT_TEXT_TEMP_IMAGE_WIDTH = 250
DEFAULT_TEXT_TEMP_IMAGE_HEIGHT = 60
DEFAULT_LABEL_RADIUS_OFFSET = 30
DEFAULT_TEXT_OUTLINE_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1),
            (-2, -2), (-2, -1), (-2, 0), (-2, 1), (-2, 2),
            (-1, -2), (-1, 2), (0, -2), (0, 2), (1, -2), (1, 2),
            (2, -2), (2, -1), (2, 0), (2, 1), (2, 2),
            (-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]

# Clock style colors
DEFAULT_BACKGROUND_COLOR = '#D2B48C'
DEFAULT_BORDER_COLOR = '#8B4513'
DEFAULT_TEXT_COLOR = '#1A0F0A'
DEFAULT_TEXT_OUTLINE_COLOR = '#FFFFFF'
DEFAULT_HAND_COLOR = '#2F1B14'
DEFAULT_OVAL_COLOR = '#F5DEB3'
DEFAULT_ORNAMENT_COLOR = '#CD853F'

# Clock style dictionary (for backward compatibility)
DEFAULT_CLOCK_STYLE = {
    "background_color": DEFAULT_BACKGROUND_COLOR,
    "border_color": DEFAULT_BORDER_COLOR,
    "text_color": DEFAULT_TEXT_COLOR,
    "hand_color": DEFAULT_HAND_COLOR,
    "oval_color": DEFAULT_OVAL_COLOR,
    "ornament_color": DEFAULT_ORNAMENT_COLOR
}

# Hand parameters
DEFAULT_HAND_BASE_WIDTH = 8
DEFAULT_HAND_TIP_WIDTH = 3
DEFAULT_HAND_LENGTH_OFFSET = 35

# Center ornaments
DEFAULT_CENTER_RADIUS = 20
DEFAULT_INNER_CENTER_RADIUS = 12
DEFAULT_CENTER_DOT_RADIUS = 4

# Band parameters  
DEFAULT_BAND_OUTER_OFFSET = 15
DEFAULT_BAND_INNER_OFFSET = 45

# User positioning
DEFAULT_MIN_TIP_VISIBLE = 15
DEFAULT_USER_SPACING = 10

# Frame parameters
DEFAULT_FRAME_WIDTH = 3