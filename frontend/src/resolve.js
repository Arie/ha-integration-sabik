// Pure helpers (no DOM, no Lit) so they can be unit tested under plain node.

// Entities are found by device and translation_key, never by entity_id, so
// renamed entities and a second unit both keep working.
export function findSabikDevices(hass) {
  const ids = new Set();
  for (const entity of Object.values(hass.entities || {})) {
    if (entity.platform === "sabik" && entity.device_id) {
      ids.add(entity.device_id);
    }
  }
  return [...ids];
}

export function resolveEntities(hass, deviceId) {
  const map = {};
  for (const entity of Object.values(hass.entities || {})) {
    if (
      entity.platform === "sabik" &&
      entity.device_id === deviceId &&
      entity.translation_key
    ) {
      map[`${entity.entity_id.split(".")[0]}.${entity.translation_key}`] = entity.entity_id;
    }
  }
  return map;
}

export function pickDevice(hass, config) {
  const devices = findSabikDevices(hass);
  const wanted = config && config.device_id;
  if (wanted) {
    return devices.includes(wanted) ? wanted : null;
  }
  return devices.length === 1 ? devices[0] : null;
}

// Rounded like the integration's bypass check, so 16.4 - 11.4 counts as 5.0.
export function temperatureDifference(extract, outdoor) {
  return Math.round((extract - outdoor) * 10) / 10;
}
