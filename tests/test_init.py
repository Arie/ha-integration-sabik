"""Smoke test for the integration scaffold."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.sabik.const import DOMAIN


async def test_integration_loads(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
