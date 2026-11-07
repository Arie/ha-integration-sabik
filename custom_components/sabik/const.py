"""Constants for the Sabik integration."""

DOMAIN = "sabik"

CONF_TRANSPORT = "transport"  # "serial" | "rtu_over_tcp" | "tcp"
CONF_PORT = "port"  # serial device path
CONF_HOST = "host"
CONF_TCP_PORT = "tcp_port"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"  # "E" | "O" | "N"
CONF_SLAVE = "slave"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_BAUDRATE = 19200
DEFAULT_PARITY = "E"
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 5
DEFAULT_TCP_PORT = 502

PLATFORMS: list[str] = ["binary_sensor", "fan", "select", "sensor", "switch"]
