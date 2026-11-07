"""Repairs for the Sabik integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .migration import (
    MigrationResult,
    async_clear_issue,
    async_get_monitor,
    async_migrate,
)


class MigrateBridgeFlow(RepairsFlow):
    """Stop the bridge, confirm, migrate, then summarise."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id
        self._init_shown = False
        self._result: MigrationResult | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        # Repairs passes {"issue_id": ...} as input on start; only a real submit counts.
        if user_input is not None and self._init_shown:
            monitor = async_get_monitor(self.hass, self._entry_id)
            if monitor is None or not monitor.bridge_running:
                return await self.async_step_confirm()
            errors["base"] = "bridge_running"
        self._init_shown = True
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema({}), errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is None:
            return self.async_show_form(step_id="confirm", data_schema=vol.Schema({}))
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        self._result = await async_migrate(self.hass, entry)
        async_clear_issue(self.hass, self._entry_id)
        return await self.async_step_done()

    async def async_step_done(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})
        result = self._result
        assert result is not None
        skipped = "\n".join(f"- {new} → {old}" for new, old in result.skipped)
        return self.async_show_form(
            step_id="done",
            data_schema=vol.Schema({}),
            errors={}
            if result.discovery_cleared
            else {"base": "discovery_not_cleared"},
            description_placeholders={
                "renamed": str(len(result.renamed)),
                "removed": str(len(result.removed)),
                "skipped": skipped or "-",
            },
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    assert data is not None
    return MigrateBridgeFlow(data["entry_id"])
