"""Config flow placeholder; the real flow replaces this."""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class SabikConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1
