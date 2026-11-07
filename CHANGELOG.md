# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0]

First release: a native Home Assistant integration that replaces the MQTT
bridge and the separate Sabik Card.

### Added
- Direct Modbus connection over USB/serial, RTU over TCP (ser2net or a gateway) or Modbus TCP, set up in the UI.
- Fan, sensors, switches, selects, numbers and buttons for the unit.
- Sabik card built into the integration, with an optional room temperature and humidity line.
- One-click repair, "Migrate from the Sabik MQTT bridge", that moves the old MQTT entities to the new integration.

### Changed
- Voltage sensors now report volts (raw value divided by 10). Their long-term statistics jump once at the switch-over.
- Boost status now shows the true state. Verified on hardware: DI 29 = 1 means boost is active (the register documentation says the opposite).
- Fan speed shows unknown instead of falling back to "medium".
- The bypass temperature-difference threshold accepts 3.0 and 6.0.

### Fixed
- Clock sync works. It is written as six single-register writes, because the unit applies a multi-register write but never answers it.

### Known issues
- After migration the Home Assistant log shows "Cannot rename statistic_id ... already in use" recorder errors. This is expected and harmless: history stays on the old entity IDs.
- Areas, labels and icons set on the old MQTT entities are not carried over.

[0.1.0]: https://github.com/Arie/ha-integration-sabik/releases/tag/v0.1.0
