"""Polling coordinator for the Sabik unit."""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import Any, Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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
from .registers import (
    COIL_BOOST,
    COIL_MANUAL_BYPASS,
    COIL_RESET_FILTER,
    COIL_SNOOZE,
    COIL_SUMMER_MODE,
    COIL_WORK_MODE_AUTO,
    FAN_SPEED_VALUES,
    HR_AIR_VOLUME,
    HR_CLOCK,
    READ_PLAN,
    SabikData,
    decode,
)

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

    async def _command(self, write: Callable[[], Awaitable[None]]) -> None:
        """Run writes, then refresh so the new state shows immediately."""
        try:
            await write()
        except SabikModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="communication_failed"
            ) from err
        await self.async_refresh()

    def _require_min(
        self, key: str, value: float, minimum: float
    ) -> None:
        # Same strict comparison as the bridge: equal to the minimum passes.
        if value < minimum:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={
                    "value": f"{value:.1f}",
                    "minimum": f"{minimum:.1f}",
                },
            )

    async def async_set_fan_speed(
        self, speed: Literal["low", "medium", "high", "auto", "snooze"]
    ) -> None:
        async def write() -> None:
            # Order mirrors the bridge so the unit sees the same sequence.
            if speed != "snooze":
                await self.client.async_write_coil(COIL_SNOOZE, False)
            if speed in ("low", "medium", "high"):
                await self.client.async_write_coil(COIL_WORK_MODE_AUTO, False)
            if speed == "snooze":
                await self.client.async_write_coil(COIL_SNOOZE, True)
            else:
                await self.client.async_write_register(
                    HR_AIR_VOLUME, FAN_SPEED_VALUES[speed]
                )

        await self._command(write)

    async def async_set_boost(self, on: bool) -> None:
        async def write() -> None:
            if on:
                await self.client.async_write_coil(COIL_SNOOZE, False)
            await self.client.async_write_coil(COIL_BOOST, on)

        await self._command(write)

    async def async_set_manual_bypass(self, on: bool) -> None:
        if on:
            data = self.data
            self._require_min(
                "bypass_outdoor_too_low",
                data.outdoor_air_temperature,
                data.min_outdoor_temperature_for_bypass,
            )
            self._require_min(
                "bypass_extract_too_low",
                data.extract_air_temperature,
                data.min_extract_temperature_for_bypass,
            )
            self._require_min(
                "bypass_difference_too_small",
                round(data.extract_air_temperature - data.outdoor_air_temperature, 1),
                data.min_temperature_difference_for_bypass,
            )
        await self.async_write_coil(COIL_MANUAL_BYPASS, on)

    async def async_set_summer_mode(self, on: bool) -> None:
        if on:
            self._require_min(
                "summer_outdoor_too_low",
                self.data.outdoor_air_temperature,
                self.data.min_outdoor_temperature_for_bypass,
            )
        await self.async_write_coil(COIL_SUMMER_MODE, on)

    async def async_write_coil(self, address: int, value: bool) -> None:
        await self._command(lambda: self.client.async_write_coil(address, value))

    async def async_set_register(self, address: int, value: int) -> None:
        await self._command(lambda: self.client.async_write_register(address, value))

    async def async_reset_filter_alarm(self) -> None:
        await self.async_write_coil(COIL_RESET_FILTER, True)

    async def async_sync_clock(self, now: datetime) -> None:
        async def write() -> None:
            # Six single-register writes: the unit never answers a multi-register
            # write, and its late reply corrupts the next read.
            fields = (now.day, now.month, now.year, now.hour, now.minute, now.second)
            for offset, value in enumerate(fields):
                await self.client.async_write_register(HR_CLOCK + offset, value)

        await self._command(write)
