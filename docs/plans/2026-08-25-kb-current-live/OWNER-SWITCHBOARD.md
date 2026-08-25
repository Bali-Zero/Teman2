# Owner switchboard — prepared proposals (MANDATE §7)

Nothing in the campaign blocks on these. They are built, measured, and waiting for a signature.

Measured 2026-08-25 by the orchestrator. Every number below was produced by a query run that
day against the Pro-bound WhatsApp mirror; none is inherited from a prior document.

---

## Decision 1 — the questions the KB must never get wrong

**Prepared from real client traffic, not from imagination.**

Source: `whatsapp_message_context`, the Pro-bound raw mirror. 60,004 inbound + 5,686 received
messages, 2022-12-19 → 2026-08-24. 10,929 of them carry a question mark. Restricting to
non-group chats and to messages between 25 and 180 characters gives the working set below.

No client text is reproduced in this file. Every example is a paraphrase written by the
orchestrator; names, numbers, companies and addresses are absent by construction (SYMBIOSIS
Law 2 — the boundary is the output, and this file is an output).

### 1.1 Topical volume — question-bearing inbound messages

| Lane          | Surface                                                                                              |  Hits | Non-group |
| ------------- | ---------------------------------------------------------------------------------------------------- | ----: | --------: |
| A immigration | visa · kitas · imigrasi · voa · sponsor · overstay · e-visa · multiple-entry · izin tinggal · golden | 2,752 |     2,433 |
| B company     | pt pma · kbli · oss · nib · lkpm · akta · bpjs · modal                                               |   656 |       583 |
| C tax         | pajak/tax · npwp · spt · efin · pph · coretax · ppn                                                  |   298 |       248 |
| D property    | tanah/land/villa · notaris · sertifikat · leasehold · hak pakai · imb/pbg · hgb · pbb                |   187 |       149 |

Counts are per keyword group and overlap across rows: a single message asking about an
investor KITAS held through a PMA is counted in both A and B. That overlap is itself finding
1.4 below, not noise to be cleaned away.

### 1.2 The largest class of traffic is one the KB must NOT answer

A substantial share of question-bearing inbound is **case state**, not knowledge:
_has my extension been submitted_ · _where do I see my tax number_ · _is the certificate ready
yet_ · _when do I pay_ · _can you send me a copy of my document_.

No knowledge base can answer these, and a KB that tries will answer them wrongly. This bounds
the product: the ~20 questions per topic must be drawn from the **knowledge** fraction, and the
correct behaviour on a case-state question is to route, not to retrieve. Recorded here because
a journey suite built on the raw traffic distribution would be measuring the wrong thing.

### 1.3 Clients speak in index codes and colloquial handles — never in instrument names

Across the sampled immigration traffic, clients ask about **C1, C5, C12, D1, D12, E33G,
E31/E28A**, and about handles like _investor KITAS_, _secondary home KITAS_, _retirement
KITAS_, _nomad/remote-working visa_, _working KITAS_. In the entire sample, **not one client
named an instrument**: no Permenkumham number, no UU number, no PP number.

This is the campaign's central retrieval risk and it is invisible to any journey whose query is
already phrased in statute language. A journey that asks _"what does Permenkumham 22/2023 say
about izin tinggal"_ proves the corpus is indexed; it does not prove a client can reach it.

**Consequence, binding on every lane:** each topic's journey set must contain at least three
journeys whose `question` is phrased the way a client phrases it — index code or colloquial
handle — while the `verbatim_phrase` remains the statute's own words. The gap between the two
is the thing being measured.

### 1.4 The real questions cross topic boundaries

Recurring shapes in the sample span two lanes at once: secondary-home KITAS against _hak pakai_
and property value rather than a bank deposit (A×D); investor KITAS renewal where the sponsor
is the client's own PMA (A×B); holding a D12 while also holding a PMA (A×B); which KBLI covers
land sub-lease and short-stay rental (B×D); reporting tax under the accommodation NIB (B×C).

A per-topic lane will systematically miss these. **Consequence:** each lane owes at least one
journey whose answer requires an instrument owned by a different lane, and must mark it as
such. These are the journeys most likely to be red, and they are the ones worth the campaign.

### 1.5 Four languages, one corpus

The sampled traffic is English, Indonesian, Italian and Spanish — frequently mixed inside a
single message. Journeys must not be English-only, or the suite will certify a retrieval path
that most of the traffic never takes.

### 1.6 What is asked for the owner

Read §1.2 through §1.5 and sign, or correct. The lane briefs already carry 1.3 and 1.4 as
build constraints; a correction changes what gets built, not merely what gets written down.

---

## Decision 2 — the official PDF of UU 25/2007 (Investment Law)

Prepared measurement pending. Held open.

---

