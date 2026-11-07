import { test } from "node:test";
import assert from "node:assert/strict";
import { temperatureDifference } from "../src/resolve.js";

// 16.4 - 11.4 is 4.999... in floating point; the integration rounds to 0.1
// before comparing, so the card must too or it blocks a bypass HA allows.
test("bypass temperature difference is rounded to one decimal", () => {
  assert.equal(temperatureDifference(16.4, 11.4), 5);
  assert.ok(!(temperatureDifference(16.4, 11.4) < 5));
  assert.equal(temperatureDifference(21.5, -0.5), 22);
  assert.equal(temperatureDifference(18.04, 15), 3);
  assert.ok(Number.isNaN(temperatureDifference(NaN, 10)));
});
