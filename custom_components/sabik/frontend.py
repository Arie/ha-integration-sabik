"""Serve the Sabik card and load it in every dashboard."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

CARD_URL = "/sabik/sabik-card.js"
CARD_PATH = Path(__file__).parent / "frontend" / "sabik-card.js"
_REGISTERED = f"{DOMAIN}_card_registered"


async def async_register_card(hass: HomeAssistant) -> None:
    """Register the card once per HA run."""
    if hass.data.get(_REGISTERED):
        return
    hass.data[_REGISTERED] = True

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), True)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    # The version query busts the browser cache after an update.
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
