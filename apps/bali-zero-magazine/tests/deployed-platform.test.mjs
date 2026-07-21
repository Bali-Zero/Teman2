import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const repoRoot = new URL("../../../", import.meta.url);

async function text(path) {
  return readFile(new URL(path, repoRoot), "utf8");
}

function numberAfter(source, key) {
  const match = source.match(
    new RegExp(`<key>${key}</key>\\s*<integer>(\\d+)</integer>`),
  );
  assert.ok(match, `missing integer key ${key}`);
  return Number(match[1]);
}

test("Pro LaunchAgents schedule morning after collectors and Breaking within ten minutes", async () => {
  const morning = await text(
    "infra/launchagents/com.balizero.magazine.morning.plist",
  );
  const breaking = await text(
    "infra/launchagents/com.balizero.magazine.breaking.plist",
  );
  assert.match(morning, /com\.balizero\.magazine\.morning/);
  assert.match(breaking, /com\.balizero\.magazine\.breaking/);
  assert.equal(numberAfter(morning, "Hour"), 6);
  assert.equal(numberAfter(morning, "Minute"), 15);
  assert.ok(numberAfter(breaking, "StartInterval") <= 600);
  assert.match(
    morning,
    /\/Users\/nuzantara\/nuzantara\/infra\/launchagents\/wrappers\/bali-zero-magazine-publish\.sh<\/string>\s*<string>morning/,
  );
  assert.match(
    breaking,
    /\/Users\/nuzantara\/nuzantara\/infra\/launchagents\/wrappers\/bali-zero-magazine-publish\.sh<\/string>\s*<string>breaking/,
  );
  assert.doesNotMatch(`${morning}\n${breaking}`, /\/Users\/balizero\//);
  assert.doesNotMatch(
    `${morning}\n${breaking}`,
    /<true\/>\s*<\/dict>\s*<\/plist>/,
  );
  assert.match(`${morning}\n${breaking}`, /<key>KeepAlive<\/key>\s*<false\/>/);
});

test("publisher wrapper is Pro-only, locked, timed, and payload-secret safe", async () => {
  const wrapper = await text(
    "infra/launchagents/wrappers/bali-zero-magazine-publish.sh",
  );
  assert.match(wrapper, /HOSTNAME_VALUE="\$\(hostname/);
  assert.match(wrapper, /Nuzantara/);
  assert.match(wrapper, /LOCKDIR=/);
  assert.match(wrapper, /duplicate suppressed/);
  assert.match(wrapper, /TIMEOUT_SECONDS/);
  assert.match(wrapper, /run_with_timeout/);
  assert.match(wrapper, /security find-generic-password -s bali-zero-magazine/);
  assert.match(wrapper, /MAGAZINE_PUBLISH_ENABLED/);
  assert.match(wrapper, /zantara_media\.cli\.magazine_publish/);
  assert.match(wrapper, /--required-system-id/);
  assert.match(wrapper, /intel-lake mata-garuda regulatory-watcher notebooklm/);
  assert.doesNotMatch(wrapper, /MAGAZINE_HMAC_SECRET\s*=/);
  assert.doesNotMatch(wrapper, /MAGAZINE_SIWC_BEARER_TOKEN\s*=/);
  assert.doesNotMatch(wrapper, /cat\s+"\$INPUT"|cat\s+\$INPUT/);
});

test("runbook records the deployed Sites capability proof and acceptance gates", async () => {
  const runbook = await text("docs/runbooks/bali-zero-magazine.md");
  for (const phrase of [
    "D1 binding `DB`",
    "R2 binding `MEDIA`",
    "inert probe version",
    "get_site",
    "`custom` workspace access",
    "SIWC dispatcher admission",
    "raw-body HMAC",
    "nonce replay rejection",
    "D1 rollback/CAS",
    "private R2",
    "Morning edition publication is atomic",
    "Breaking publication is atomic",
    "Role revocation takes effect",
    "Reduced-motion CSS",
  ]) {
    assert.match(
      runbook,
      new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
    );
  }
});

test("hosting declares the durable platform bindings used by the internal deployment", async () => {
  const hosting = JSON.parse(
    await text("apps/bali-zero-magazine/.openai/hosting.json"),
  );
  assert.equal(hosting.d1, "DB");
  assert.equal(hosting.r2, "MEDIA");
});

test("automation reference includes repo-canon magazine jobs without rewriting live snapshot", async () => {
  const reference = await text("docs/AUTOMATIONS_REFERENCE.md");
  assert.match(reference, /Repo-canon additions pending live snapshot/);
  assert.match(reference, /com\.balizero\.magazine\.morning/);
  assert.match(reference, /06:15 WITA/);
  assert.match(reference, /com\.balizero\.magazine\.breaking/);
  assert.match(reference, /600s/);
});
