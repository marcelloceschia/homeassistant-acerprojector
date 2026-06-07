"""Constants for the Acer Projector integration."""

from typing import Final

DOMAIN: Final = "acerprojector"

CONF_MODEL: Final = "model"
CONF_CONNECTION_TYPE: Final = "connection_type"
CONF_INTERVAL: Final = "interval"
CONF_DEFAULT_INTERVAL: Final = 10

CONF_TYPE_SERIAL: Final = "serial"
CONF_TYPE_TCP: Final = "tcp"

CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUD_RATE: Final = "baud_rate"

DEFAULT_PORT: Final = 23
DEFAULT_BAUD_RATE: Final = 9600

POWERSTATUS_UNKNOWN = -1
POWERSTATUS_OFF = 0
POWERSTATUS_POWERINGON = 1
POWERSTATUS_ON = 2
POWERSTATUS_POWERINGOFF = 3
