# Operator Daily Tracker — Annual Report / RUPS 2026

**Bali Zero Corporate Desk · how to use the daily log · FY2025 cycle**

> Each operator updates **their own client rows every day** they touch the file. One row per client. Import `03-operator-daily-tracker.csv` into Google Sheets (File → Import → Upload → *Replace current sheet*), then share with the corporate desk. The CSV header is the column order below.

---

## Column legend

| Column | What to write |
|---|---|
| **Client** | Client display name (as in CRM). |
| **PT Name** | Full legal PT name. |
| **Entity Type** | `PT PMA` · `PT PMDN` · `PT Perorangan` · `Other`. Drives the path (PT Perorangan = no notary). |
| **FY-end** | Fiscal year-end date. Default `31 Dec 2025`. Non-December → recompute deadlines. |
| **RUPS Status** | Pipeline stage: `Accounts pending` → `Accounts in` → `Notary booked` → `Deed signed` → `Filed` → `Closed`. |
| **RUPS / Circular Date** | Date the shareholders approved (meeting or circular resolution signing). |
| **Deed Signed Date** | Date the notary signed the *akta*. **This date starts the 30-day SABH clock — record it exactly.** |
| **Notary** | Notary name handling the deed + filing. |
| **Filing Deadline (deed +30d)** | Deed Signed Date + 30 calendar days. The hard outer date for the SABH filing. |
| **SABH Filing Date (actual)** | The date the notary actually filed into SABH/AHU. |
| **Filing Evidence (link)** | Link to the SABH/AHU submission receipt. **No evidence = not done.** |
| **UBO Checked** | `Yes` / `No`. Stale UBO data blocks SABH — verify at close-out. |
| **Owner (operator)** | You — who owns this client file. |
| **Last Update** | Date you last touched the row (update every working session). |
| **Status** | Roll-up: `In progress` · `At risk` · `Done`. `Done` only when all of §"Definition of done" are true. |
| **Notes / Blocker** | Anything outstanding: audit threshold, UBO follow-up, client silence, pre-existing block. |

---

## Status rules

- **`In progress`** — any step before `Filed` + evidence + UBO check.
- **`At risk`** — client silent after the deadline reminder (script 5.C), or a blocker (audit not engaged, pre-existing SABH block, director mismatch). Escalate per the playbook.
- **`Done`** — RUPS approved + deed signed + SABH filed within deed+30d + **evidence linked** + UBO checked. Nothing less.

## The one date rule (don't get this wrong)

The **30-day filing clock runs from the *Deed Signed Date*, not the RUPS date.** Always compute `Filing Deadline = Deed Signed Date + 30 days`. The legal meeting deadline (30 June) is separate and earlier.

## Daily discipline

1. Open the sheet, filter to your rows (Owner = you).
2. For every client you acted on today: advance `RUPS Status`, fill the date columns, set `Last Update` to today.
3. Any client that went quiet or hit a blocker → set `Status = At risk` + note it, and escalate.
4. A client is removed from active chase only when `Status = Done`.

---

*Legal base: UU No. 40 of 2007 (Art. 66, 91) · Permenkum No. 49 of 2025 (Art. 16 deed + 30-day SABH filing, Art. 17 sanctions). In force 17 December 2025.*
