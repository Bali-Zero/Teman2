import assert from "node:assert/strict";
import test from "node:test";

import { authorize } from "../lib/server/authorization.ts";
import { requireViewer } from "../lib/server/identity.ts";

const actorKeySecret = "test-actor-key-secret-with-enough-entropy";

test("authorization defaults an authenticated workspace user to reader", async () => {
  const headers = new Headers({
    "oai-authenticated-user-email": " Reader@Example.COM ",
  });
  const viewer = await requireViewer(headers, {
    actorKeySecret,
    roleAllowlist: { version: "roles.v1", analysts: [], operators: [] },
  });
  assert.equal(viewer.role, "reader");
  assert.equal(viewer.roleConfigVersion, "roles.v1");
  assert.notEqual(viewer.actorKey, "reader@example.com");
  assert.deepEqual(Object.keys(viewer).sort(), [
    "actorKey",
    "role",
    "roleConfigVersion",
  ]);
});

test("authorization normalizes email before deriving the actor key", async () => {
  const config = {
    actorKeySecret,
    roleAllowlist: { version: "roles.v1", analysts: [], operators: [] },
  };
  const first = await requireViewer(
    new Headers({ "oai-authenticated-user-email": "Reader@Example.com" }),
    config,
  );
  const second = await requireViewer(
    new Headers({ "oai-authenticated-user-email": " reader@example.COM " }),
    config,
  );
  assert.equal(first.actorKey, second.actorKey);
  assert.match(first.actorKey, /^[a-f0-9]{64}$/);
});

test("authorization rejects missing or ambiguous platform identity", async () => {
  const config = {
    actorKeySecret,
    roleAllowlist: { version: "roles.v1", analysts: [], operators: [] },
  };
  await assert.rejects(
    () => requireViewer(new Headers(), config),
    /authenticated user/,
  );
  await assert.rejects(
    () =>
      requireViewer(
        new Headers({
          "oai-authenticated-user-email": "one@example.com,two@example.com",
        }),
        config,
      ),
    /invalid authenticated user email/,
  );
});

test("authorization applies analyst and operator membership by actor key", async () => {
  const base = await requireViewer(
    new Headers({ "oai-authenticated-user-email": "operator@example.com" }),
    {
      actorKeySecret,
      roleAllowlist: { version: "roles.v1", analysts: [], operators: [] },
    },
  );
  const operator = await requireViewer(
    new Headers({ "oai-authenticated-user-email": "operator@example.com" }),
    {
      actorKeySecret,
      roleAllowlist: {
        version: "roles.v2",
        analysts: [],
        operators: [base.actorKey],
      },
    },
  );
  assert.equal(operator.role, "operator");
  assert.equal(authorize(operator, "ops:create").allowed, true);
  assert.equal(authorize(operator, "research:create").allowed, false);
});

test("authorization revocation is effective on the next request", async () => {
  const base = await requireViewer(
    new Headers({ "oai-authenticated-user-email": "operator@example.com" }),
    {
      actorKeySecret,
      roleAllowlist: { version: "roles.v1", analysts: [], operators: [] },
    },
  );
  const operator = { ...base, role: "operator", roleConfigVersion: "roles.v1" };
  const allowlistV1 = {
    version: "roles.v1",
    analysts: [],
    operators: [base.actorKey],
  };
  const allowlistV2 = { version: "roles.v2", analysts: [], operators: [] };
  assert.equal(authorize(operator, "ops:create", allowlistV1).allowed, true);
  assert.equal(authorize(operator, "ops:create", allowlistV2).allowed, false);
});
