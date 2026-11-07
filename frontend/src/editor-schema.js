// Pure (no DOM, no Lit) so it can be unit tested under plain node.
import { findSabikDevices } from "./resolve.js";

export function editorSchema(hass) {
  return [
    {
      name: "device_id",
      // With a single unit the card finds it by itself.
      required: findSabikDevices(hass).length > 1,
      selector: { device: { integration: "sabik" } },
    },
    {
      name: "room_temperature_entity",
      selector: { entity: { filter: { domain: "sensor", device_class: "temperature" } } },
    },
    {
      name: "room_humidity_entity",
      selector: { entity: { filter: { domain: "sensor", device_class: "humidity" } } },
    },
  ];
}

// Which room readings the card's first middle-column line shows.
export function roomReadingParts(config) {
  return {
    temperature: Boolean(config?.room_temperature_entity),
    humidity: Boolean(config?.room_humidity_entity),
  };
}
