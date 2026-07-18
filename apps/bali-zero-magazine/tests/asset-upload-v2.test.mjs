import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { parseAssetUploadMetadata } from "../lib/contracts/collector.ts";
import { canonicalizeImageAsset } from "../lib/server/media.ts";
import { sha256Hex } from "../lib/server/security.ts";
import {
  ACTIVE_JPEG_APP,
  ACTIVE_PNG_TEXT,
  JPEG_WITH_C2PA,
  JPEG_WITH_ICC,
  JPEG_WITH_XMP,
  MALFORMED_JPEG,
  MALFORMED_PNG,
  PNG_WITH_CABX,
  PNG_WITH_ICCP,
  PNG_WITH_ZTXT,
  validAssetMetadataV2,
} from "./helpers/task-5-fixtures.mjs";

test("AssetUploadV2 binds source bytes while v1 is explicitly unsupported", async () => {
  const v2 = await validAssetMetadataV2();
  assert.deepEqual(parseAssetUploadMetadata(v2), v2);
  assert.throws(
    () => parseAssetUploadMetadata({ schema_version: "asset-upload.v1" }),
    /unsupported schema_version asset-upload\.v1/,
  );
});

test("Task 6 Python publisher fixture matches the closed AssetUploadV2 contract", async () => {
  const fixture = JSON.parse(
    await readFile(
      new URL("./fixtures/asset-upload-v2.json", import.meta.url),
      "utf8",
    ),
  );
  assert.deepEqual(parseAssetUploadMetadata(fixture), fixture);
});

test("representative JPEG and PNG metadata is accepted and canonicalized to deterministic PNG", async () => {
  const fixtures = [
    ["image/jpeg", JPEG_WITH_XMP],
    ["image/jpeg", JPEG_WITH_ICC],
    ["image/jpeg", JPEG_WITH_C2PA],
    ["image/png", PNG_WITH_ZTXT],
    ["image/png", PNG_WITH_ICCP],
    ["image/png", PNG_WITH_CABX],
  ];
  for (const [index, [mime, bytes]] of fixtures.entries()) {
    const metadata = await validAssetMetadataV2(
      {
        asset_id: `asset-corpus-${index}`,
        source_mime_type: mime,
      },
      bytes,
    );
    const first = await canonicalizeImageAsset(bytes, mime, metadata);
    const second = await canonicalizeImageAsset(bytes, mime, metadata);
    assert.equal(first.mimeType, "image/png");
    assert.equal(first.sha256, second.sha256);
    assert.deepEqual(first.bytes, second.bytes);
    assert.equal(first.sha256, await sha256Hex(first.bytes));
  }
});

test("active metadata never survives canonical bytes", async () => {
  for (const [mime, bytes] of [
    ["image/jpeg", ACTIVE_JPEG_APP],
    ["image/png", ACTIVE_PNG_TEXT],
  ]) {
    const metadata = await validAssetMetadataV2(
      { source_mime_type: mime },
      bytes,
    );
    const canonical = await canonicalizeImageAsset(bytes, mime, metadata);
    assert.equal(
      new TextDecoder()
        .decode(canonical.bytes)
        .toLowerCase()
        .includes("<script>"),
      false,
    );
  }
});

test("malformed compressed payloads remain rejected", async () => {
  for (const [mime, bytes] of [
    ["image/jpeg", MALFORMED_JPEG],
    ["image/png", MALFORMED_PNG],
  ]) {
    const metadata = await validAssetMetadataV2(
      { source_mime_type: mime },
      bytes,
    );
    await assert.rejects(
      canonicalizeImageAsset(bytes, mime, metadata),
      /not decodable|invalid|truncated/,
    );
  }
});
