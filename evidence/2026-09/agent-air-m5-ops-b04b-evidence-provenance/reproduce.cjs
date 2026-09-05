// Run from the repository root: node <this-file>.
const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const { createHash } = require("node:crypto");
const ts = require("typescript");
const parent = "58e8b0b027a25f8e213414577f154f16599d7ce6"; // pragma: allowlist secret - public Git commit
const child = "cd407c561304c6b0ea9b1318aa1103ba12d7c49a"; // pragma: allowlist secret - public Git commit
function initializer(ref, path) {
  const text = execFileSync("git", ["show", `${ref}:${path}`], {
    encoding: "utf8",
  });
  const source = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true);
  const values = [];
  function walk(node) {
    if (
      ts.isVariableDeclaration(node) &&
      node.name.getText(source) === "CATEGORY_SEO"
    ) {
      assert(node.initializer, "CATEGORY_SEO must have an initializer");
      values.push(node.initializer.getText(source));
    }
    ts.forEachChild(node, walk);
  }
  walk(source);
  assert.equal(values.length, 1, "exactly one CATEGORY_SEO declaration");
  return values[0];
}
const before = initializer(
  parent,
  "apps/mouth/src/app/(blog)/[category]/layout.tsx",
);
const after = initializer(child, "apps/mouth/src/lib/blog/category-seo.ts");
assert.equal(after, before, "initializer bytes must match the parent");
const sha256 = createHash("sha256").update(after, "utf8").digest("hex");
assert.equal(
  sha256,
  "899ab45308ca82e278995d395bf07919cb8bfa5537066d106b52511577ed74e4", // pragma: allowlist secret - public artifact digest
);
console.log(JSON.stringify({ initializer_byte_equal: true, sha256 }));
