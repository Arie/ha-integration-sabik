"""Polling coordinator for the Sabik unit."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BAUDRATE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)
from .modbus import ConnectionSettings, SabikClient, SabikModbusError
from .registers import READ_PLAN, SabikData, decode

_LOGGER = logging.getLogger(__name__)

type SabikConfigEntry = ConfigEntry[SabikCoordinator]


def settings_from_entry(data: Mapping[str, Any]) -> ConnectionSettings:
    """Build connection settings from config entry data."""
    return ConnectionSettings(
        transport=data[CONF_TRANSPORT],
        port=data.get(CONF_PORT),
        host=data.get(CONF_HOST),
        tcp_port=data.get(CONF_TCP_PORT),
        baudrate=data.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
        parity=data.get(CONF_PARITY, DEFAULT_PARITY),
        slave=data.get(CONF_SLAVE, DEFAULT_SLAVE),
    )


class SabikCoordinator(DataUpdateCoordinator[SabikData]):
    """Reads the whole register plan on every refresh."""

    config_entry: SabikConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SabikConfigEntry, client: SabikClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client

    async def _async_update_data(self) -> SabikData:
        try:
            return decode(await self.client.async_read(READ_PLAN))
        except SabikModbusError as err:
            raise UpdateFailed(str(err)) from err
