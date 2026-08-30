# Zantara S01E13 creative-divergence and cinematic-probe design

**Date:** 2026-08-31
**Branch:** `agent/air-m5/wr3/zantara-video-factory-v3`
**Status:** operator-approved pilot; camera probes authorized; no publication or full episode production authorized

## Decision

The factory keeps a stable, resumable production grammar while making the creative answer deliberately non-repeatable.

The stable part contains stage order, contracts, identity, factual context, safety gates, manifests, and review criteria. The divergent part is a fresh `creative_seed` created for each episode. A reroll never overwrites that seed: it creates a child seed with an explicit parent and a new creative signature.

This avoids two opposite failures:

- spending high-reasoning tokens repeatedly on mechanical production decisions; and
- caching the artistic conclusion until every episode looks like the previous one.

## Pilot boundary

This design covers only Season 01 Episode 13, candidate `C07`, **What Your Residency Permit Does Not Come With**.

The operator approved:

- the topic for this pilot;
- one high-reasoning Creative Lock;
- up to 24 paid Flow/Veo camera probes across six four-variant families;
- a six-clip frontier wave first, containing one deliberately different probe per family;
- a measured ceiling of 240 Flow credits for this probe scope, derived from the first
  successful Tier1P5 charge of 10 credits and the 24-attempt hard limit.

The operator did not approve:

- the other 19 Season 01 topics;
- a legally grounded final script;
- a finished episode;
- upload, publication, deployment, or outbound messaging.

The probes contain no implementation-specific legal, regulatory, pricing, duration, or eligibility claim. Their purpose is to select a cinematic grammar before factual scripting.

## Three-plane architecture

### Plane A — immutable, cacheable context

`context-snapshot.json` freezes the selected topic, audience, narrative promise, source-artifact hashes, Zantara identity anchor, technical format, legal-scope restriction, and forbidden visual vocabulary. Its canonical SHA-256 is the context identity.

This plane may be cached and reused throughout the episode because it is evidence and constraint, not artistic conclusion.

### Plane B — fresh divergent Creative Lock

`creative-lock.json` is generated once from the immutable context and receives a fresh UUID. It fixes:

- narrative engine;
- opening image;
- spatial metaphor;
- camera grammar;
- transition grammar;
- sound motif;
- color and light arc;
- blocking logic;
- wardrobe logic;
- emotional turn;
- final image;
- forbidden prior motifs.

For this pilot the thesis is **continuity of movement, discontinuity of rights**. Zantara appears to move through one continuous architectural world, while invisible thresholds progressively alter space, light, access, and rhythm. The film moves from warm certainty, through compressed ambiguity, to neutral clarity. Camera movement decreases as the idea becomes precise.

The apparent oner is not a gimmick. Camera movement exists only while the audience shares the character's false sense of continuous access. The final static close-up breaks that assumption. This follows the cinematographic principle that movement and cutting need emotional motivation, not decorative virtuosity.

### Plane C — deterministic production expansion

After the Creative Lock, a cheap deterministic expander generates controlled variants. It does not reinterpret the episode. Each probe changes only declared axes such as focal length, camera height, occluder, blocking beat, or light boundary.

The six probe families are:

1. fluid warm approach;
2. full-frame occlusion bridge;
3. broad-to-compressed spatial transition;
4. invisible lighting threshold;
5. deep-focus two-plane information shot;
6. static direct-address myth break.

Each family defines four variants, but the factory does not render them blindly. It first
renders one probe from every family, reviews the six genuinely different camera ideas, and
opens the remaining eighteen slots only for a diagnosed ambiguity, failure, or close contest.
The cap of 24 is a convergence boundary: after four controlled variants per problem, another
generation is allowed only after a specific failure diagnosis and a child seed or revised axis.
This adaptive frontier keeps Flow spend permissive while preventing mechanical overproduction
and repeated LLM deliberation.

## Cinematic craft translated into testable rules

The probe grammar draws on current professional cinematography discussion, then reduces it to decisions Flow can execute:

- **Motivated camera:** movement follows the character's certainty and stops at the intellectual reversal. Camera activity may not exist merely to signal production value.
- **Long-take psychology:** continuity is used to place the viewer inside the mistaken mental model. Hidden stitch points are permitted only at motivated occlusions or match-on-action moments.
- **Occlusion cuts:** an architectural foreground element must cover the complete frame long enough to provide a clean edit surface.
- **Deep staging:** foreground and background carry different pieces of information without explanatory graphics. The shot must remain readable on a phone.
- **Light as narrative state:** the change from warm certainty to neutral clarity occurs inside the action, not through a decorative color-grade wipe.
- **Motion-to-stasis arc:** tracking, then compression, then a held human face. The close-up is the verdict, not filler coverage.
- **Sound bridge:** one dry architectural click or latch becomes a J/L-cut bridge. Music does not announce transitions that the image and sound can already express.
- **Negative space:** architecture and blocking imply unavailable access; there are no labelled doors, floating documents, holograms, stamps, or generated legal text.

