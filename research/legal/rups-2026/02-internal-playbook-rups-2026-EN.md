# Internal Playbook — Annual Report / RUPS Filing 2026

**Bali Zero Corporate Desk · Setup Team operating manual · FY2025 cycle**

> This is an internal document. It tells the setup team how to run a client's annual-report obligation end to end under Permenkum 49/2025, where the traps are, and what to say to the client at each step. The client-facing notice is a separate file (`01-client-notice`). Keep the daily tracker (Google Sheet) updated per client as you move through these steps.

---

## 1. The obligation in one screen

Every PT *persekutuan modal* (PMA and PMDN) must, for financial year 2025:

1. Have its directors present the annual report to the **RUPS**, which approves it — **within 6 months of fiscal year-end** → **30 June 2026** for a 31 December year-end (legal base: **UU 40/2007**, Companies Law).
2. Have that approval recorded in a **notarial deed** (*akta notaris*) — **Pasal 16, Permenkum 49/2025**.
3. Have the notary file the deed into **SABH / AHU Online** — **within 30 calendar days of the deed's signing date** (*tanggal penandatanganan akta*) — **Pasal 16, Permenkum 49/2025**.

**Sanction for default (Pasal 17):** *teguran tertulis* (written warning) → *pemblokiran akses SABH* (SABH access block = company legally frozen: no director/shareholder/deed/address/capital changes; cascades to KITAS/work-permit and OSS).

Regulation in force since **17 December 2025**; FY2025 is the first cycle it bites.

### The date logic — get this right, it is the #1 client question

- There is **no fixed "30 July deadline" in the law.** The hard legal date is **30 June** (the RUPS).
- The **30-day clock starts at the deed signing, not the RUPS.** If the deed is signed 30 June, the notary's filing deadline is **30 July**. If the deed is signed 12 June, the filing deadline is **12 July**.
- So "by 30 July" is the *practical outer edge* only for a deed signed on the last possible day. Do not let a client believe they have until 30 July to hold the meeting. **The meeting is 30 June. Full stop.**

---

## 2. Client segmentation — decide the path first

Before touching anything, classify the client. The path differs.

| Client profile | Path |
|---|---|
| **Active PT PMA / PMDN, Dec year-end** | Full path: accounts → RUPS/circular → deed → SABH filing. Standard. |
| **Dormant PT (zero activity 2025)** | **Still full path.** Obligation is on the entity, not turnover. Near-empty report, but RUPS + deed + filing all required. This is the highest-risk-of-being-forgotten segment — prioritise outreach. |
| **PT Perorangan (single owner)** | Lighter: **no RUPS, no notarial deed.** Financial report filed electronically via SABH directly. Do not book a notary. |
| **Non-December fiscal year** | Six-month clock runs from *their* year-end, not 30 June. Recompute the dates per client. |
| **Already has an SABH block (any cause)** | Stop. The block must be cleared first (often stale UBO data) before any new filing will go through. Flag to senior immediately. |

---

## 3. The workflow, step by step

### Step 0 — Open the file and the tracker row
Create the client's row in the daily Google Sheet tracker. Fill: client, PT name, FY-end, owner (you). Set status = `Accounts pending`. Every later step updates this row the same day you do the work.

### Step 1 — Collect the inputs from the client
Send the client the input request (script in §5.A). You need:
- **2025 financial statements** — balance sheet + P&L minimum. **Audited financials are required if assets OR turnover ≥ IDR 50 billion** — check this threshold early; an audit cannot be improvised in late June.
- **Current directors, commissioners, shareholders** — confirm against what the deed will state. Mismatches here are a deed-redraft, so catch them now.
- **UBO (beneficial owner) details** — current. See the UBO trap in §4.

Tracker: status → `Accounts in`.

### Step 2 — Choose the meeting form
Two valid forms under UU 40/2007:
- **Physical / virtual RUPS** — a real meeting, minutes taken.
- **Circular resolution (Art. 91)** — written approval signed by *all* shareholders, no meeting. Faster for the June wave, and most notaries prefer it for volume. **The notary drives the exact format** — confirm with them before drafting, because how the circular is papered into the required deed varies by notary.

Tracker: record which form in the notes.

### Step 3 — Book the notary NOW
This is the bottleneck, not a formality. **Every PT in Indonesia has the same 30 June deadline — June is the notaries' busiest month in years.** Book the slot before the accounts are even final; you can finalise figures into a held slot, you cannot conjure a slot in the last week.

Use a notary we have a working relationship with. Confirm they will (a) deed the RUPS approval and (b) handle the SABH filing — both, in writing.

Tracker: status → `Notary booked`, record notary name + target deed date.

### Step 4 — Hold the RUPS / sign the circular, then the deed
- Approve: the annual report, discharge of directors (*pelunasan*), and any (re)appointments due.
- Notary records the approval in the **akta notaris**. **The deed signing date is the date that starts the 30-day SABH clock — write it down the moment it happens.**

Tracker: status → `Deed signed`, record exact deed date, compute filing deadline = deed date + 30 days, put it in the deadline column.

### Step 5 — Confirm the SABH filing actually happened
The notary files within 30 days. **Do not assume it was done — ask for the filing evidence** (the SABH/AHU submission receipt). A deed that never reaches SABH is the same as no compliance: the warning-then-block chain still triggers.

