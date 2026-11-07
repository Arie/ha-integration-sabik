import { test } from "node:test";
import assert from "node:assert/strict";
import { roomReadingParts } from "../src/editor-schema.js";

test("room reading parts follow the configured entities", () => {
  assert.deepEqual(
    roomReadingParts({ room_temperature_entity: "sensor.t", room_humidity_entity: "sensor.h" }),
    { temperature: true, humidity: true },
  );
  assert.deepEqual(roomReadingParts({ room_humidity_entity: "sensor.h" }), { temperature: false, humidity: true });
  assert.deepEqual(roomReadingParts({ room_temperature_entity: "sensor.t" }), { temperature: true, humidity: false });
  assert.deepEqual(roomReadingParts({}), { temperature: false, humidity: false });
});
