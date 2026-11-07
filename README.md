# Sabik for Home Assistant

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Arie&repository=ha-integration-sabik&category=integration)

Native Home Assistant integration for the S&P Sabik heat recovery unit. It talks Modbus directly to the unit, needs no MQTT broker and no YAML, and ships the Sabik dashboard card.

## Install

1. In HACS, open the menu, choose **Custom repositories**, add `Arie/ha-integration-sabik` with category **Integration** (or use the badge above).
2. Download **Sabik** in HACS and restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and pick **Sabik**.

Requires Home Assistant 2026.10.4 or newer.

## Setup

Only one client can talk to the unit at a time. Stop anything else that uses the same bus or port (including the old MQTT bridge) first.

**USB / serial.** Choose **USB / serial port** and pick your adapter, preferably the stable `/dev/serial/by-id/...` path. The defaults match the unit's factory settings: 19200 baud, 8E1 (even parity), slave address 1.

**Network.** Choose **Network (host:port)** and enter the host and port of a serial-to-network gateway:

- **ser2net** next to the adapter, in raw mode. Select the protocol **Modbus RTU over TCP**. A minimal `ser2net.yaml`:

  ```yaml
  connection: &sabik
    accepter: tcp,4001
    enable: on
    options:
      kickolduser: true
    connector: serialdev,/dev/serial/by-id/YOUR-ADAPTER,19200e81,local
  ```

  Raw mode is the default for `tcp` accepters; do not use telnet or RFC2217 modes.
- **An RS485-to-WiFi/Ethernet gateway.** Use **Modbus RTU over TCP** if it passes serial bytes through transparently, or **Modbus TCP** if it converts to Modbus TCP itself.

## Entities

- **Fan:** `fan.sabik` is the main control: speed and presets. Turning it off means snooze.
- **Sensors:** air temperatures (extract, exhaust, outdoor, supply), relative humidity per air stream, fan RPM and motor voltage, bypass valve position, work mode, defrost status, selected air volume, communication error, unit clock.
- **Binary sensors:** filter alarm, fan alarms, summer mode, boost status, active alarms, temperature sensor faults.
- **Controls:** switches for boost, manual bypass, automatic bypass, summer mode, snooze and automatic work mode; a fan speed select; numbers for the bypass thresholds and manual bypass timer; buttons to reset the filter alarm and sync the unit clock.

## Card

The card needs no YAML and no Lovelace resource. It shows up as **Sabik** in the card picker, and `type: custom:sabik-card` still works in YAML dashboards. The room temperature and humidity sensors are optional; choose them in the visual editor if you want them shown.

## Migrating from the MQTT bridge

Take a backup first.

1. Stop and disable the bridge: `docker compose down` for Docker, or `systemctl --user disable --now sabik-mqtt.service` for the systemd user service.
2. Install the integration (see above) and add it with the same connection settings.
3. Open **Settings > Repairs** and run **Migrate from the Sabik MQTT bridge**. Entity IDs, history and your customisations (name, icon, area, labels, aliases, hidden or disabled, voice exposure, display precision and unit) carry over.
4. Uninstall the old **Sabik Card** from HACS.
5. In automations, replace `climate.sabik_ventilation` with `fan.sabik`.

After migration the log may show "Cannot rename statistic_id ... already in use" recorder errors. They are harmless: history stays on the old entity IDs. See the [changelog](CHANGELOG.md) for details.

## Credits

The card is based on [wichers/lovelace-comfoair](https://github.com/wichers/lovelace-comfoair). Replaces [Arie/sabik](https://github.com/Arie/sabik) and [Arie/lovelace-sabik](https://github.com/Arie/lovelace-sabik).

Released under the MIT license.