Tracker: status → `Filed`, record actual filing date + attach/link the evidence. Only now is the obligation closed.

### Step 6 — Close-out check on standing + UBO
While you are in the client's AHU record, verify:
- the filing shows as received and the company is not flagged;
- **UBO data is current** — stale UBO records jam SABH transactions under the same regulation and will surface as a block at the next corporate action.

Tracker: status → `Closed`, note any UBO follow-up needed.

---

## 4. Traps — where this goes wrong

**The dormant-company miss.** The single most common failure. Owners of sleeping PTs don't think the obligation applies and we don't think to chase them. It applies. They discover the block months later when they try to sell or close. **Proactively list every dormant PT in the book and contact each one this cycle.**

**The deed-date / RUPS-date confusion.** The 30 days run from the *deed signing*, not the meeting. A team member who starts the clock from the RUPS date will under-count and risk a late filing. Always anchor the deadline to the deed.

**The "I'll do it in December" client.** The old habit. There is no December option anymore — the SABH window for FY2025 opened 1 June 2026 and the meeting deadline is 30 June. Correct this belief on first contact.

**The audit-threshold surprise.** A client at/above IDR 50 billion assets or turnover needs *audited* financials. An audit takes weeks. If you discover this in mid-June you have a problem. Screen for the threshold at Step 1.

**The stale UBO block.** A client can be fully ready to file and still be blocked because their UBO record is out of date. Check UBO standing early; a UBO consent/statement refresh may be needed before anything else moves.

**Assuming the notary filed.** The notary files, but you own the outcome for the client. Always retrieve the filing evidence. "The notary said they'd do it" is not evidence.

**The KBLI chain-reaction.** If a client also has a pending KBLI/activity deed amendment from the June 2026 transition, an SABH block from a missed annual report will stop them fixing the KBLI too. Compliance debts in Indonesia don't stay in their own lane — if a client has both open, sequence the annual-report filing first to keep SABH unblocked.

---

## 5. Client communication scripts

> Keep the same plain, authoritative Bali Zero tone. State the date, state the consequence, state what we need. No hedging.

### 5.A — Input request (start of file)

> Subject: **Your 2025 annual report filing — what we need from you**
>
> Indonesia changed the rules at the end of 2025. Your company's annual shareholders' approval of the 2025 report must now be recorded by a notary and filed with the Ministry of Law — the deadline to approve is **30 June 2026**, and the filing follows within 30 days.
>
> To open your file, please send us:
> 1. Your **2025 financial statements** (balance sheet + profit-and-loss).
> 2. Confirmation of your **current directors, commissioners, and shareholders**.
> 3. Your **beneficial-owner details**, so the filing goes through cleanly.
>
> We handle the meeting, the notary, and the government filing. The one thing only you can give us is the figures and the confirmations above — the sooner they arrive, the safer the deadline.

### 5.B — Dormant-company nudge

> Subject: **Yes, this applies to your dormant company too**
>
> Your PT did no business in 2025 — and it still has to file. The obligation is on the company itself, not on whether it traded. A dormant PT that skips this gets its government access blocked, and owners usually find out only when they try to sell or close the company and can't.
>
> It's a small job: one short report, one notary deed, one filing — and then your company is compliant and you don't think about it again. Let us handle it this month.

### 5.C — Deadline reminder (client gone quiet)

> Subject: **Your annual-report deadline is close — and notaries are full**
>
> We still need your 2025 figures to file your annual report. The approval deadline is **30 June**, and every company in Indonesia is booking the same notaries right now. Each day of delay narrows the window. Send us the statements and we'll secure your slot today.

### 5.D — Confirmation of completion

> Subject: **Done — your 2025 annual report is filed**
>
> Your annual report was approved, deeded by the notary, and filed into the Ministry of Law's SABH system on [date]. Filing evidence is attached. Your company is compliant for the 2025 cycle and your SABH access is clear. Nothing further is needed from you this year.

---

## 6. Escalation

- **Pre-existing SABH block** discovered at any step → senior corporate, same day. Do not attempt a new filing over an existing block.
- **Audit required (≥ IDR 50bn) and no auditor engaged** → flag to the client and senior immediately; this is a timeline risk that can blow the deadline.
- **Director/shareholder mismatch** the client cannot quickly resolve → senior, because it may require a separate corporate amendment before the deed.
- **Client refuses / ignores after 5.C** → log in tracker as `At risk`, escalate to the account owner for a direct call. Document that we warned them, with dates.

---

## 7. Definition of done

A client file is closed only when the tracker row shows **all** of:
- RUPS/circular approved (date recorded);
- deed signed (date recorded);
- SABH filing completed within deed + 30 days (actual date recorded);
- **filing evidence retrieved and linked**;
- UBO standing checked.

Anything short of that is `In progress`, not done — regardless of what the notary said.

---

*Legal base: UU No. 40 of 2007 (Companies Law), Art. 66, 91 · Permenkum No. 49 of 2025, Art. 16 (deed + 30-day SABH filing), Art. 17 (teguran tertulis → pemblokiran akses SABH) · in force 17 December 2025.*
