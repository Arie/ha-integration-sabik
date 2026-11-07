import { test } from "node:test";
import assert from "node:assert/strict";
import { editorSchema } from "../src/editor-schema.js";

const hassWith = (n) => ({
  entities: Object.fromEntries(
    Array.from({ length: n }, (_, i) => [
      `sensor.s${i}`,
      { entity_id: `sensor.s${i}`, platform: "sabik", device_id: `dev${i}` },
    ])
  ),
});

const field = (schema, name) => schema.find((f) => f.name === name);

test("device_id is required only with more than one Sabik device", () => {
  assert.equal(field(editorSchema(hassWith(2)), "device_id").required, true);
  assert.equal(field(editorSchema(hassWith(1)), "device_id").required, false);
  assert.deepEqual(field(editorSchema(hassWith(1)), "device_id").selector, {
    device: { integration: "sabik" },
  });
});

test("room sensors filter on sensor domain and the right device_class", () => {
  const schema = editorSchema(hassWith(1));
  assert.deepEqual(field(schema, "room_temperature_entity").selector, {
    entity: { filter: { domain: "sensor", device_class: "temperature" } },
  });
  assert.deepEqual(field(schema, "room_humidity_entity").selector, {
    entity: { filter: { domain: "sensor", device_class: "humidity" } },
  });
});
