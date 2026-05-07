"""Constants for Advanced Presence Detection."""

from homeassistant.const import Platform

DOMAIN = "advanced_presence_detection"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]

CONF_DOOR_ENTITIES = "door_entities"
CONF_CONTROL_ACTIVE_STATES = "control_active_states"
CONF_MOTION_ENTITIES = "motion_entities"
CONF_MOTION_COOLDOWNS = "motion_cooldowns"
CONF_DEFAULT_COOLDOWN = "default_cooldown"
CONF_FRESH_WINDOW = "fresh_window"
CONF_NO_MOTION_TIMEOUT = "no_motion_timeout"
CONF_OPEN_NO_MOTION_TIMEOUT = "open_no_motion_timeout"
CONF_CONTROL_CLOSED_MODE = "control_closed_mode"

DEFAULT_NAME = "Advanced Presence Detection"
DEFAULT_COOLDOWN = 180
DEFAULT_FRESH_WINDOW = 15
DEFAULT_NO_MOTION_TIMEOUT = 3600
DEFAULT_OPEN_NO_MOTION_TIMEOUT = 0
DEFAULT_CONTROL_CLOSED_MODE = "all"

CONTROL_CLOSED_MODE_ALL = "all"
CONTROL_CLOSED_MODE_ANY = "any"
