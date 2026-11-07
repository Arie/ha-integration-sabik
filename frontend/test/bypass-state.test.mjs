import { test } from "node:test";
import assert from "node:assert/strict";
import { bypassState } from "../src/resolve.js";

test("closed bypass: a click opens it manually", () => {
  assert.deepEqual(bypassState("closed", "off", "off"), { open: false, automatic: false, turnOn: true });
});

test("manually opened bypass: a click closes it", () => {
  assert.deepEqual(bypassState("open", "on", "off"), { open: true, automatic: false, turnOn: false });
});

// Turning off a manual bypass that isn't on would do nothing; the unit owns this one.
test("bypass opened by the unit: shown as automatic, a click takes it over manually", () => {
  assert.deepEqual(bypassState("open", "off", "on"), { open: true, automatic: true, turnOn: true });
});

test("manual wins over automatic when both are on", () => {
  assert.deepEqual(bypassState("open", "on", "on"), { open: true, automatic: false, turnOn: false });
});

test("missing states count as off", () => {
  assert.deepEqual(bypassState(undefined, undefined, undefined), { open: false, automatic: false, turnOn: true });
});
