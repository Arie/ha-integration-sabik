"""Tests for the card registration."""

from collections.abc import Awaitable, Callable

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.sabik.const import DOMAIN

CARD_URL = "/sabik/sabik-card.js"


async def test_card_registered(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    await setup_integration()

    assert f"{CARD_URL}?v=0.1.0" in hass.data[DATA_EXTRA_MODULE_URL].urls

    client = await hass_client()
    resp = await client.get(CARD_URL)
    assert resp.status == 200
    assert 'customElements.get("sabik-card")' in await resp.text()


async def test_registered_once_with_two_entries(
    hass: HomeAssistant,
    setup_integration: Callable[[], Awaitable[MockConfigEntry]],
) -> None:
    await setup_integration()
    await setup_integration()

    urls = [u for u in hass.data[DATA_EXTRA_MODULE_URL].urls if u.startswith(CARD_URL)]
    assert urls == [f"{CARD_URL}?v=0.1.0"]
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
