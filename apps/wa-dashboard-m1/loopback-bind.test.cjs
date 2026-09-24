"use strict";

// Guards the 2026-09-25 LAN containment (spec_T37 P0): the cockpit mirrors
// team WhatsApp chats unauthenticated, so it must default to loopback and
// the tracked LaunchAgent must never re-widen that bind (superscar #1,
// HOME-fork: a plist regenerated without HOST would re-expose the LAN).

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const SERVER_SRC = fs.readFileSync(path.join(__dirname, "server.cjs"), "utf8");
const PLIST_PATH = path.join(__dirname, "..", "..", "infra", "launchagents", "com.balizero.wa-dashboard-m1.plist");

function hostFromPlist(xml) {
  const m = xml.match(/<key>HOST<\/key>\s*<string>([^<]*)<\/string>/);
  return m ? m[1] : null;
}

const WILDCARD_HOSTS = new Set(["0.0.0.0", "*", "::"]);

function assertLoopbackHost(xml, label) {
  const host = hostFromPlist(xml);
  assert.ok(host, `${label}: plist must set HOST explicitly`);
  assert.ok(!WILDCARD_HOSTS.has(host), `${label}: HOST must not be a wildcard bind, got "${host}"`);
  return host;
}

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

// --- tracked plist: HOST present and pinned to loopback (innocence case) ---

assert.ok(fs.existsSync(PLIST_PATH), `tracked plist missing at ${PLIST_PATH}`);
const plistXml = fs.readFileSync(PLIST_PATH, "utf8");
const plistHost = assertLoopbackHost(plistXml, "tracked plist");
assert.equal(plistHost, "127.0.0.1", `tracked plist HOST must be loopback, got "${plistHost}"`);

// --- guilt case: the SAME checker must reject a fixture with HOST=0.0.0.0 ---

const guiltyFixture = `<plist><dict><key>EnvironmentVariables</key><dict><key>HOST</key><string>0.0.0.0</string></dict></dict></plist>`;
assert.throws(
  () => assertLoopbackHost(guiltyFixture, "guilty fixture"),
  /wildcard bind/,
  "checker must fail a fixture plist that binds HOST=0.0.0.0"
);

// --- innocence case: the SAME checker must accept a fixture with HOST=127.0.0.1 ---

const innocentFixture = `<plist><dict><key>EnvironmentVariables</key><dict><key>HOST</key><string>127.0.0.1</string></dict></dict></plist>`;
assert.equal(assertLoopbackHost(innocentFixture, "innocent fixture"), "127.0.0.1");

console.log(
  "loopback-bind.test.cjs: OK (default=127.0.0.1, plist HOST=127.0.0.1, " +
    "guilt fixture rejected, innocence fixture accepted)"
);
