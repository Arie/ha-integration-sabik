# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0]

First release: a native Home Assistant integration that replaces the MQTT
bridge and the separate Sabik Card.

### Added
- Direct Modbus connection over USB/serial, RTU over TCP (ser2net or a gateway) or Modbus TCP, set up in the UI.
- Fan, sensors, switches, selects, numbers and buttons for the unit.
- Binary sensors for automatic bypass (DI 15) and the boost contact (DI 28), which the bridge read but never published.
- Sabik card built into the integration, with an optional room temperature and humidity line.
- One-click repair, "Migrate from the Sabik MQTT bridge", that moves the old MQTT entities to the new integration, keeping their entity IDs, history and customisations (name, icon, area, labels, aliases, hidden or disabled, voice exposure, display precision and unit).

### Changed
- Voltage sensors now report volts (raw value divided by 10). Their long-term statistics jump once at the switch-over.
- Boost status: confirmed on hardware that DI 29 = 1 means boost is active, although the register documentation says the opposite. The behaviour is unchanged from the bridge.
- Fan speed shows unknown instead of falling back to "medium".
- The bypass temperature-difference threshold accepts 3.0 and 6.0.
- Switching the automatic work mode on or off also leaves snooze, as the bridge's mode command did.
- The card's bypass button follows the manual bypass switch instead of the valve position, and its tooltip shows when the unit opened the bypass itself.

### Fixed
- Clock sync works. It is written as six single-register writes, because the unit applies a multi-register write but never answers it.

### Known issues
- After migration the Home Assistant log shows "Cannot rename statistic_id ... already in use" recorder errors. This is expected and harmless: history stays on the old entity IDs.
- If the Sabik device has an area (the migration copies the old device's area), entities added by later updates get the area in their entity ID, for example `binary_sensor.zolder_sabik_automatic_bypass`. Rename them by hand if you want them to match.

[0.1.0]: https://github.com/Arie/ha-integration-sabik/releases/tag/v0.1.0