Craft references:

- American Society of Cinematographers, _Cyrano_: camera kinetics follow performance and later give way to stasis; a long take needs an emotional reason. <https://theasc.com/articles/collaborative-process-cyrano>
- ARRI, Emmanuel Lubezki on _Birdman_: continuous movement must remain organic to the story rather than become a technical stunt. <https://www.arri.com/news-en/emmanuel-lubezki-asc-amc-on-birdman-/47554-47554>
- American Society of Cinematographers, _Children of Men_: the camera may act as a point of view that directs attention beyond plot mechanics. <https://theasc.com/articles/children-of-men-humanitys-last-hope>
- Sony Cine, focus as story: deep focus lets foreground, middle ground, and background carry simultaneous information. <https://sony-cinematography.com/articles/6-scenes-that-show-how-a-cameras-focus-tells-the-story/>
- Filmmakers Academy, audio bridges: J-cuts and L-cuts join separate images into perceived continuity. <https://www.filmmakersacademy.com/glossary/audio-bridge/>

## Originality contract

Consistency is evaluated separately from novelty.

### Invariants

- approved A007 Zantara identity;
- vertical 9:16, eight-second source clips;
- natural native audio;
- one legible action per clip;
- no visible generated text, subtitles, logos, interfaces, documents, or official insignia;
- no additional visible person or duplicate/reflected Zantara;
- no airport, passport, stamp, floating-paper, hologram, drone-Bali, resort, or literal labelled-door cliché.

### Creative signature

The signature stored with every seed includes narrative engine, spatial metaphor, camera grammar, transition motif, sound motif, color arc, hero prop, blocking, wardrobe arc, emotional turn, and final image. A future episode may reuse the pipeline but must not silently reproduce the same signature cluster.

### Gate order

The implemented pre-generation gate runs from cheapest to most expensive:

1. categorical collision against prior signatures;
2. normalized-description lexical comparison using the configured Jaccard threshold;
3. replay of every historical ledger record against the same originality policy;
4. atomic append to a locked ledger, followed by validation of the exact persisted prefix.

This proves structural and lexical divergence under the declared policy. It does not prove
that two free-form descriptions are semantically different, nor can it compare unseen video
frames. Those judgments remain with the Creative Lock and independent critic until the first
canary MP4 is locally available.

The post-retrieval extension will add, in order:

1. exact SHA-256 and perceptual hashes of start, middle, and end keyframes;
2. one local VLM comparison of a contact sheet on Pro;
3. a critic verdict that binds the visual evidence to the persisted creative signature.

Ambiguous or failed checks never become a silent pass. Intentional reuse must be declared with provenance.

## Reasoning budget policy

High reasoning is used only for:

- producing two or three genuinely different candidate seeds in one call;
- selecting and locking one seed;
- resolving a critic disagreement or an ambiguous originality result.

Everything else is deterministic or mechanical: prompt expansion, schema validation, hashes, media probing, keyframe extraction, identity thresholds, duplicate detection, contact-sheet assembly, and manifest writing.

The model does not re-read the full research corpus for each clip. It receives the context SHA, Creative Lock, one family contract, and the current variant axis. The final script will be grounded later in a separate legal-claim pass.

## Success criteria for the probe wave

The wave succeeds only if:

- every submitted generation has durable job and output lineage, including failures;
- the six-family frontier is complete and no more than 24 attempts are made;
- every downloaded artifact is a valid portrait MP4 of approximately eight seconds;
- no selected clip violates identity, text, duplicate-person, or cliché invariants;
- the selected grammar contains every clean edit surface required by the continuity map;
- the motion-to-stasis arc is visually coherent across independently generated clips;
- native audio provides usable room tone and at least one clean click/latch bridge;
- the winning grammar is chosen for narrative fitness, not merely technical polish;
- rejected variants retain explicit rejection reasons;
- no external publication or deployment occurs.

## Deferred work

After probe review, the next recommended priorities are:

1. legally ground the three-part distinction: what residency grants, merely enables, and does not determine;
2. write a short script whose claims bind to evidence IDs before voice or lipsync generation;
3. convert the selected camera grammar into a continuity map with exact occlusion handles and sound bridges;
4. expand the implemented seed/originality ledger with a production anti-cliché corpus and keyframe perceptual comparisons after the first canary is locally available.

The generalized categorical/lexical originality gate is no longer deferred. It is implemented as an append-only, locked ledger: exact replays are idempotent, child seeds bind to their parent, and a new result must differ on at least four material axes including one conceptual and two cinematic axes. Surface-only changes do not count as originality.

The ledger now contains the root Creative Lock and the M02-v05 inertia-stop child. The child
passes with ten material differences, including five conceptual and five cinematic axes, and
a description Jaccard of `0.1` against the parent. Its registration is deliberately labelled
as a post-generation backfill: it demonstrates the policy on an existing result, while the
enforced rule for every subsequent creative pass is registration before spend.