## Decision 3 — `legal_unified_2026`

**Measurement.** 15,410 points, frozen since 2026-05-16, byte-for-byte identical to the May
census. The nightly regulatory watcher has no ingest path anywhere: `regulatory-watcher-run.sh`
contains zero occurrences of qdrant, upsert or ingest. Three entrypoints named the collection;
none of them wrote to it, and the runner that was supposed to could not have run at all.
Of the 18 documents it holds, 11 contradict their own text, and 5 of those had already leaked
into `legal_unified`.

**Recommendation: freeze in place, do not delete, and let the gate keep it unreachable.**

Reasoning: the collection is a measured artifact of a real defect and it is the only surviving
copy of some fragments (3,725 of the Permen ATR/BPN 18/2021 fragments exist there and nowhere
else — lane D §4.4). Deleting it destroys the evidence and the fragments in one gesture. The
gate landed in PR #4907 already prevents any new writer from naming it: the AST lint refuses an
ingest target that a static reader cannot resolve to the registry, so the collection cannot
silently re-acquire a writer. It costs storage and nothing else.

**Owner gesture:** approve the freeze, or instruct otherwise. Deletion, if ever chosen, is a
separate gesture that must follow a containment proof, never precede one.

---

## Decision 4 — team confirmation per topic (G6)

Five real questions per topic, asked by the person who answers that domain. Prepared once each
lane's journey set is green enough to be worth a human's time. Held open by sequence, not by
blocker.

---

## Decision 5 — superseded instruments: remove or mark?

**The question is no longer hypothetical. Lane A measured it happening.**

Journey 3 asks how long a current ITAS is valid and quotes Permenkumham 22/2023, the
regulation in force. It does not rank in the top ten. Journey 4 asks the same question
against the equivalent span of **Permenkumham 29/2021, which was superseded**, and it
comes back at rank 3. A client asking the plainest possible question about the duration
of their own stay permit is answered from a regulation that no longer applies.

Root cause, traced and verified independently (direct fetch of the official page plus two
searches): **both documents carry `legal_status: dicabut` — "revoked" — in their own
payload.** For 29/2021 that is correct. For 22/2023 it is wrong; it is the current
instrument. So the corpus believes the law in force is dead.

This matters for the shape of the decision, not only its urgency: **the obvious remedy
makes it worse.** A filter that excludes anything marked `dicabut` would remove the
correct regulation from the corpus and leave the superseded one — which at least is not
excluded by a rule keyed on a field it fills honestly. Whatever is chosen here cannot be
implemented as a filter on that field until the field is trustworthy.

**Prepared recommendation: MARK, do not remove — and repair the status field first.**

Three reasons, in order of weight:

1. **Removal is irreversible and the identity data is demonstrably unreliable.** Lane A
   found one in-force regulation marked revoked; lane D found a Bali governor's
   regulation filed under a national statute number, and a national regulation stored
   under a garbled four-digit id that no 2021 PP could have. A deletion rule driven by
   these fields would delete correct law. Nothing in this campaign deletes anything.
2. **A superseded instrument still has to be answerable.** Clients ask what applied when
   they filed. An answer that says "this was the rule until 2023, and here is what
   replaced it" is better than silence, and strictly better than an unlabelled quote from
   the old text — which is what happens today.
3. **Marking is testable and removal is not.** A mark can be asserted by a journey: ask
   the current question, require the current instrument's phrase, and require the
   superseded one to be labelled where it appears. That is a probe. "It was deleted" is
   not a probe; it is an absence, and absences are what §4.2 says take three measurements
   to establish.

**Owner gesture:** pick MARK or REMOVE. If MARK, the repair of `legal_status` on
Permenkumham 22/2023 and the audit of that field across the corpus become lane A's next
unit of work rather than an inventory row.

---

## An error of my own, corrected by a lane

Lane D's brief carried my framing of Permen ATR/BPN 18/2021 as a "fuller edition" —
10,266 points in the retired collection against 534 in production, therefore the retired
copy contains what production is missing. **That framing was wrong, and lane D measured
it rather than accepting it.**

Of production's 404 distinct fragment hashes, only **134 (33.17%)** were found anywhere
in the retired copy. The retired edition does not contain two thirds of what production
already has. Two explanations remain live and undistinguished — genuinely different
content, or different chunk boundaries defeating hash-exact comparison — and the retired
copy is ~2.7× internally duplicated (10,266 points across 3,860 unique fragments), which
is consistent with a collection written nightly and never cleared.

Lane D stopped at step 1 of the three-step order and retired nothing. That was correct.
Recorded here because the campaign's rule that identity precedes content applies to the
orchestrator's own assertions, and because a proposal built on the original framing —
"promote the fuller edition" — would have destroyed two thirds of a live document.
