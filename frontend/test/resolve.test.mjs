import { test } from "node:test";
import assert from "node:assert/strict";
import { findSabikDevices, resolveEntities, pickDevice } from "../src/resolve.js";

function makeHass() {
  return {
    devices: { A: {}, B: {}, C: {} },
    entities: {
      "sensor.sabik_outdoor_temp_renamed": {
        entity_id: "sensor.sabik_outdoor_temp_renamed",
        device_id: "A",
        platform: "sabik",
        translation_key: "outdoor_air_temperature",
      },
      "select.fan_speed": {
        entity_id: "select.fan_speed",
        device_id: "A",
        platform: "sabik",
        translation_key: "fan_speed",
      },
      "sensor.sabik_2_outdoor_air_temperature": {
        entity_id: "sensor.sabik_2_outdoor_air_temperature",
        device_id: "B",
        platform: "sabik",
        translation_key: "outdoor_air_temperature",
      },
      "sensor.other": {
        entity_id: "sensor.other",
        device_id: "C",
        platform: "mqtt",
        translation_key: "outdoor_air_temperature",
      },
      "sensor.no_device": { entity_id: "sensor.no_device", platform: "sabik" },
    },
  };
}

test("findSabikDevices lists only devices with sabik entities", () => {
  assert.deepEqual(findSabikDevices(makeHass()).sort(), ["A", "B"]);
});

test("resolveEntities follows a renamed entity", () => {
  const map = resolveEntities(makeHass(), "A");
  assert.equal(map["sensor.outdoor_air_temperature"], "sensor.sabik_outdoor_temp_renamed");
  assert.equal(map["select.fan_speed"], "select.fan_speed");
});

test("resolveEntities never leaks another device's entities", () => {
  const hass = makeHass();
  const a = resolveEntities(hass, "A");
  const b = resolveEntities(hass, "B");
  assert.ok(!Object.values(a).includes("sensor.sabik_2_outdoor_air_temperature"));
  assert.equal(b["sensor.outdoor_air_temperature"], "sensor.sabik_2_outdoor_air_temperature");
  assert.equal(b["select.fan_speed"], undefined);
});

test("pickDevice: ambiguous without config", () => {
  assert.equal(pickDevice(makeHass(), {}), null);
});

test("pickDevice: configured id when it exists", () => {
  assert.equal(pickDevice(makeHass(), { device_id: "B" }), "B");
});

test("pickDevice: null when configured id is gone", () => {
  assert.equal(pickDevice(makeHass(), { device_id: "gone" }), null);
});

test("pickDevice: the only device when there is one", () => {
  const hass = makeHass();
  delete hass.entities["sensor.sabik_2_outdoor_air_temperature"];
  assert.equal(pickDevice(hass, {}), "A");
  assert.equal(pickDevice(hass, undefined), "A");
});
