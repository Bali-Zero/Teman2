"use strict";

// Guards the 2026-09-25 LAN containment (spec_T37 P0): the cockpit mirrors
// team WhatsApp chats unauthenticated, so it must default to loopback.
// (The LaunchAgent plist that also needs to pin HOST=127.0.0.1 ships in a
// later, separate PR — it needs organ genes (G1/G2/G5/G9) to track.)

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SERVER_SRC = fs.readFileSync(path.join(__dirname, "server.cjs"), "utf8");

// --- server.cjs default bind ---

const defaultAssignMatch = SERVER_SRC.match(
  /const HOST = process\.env\.HOST \|\| "([^"]*)"/
);
assert.ok(defaultAssignMatch, "server.cjs must fall back to a literal HOST default");
const defaultHost = defaultAssignMatch[1];
assert.equal(
  defaultHost,
  "127.0.0.1",
  `server.cjs default HOST must be loopback, got "${defaultHost}"`
);

// Loud warning wired for an operator who explicitly widens the bind.
assert.match(
  SERVER_SRC,
  /WARNING:.*binds the mirrored-chat cockpit/,
  "server.cjs must log a loud warning when HOST is set to a wildcard"
);

// --- guilt case: a fixture source with a wildcard default must be rejected ---

function extractDefaultHost(src) {
  const m = src.match(/const HOST = process\.env\.HOST \|\| "([^"]*)"/);
  return m ? m[1] : null;
}

const WILDCARD_HOSTS = new Set(["0.0.0.0", "*", "::"]);

const guiltyFixture = 'const HOST = process.env.HOST || "0.0.0.0";';
const guiltyHost = extractDefaultHost(guiltyFixture);
assert.ok(
  WILDCARD_HOSTS.has(guiltyHost),
  "checker sanity: the guilt fixture must itself default to a wildcard"
);
assert.notEqual(
  guiltyHost,
  "127.0.0.1",
  "checker must reject a fixture whose default HOST is a wildcard bind"
);

// --- innocence case: a fixture source with a loopback default must be accepted ---

const innocentFixture = 'const HOST = process.env.HOST || "127.0.0.1";';
assert.equal(extractDefaultHost(innocentFixture), "127.0.0.1");

console.log(
  "loopback-bind.test.cjs: OK (default=127.0.0.1, guilt fixture rejected, " +
    "innocence fixture accepted)"
);
