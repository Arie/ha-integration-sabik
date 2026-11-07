import { test } from "node:test";
import assert from "node:assert/strict";

// Regression: as an extra module the card loads before Lovelace has defined
// ha-panel-lovelace, so it must wait instead of reading a missing prototype.
test("card waits for ha-panel-lovelace before defining", async () => {
  const defined = new Map();
  const waiters = [];
  globalThis.customElements = {
    get: (name) => defined.get(name),
    define: (name, ctor) => defined.set(name, ctor),
    whenDefined: (name) =>
      defined.has(name)
        ? Promise.resolve(defined.get(name))
        : new Promise((resolve) => waiters.push({ name, resolve })),
  };
  globalThis.window = { customCards: [] };

  let settled = false;
  const loading = import("../src/sabik-card.js").then(() => {
    settled = true;
  });
  await new Promise((r) => setTimeout(r, 20));

  assert.equal(settled, false, "import must be pending until Lovelace exists");
  assert.equal(defined.has("sabik-card"), false);
  assert.equal(window.customCards.length, 1, "picker entry registered up front");

  class FakeLit {}
  FakeLit.prototype.html = (strings) => strings;
  FakeLit.prototype.css = (strings) => strings;
  class FakePanel extends FakeLit {}
  defined.set("ha-panel-lovelace", FakePanel);
  for (const w of waiters) w.resolve(FakePanel);
  await loading;

  assert.ok(defined.has("sabik-card"));
  assert.equal(window.customCards.length, 1);
});
