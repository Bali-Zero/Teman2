"""Immutable MediaManifest contract from frozen CONTRACTS.md section 10.

``MediaManifest`` is the "reproducible, rights-aware manifest for WR2, WR3,
and other media." Unlike every other kind in this slice, section 10's wire
shape carries no ``media_manifest_family_id``, ``revision``,
``supersedes_media_manifest_ref``, or ``recorded_at`` field -- confirmed
against ``primitives.V1_RESERVED_EXTENSION_FIELD_NAMES`` (frozen section 3
vocabulary), which lists ``media_manifest_id`` but no
``media_manifest_family_id``/``supersedes_media_manifest_ref`` sibling the
way it lists both halves for every other successor-chained kind. A
``MediaManifest`` is scoped to one exact ``content_object_ref`` (which
already bakes in the referenced revision); a new content revision or a
receipt-bearing derivative is a brand-new manifest, not a chained
successor of this one. Transcribed as-is -- no family/revision fields are
invented here.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.models.content_object import ClaimRef, ContentLineage, ContentObjectRef
from research_os.primitives import (
    Classification,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)

MediaType = Literal["carousel", "video", "image", "audio"]


class MediaAsset(FrozenCoreModel):
    """``assets: [{asset_id, sha256, risk_class, sensitivity, source,
    derivation, rights, rights_expires_at?, prompt_ref?, model?, seed?,
    tool_version?}]``.

    Section 10: "Every asset entry binds immutable asset identity/content
    hash and both classification axes" (``asset_id``/``sha256``/
    ``risk_class``/``sensitivity`` mandatory) and "Every hero or clip
    declares source, derivation, and rights status" (``source``/
    ``derivation``/``rights`` also mandatory, matching the absence of a
    ``?`` on all six in section 10's wire shape).

    INTERPRETATION: ``rights`` has no entry in section 3's closed enum
    registry -- the identical gap the sibling operator-decision lane found
    for ``CreativeLock.reference_assets[].rights_state`` (also unlisted in
    section 3), which it resolved as an open ``RegisteredName`` rather
    than fabricate a closed set the freeze never wrote down. Mirrored
    here. ``source``/``derivation`` are given as bare keys with no
    enumerated values or nested shape at all, so they are modeled as
    free-form non-empty strings.
    """

    asset_id: str = Field(min_length=1)
    sha256: Sha256Hex
    risk_class: RiskClass
    sensitivity: Sensitivity
    source: str = Field(min_length=1)
    derivation: str = Field(min_length=1)
    rights: RegisteredName
    rights_expires_at: UtcDateTime | None = None
    prompt_ref: str | None = None
    model: str | None = None
    seed: int | None = None
    tool_version: str | None = None


class TimelineOrSlidesRef(FrozenCoreModel):
    """``timeline_or_slides: durable structured reference with sha256``.

    INTERPRETATION: the prose gives no key names at all (unlike almost
    every other field in this contract family, which spells out
    ``{a, b, c}``). Modeled minimally as ``{locator, sha256}``, reusing
    ``Evidence.source_span``'s ``locator`` idiom (section 5) for "durable
    structured reference" and adding the one key the prose explicitly
    names. Not presented as spec-derived.
    """

    locator: str = Field(min_length=1)
    sha256: Sha256Hex


class QualityCheck(FrozenCoreModel):
    """One ``quality.checks[]`` entry -- section 10 gives ``checks: []`` bare,
    with no inner key names at all (see ``Quality`` below). ``extra="allow"``
    deliberately overrides ``FrozenCoreModel``'s own ``extra="forbid"`` (the
    one open-vocabulary override in this module) rather than falling back to
    a bare ``dict[str, Any]`` element: a plain dict's own entries stay
    mutable after the outer tuple/model validates, so a live ``Quality``
    could be mutated post-validation while still reporting its original,
    now-stale ``object_hash`` -- contradicting section 2's "``object_hash``
    always means the hash of the complete canonical object" and Rule 4.
    Making each entry its own ``FrozenCoreModel`` subclass gives it the same
    ``frozen=True`` protection every other object in this package already
    gets (pydantic's per-model ``ConfigDict`` merge -- verified: a child's
    partial ``ConfigDict`` updates the parent's key-by-key, so ``frozen=True``
    survives here without being re-stated), closing the gap with the
    package's existing idiom instead of inventing a bespoke immutable-dict
    type.
    """

    model_config = ConfigDict(extra="allow")


class Quality(FrozenCoreModel):
    """``quality: {checks: [], critic_target_hash: sha256?}``.

    INTERPRETATION: ``checks`` is bare ``[]`` with no inner key names at
    all -- the same shape the sibling operator-decision lane found for
    ``DecisionPacket.alternatives``/``downstream_candidates`` (section 7),
    which it modeled as free-form JSON objects rather than invent a
    structure. Mirrored here (as ``QualityCheck``, not a bare dict -- see
    its docstring) rather than reinvented.
    """

    checks: tuple[QualityCheck, ...]
    critic_target_hash: Sha256Hex | None = None


class PlatformSpec(FrozenCoreModel):
    """``platform_specs: [{platform, aspect_ratio, safe_zone,
    duration_or_count}]``.

    INTERPRETATION: ``platform`` names a target channel the same way
    ``CreativeLock.channel_intent[].surface`` (section 8.2) does, so it is
    typed ``Identifier`` by the same reasoning. ``aspect_ratio``/
    ``safe_zone`` are bare keys with no enumerated values, modeled as
    free-form non-empty strings. ``duration_or_count``'s compound name
    literally signals either a duration (seconds) or a count (item
    number) with no unit given for either -- modeled as ``int | float``
    rather than pick one meaning the freeze does not commit to.
    """

    platform: Identifier
    aspect_ratio: str = Field(min_length=1)
    safe_zone: str = Field(min_length=1)
    duration_or_count: int | float


class AudioMetadata(FrozenCoreModel):
    """``audio?: {transcript_hash, subtitle_hash, loudness_lufs,
    sync_result}``.

    INTERPRETATION: ``sync_result`` has no entry in section 3's closed
    enum registry -- modeled as an open ``RegisteredName``, the same
    reasoning as ``MediaAsset.rights`` above.
    """

    transcript_hash: Sha256Hex
    subtitle_hash: Sha256Hex
    loudness_lufs: float
    sync_result: RegisteredName


class AssetAnchorRef(FrozenCoreModel):
    """``identity.anchor_ref`` -- section 10 gives the bare key with no
    nested shape. Modeled on the sibling operator-decision lane's
    ``CreativeLock`` ``AssetRef`` idiom (``{asset_id, content_hash}``,
    section 8.2), since an "anchor" in this domain is itself an existing
    asset.
    """

    asset_id: str = Field(min_length=1)
    content_hash: Sha256Hex


class IdentityMetadata(FrozenCoreModel):
    """``identity?: {anchor_ref, verification_result}``.

    INTERPRETATION: ``verification_result`` has no entry in section 3's
    closed enum registry -- modeled as an open ``RegisteredName``, the
    same reasoning as ``MediaAsset.rights`` and ``AudioMetadata.sync_result``.
    """

    anchor_ref: AssetAnchorRef
    verification_result: RegisteredName


class MediaManifest(FrozenCoreModel):
    media_manifest_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    content_object_ref: ContentObjectRef
    media_type: MediaType
    claim_refs: tuple[ClaimRef, ...]
    classification: Classification
    assets: tuple[MediaAsset, ...]
    timeline_or_slides: TimelineOrSlidesRef
    quality: Quality
    platform_specs: tuple[PlatformSpec, ...]
    audio: AudioMetadata | None = None
    identity: IdentityMetadata | None = None
    producer: Producer
    lineage: ContentLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_media_manifest(self) -> MediaManifest:
        # Section 10: "content_object_ref and every claim reference are
        # mandatory exact inputs; a family ID, mutable current lookup, or
        # bare revision number is invalid." Satisfied structurally --
        # ``ContentObjectRef``/``ClaimRef`` require every field of their
        # exact triple/pair, and ``FrozenCoreModel``'s ``extra="forbid"``
        # rejects a bare-revision or family-only substitute outright --
        # nothing further to check here.
        #
        # "The manifest classification is the component-wise maximum of
        # the exact ContentObject revision and every exact asset input."
        # NOT enforced: this manifest never embeds the referenced
        # ContentObject's own classification (only its id/revision/hash),
        # so the true maximum cannot be computed from this object alone.
        # Nor is "classification >= max(assets)" a safe substitute: the
        # very next sentence permits a distinct derivative to hold a
        # LOWER classification than that maximum when backed by a valid
        # SanitizationReceipt/RiskReclassificationReceipt "indexed by that
        # exact output hash" -- a receipt this manifest cannot see, since
        # "the manifest never embeds a receipt that depends on that same
        # hash" (this same section, "Manifest completeness" bullet). Any
        # in-model floor would reject exactly the legitimately-lowered
        # document this section explicitly permits. Enforcing the true
        # maximum (or the receipt-aware exception) requires a repository
        # layer that can dereference both the ContentObject and the
        # receipt ledger; it does not belong on this schema. See report.
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
