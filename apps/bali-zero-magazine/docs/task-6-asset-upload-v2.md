# Task 6 publisher handoff: AssetUploadV2

The Python publisher must treat the uploaded file as a source artifact and the
response digest as the publication artifact. They are intentionally different.

## Required upload sequence

1. Read the source file once as raw bytes.
2. Derive `source_sha256`, `source_byte_count`, `source_mime_type`,
   `source_width`, and `source_height` from those exact bytes.
3. Build the closed `asset-upload.v2` metadata object. Use the fixture at
   `tests/fixtures/asset-upload-v2.json` as the field-level contract.
4. Serialize the metadata compactly and place it in
   `x-magazine-asset-metadata`.
5. Sign the exact request body and the exact metadata header with the existing
   machine HMAC protocol. Send the source MIME as `Content-Type`.
6. POST the source bytes to `/api/machine/assets`.
7. Require `canonical_sha256` and `canonical_mime_type` from a `201 created` or
   `200 replay` response. The canonical MIME is currently `image/png`.
8. Put `canonical_sha256`, never `source_sha256`, in the story or edition
   `asset_digests` manifest.

The Worker decodes JPEG, PNG, or WebP with Photon, discards source metadata,
and deterministically re-encodes a browser-safe PNG. It persists the source
manifest separately from the canonical byte count, dimensions, MIME, and
digest. AssetUploadV1 is unsupported.

## Replay and conflict rules

- Retry with the identical source bytes, identical AssetUploadV2 manifest, and
  the same asset identity. A fresh HMAC nonce is still required.
- An exact replay returns `200` and the same canonical digest.
- A changed source digest, byte count, MIME, dimensions, provenance field,
  canonical result, asset ID binding, or R2 key is a conflict.
- Never derive the publication digest locally and never assume it equals the
  source digest.
- Never upload a pre-existing object over a canonical key. The Worker owns
  canonical storage and rejects inconsistent existing objects without
  overwriting them.

## Python response check

```python
payload = response.json()
if response.status_code not in {200, 201}:
    raise RuntimeError("magazine asset ingress rejected the source")
if payload.get("source_sha256") != metadata["source_sha256"]:
    raise RuntimeError("magazine asset ingress returned a source mismatch")
canonical_digest = payload.get("canonical_sha256")
if not isinstance(canonical_digest, str) or len(canonical_digest) != 64:
    raise RuntimeError("magazine asset ingress omitted canonical_sha256")
if payload.get("canonical_mime_type") != "image/png":
    raise RuntimeError("magazine asset ingress returned an unsupported canonical MIME")
```

Do not log source bytes, HMAC material, or unsanitized client data. Store only
the contract fields and the canonical result needed for the next publication
request.
