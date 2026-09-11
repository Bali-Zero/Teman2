# ChatGPT marketing media actions v2

## Objective

Let the private Bali Zero Marketing ChatGPT app take an approved WR2 carousel
through re-render and delivery, and take a public editorial prompt through a
Flow image-to-video generation path. The bridge remains fail-closed and does
not publish to social channels.

## Contract

- `wr2_get_delivery` returns only an allowlisted Google Drive delivery URL for
  an existing human-review item.
- `wr2_request_rerender` resolves the draft UUID from the local queue, rejects
  post-publication states, requires explicit confirmation and an idempotency
  key, and invokes the existing official re-render command without `--force`.
- `wr2_rerender_status` returns the durable request state without internal
  paths or subprocess output.
- `flow_generate_video_from_prompt` composes the existing idempotent Flow image
  and video operations. A retry resumes from the stored child operations.
- `flow_operation_status` reads durable image/video operation records.
- `flow_get_media` returns readiness and an allowlisted, expiring Google media
  URL. It never returns encoded media bytes.

## Boundaries

- No arbitrary local path, Drive-file import, upload command, shell argument,
  CRM/client data, or raw OSINT is exposed.
- No Instagram, X, Facebook, email, or WhatsApp publication action is added.
- Re-render is restricted to pre-publication queue states and cannot use the
  official command's force override.
- Flow generation remains subject to the existing confirmation, daily quota,
  fixed project, fixed paygate tier, and public-input validation.
- ChatGPT Business administrators must recreate or republish the private app
  after the MCP manifest changes; the server cannot mutate that app snapshot.

## Acceptance criteria

1. The exact tool allowlist contains the six new tools and no social-publish,
   upload, arbitrary-path, CRM, document, or admin tool.
2. Unit tests exercise allowlist URL filtering, post-publication re-render
   refusal, idempotent re-render, prompt-to-video resume, media status, and
   disarmed writes without calling live Flow or the production database.
3. The production WR2 queue checksum is unchanged by the test suite.
4. Flow credits are not consumed during automated verification.
5. The existing News Room and marketing bridge suites remain green.
