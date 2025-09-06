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
DEFAULT_IMAGES_PATH = "/config/www/images"

# Clock dimensions
DEFAULT_CLOCK_WIDTH = 448
DEFAULT_CLOCK_HEIGHT = 448
DEFAULT_OUTER_RADIUS = 180
DEFAULT_INNER_RADIUS = 40

# Image sizes
DEFAULT_USER_IMAGE_RADIUS = 30
MIN_USER_IMAGE_RADIUS = 15
MAX_USER_IMAGE_RADIUS = 50

# Font sizes
DEFAULT_FONT_SIZE = 14
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 24