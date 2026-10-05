# Universal Conductor host seat maps

These manifests are static, non-secret discovery inputs. They answer only:
which opaque account seats are locally bound and visible to a selector on one
specific machine?

They do not select models. Model endpoint selection belongs to the Model
Intelligence Registry. They also do not prove authentication: every committed
`runtime_auth` value is deliberately `unverified`; authority comes from a
fresh runtime receipt for the same host and seat.

The Claude roster is exactly A1-A5+AZ. `CLAUDE_CONFIG_DIR` profiles and
headless OAuth token slots are separate surfaces and have no inferred identity
mapping. The Codex roster is per host: Pro and Mini are exactly O1/O2 (O2's canonical
and compatibility names refer to one seat); Air-M5 is O1/O2/O3, where the acct2
name is a distinct account (O3) carrying `quota_independence: unverified`.
`auto_rotation_order` is declarative only: no runtime reads it. On Air-M5 it
mirrors the order in which `scripts/lib/codex_seat.sh` enumerates its default
directory list (a test pins the two together); excluding a seat from automatic
rotation is a `CODEX_SEAT_DIRS` change on the host, not a manifest edit. A
runtime consumer of the field is owed (`FLEET_TOPOLOGY.json` `pending_arms`).

No manifest may contain a local path, email/account identity, credential,
provider output, or token value. Pro evidence never establishes Mini or Air-M5
state.
