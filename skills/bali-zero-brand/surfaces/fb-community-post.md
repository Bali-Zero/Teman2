# Surface: fb-community-post (Facebook Page)

**Status**: spec drafted 2026-05-11, verified + corrected 2026-05-18 (NB-4 query removed wrong KEP-71 citation). Pending first production post + health-check audit of facebook.com/balizero0 (admin: Antonello). Subhi D4 Minggu 3+ deliverable. **W1 Post 1 publish target: 2026-05-19**.

## Purpose

Brand-compliant short-form posts published to **facebook.com/balizero0** (existing Page, admin: Antonello). Distinct from Instagram carousel surface — FB is **single post + one image** (or one short video, no carousel logic). Audience skew: older WNA + Indonesian community + retiree segment. Less editorial-design heavy, more conversational + practical.

Access via Business Manager (`business.facebook.com`) → Subhi role = **Content Creator** (can post + schedule, cannot delete Page or alter admins).

## Cross-surface rules (inherited mandatory)

Per constitution Article 12.2, every FB post inherits:

- Article 2 — palette (closed namespace, `color.bg.antracite` etc. — applies to image overlays only, FB post body has no palette control)
- Article 3 — single sans-serif family in image overlays (Montserrat/Inter/Poppins)
- Article 6.3 — numbers concrete
- Article 6.4 — regulatory citations verbatim
- Article 6.5 — bilingual lexicon untranslated (KITAS, PT PMA, KBLI, hak pakai, BATARA, NPWP, SPT, PPh)
- Article 6.6 — no CTA hard-sell as primary editorial content
- Article 6.7 — no emoji
- Article 7 — forbidden phrases closed list
- Article 8 — spell-check + acronym verification

## Surface-specific rules

### Format

- **Post body**: 200-500 characters ideal (FB algorithm shows first ~250 chars in feed before "See more"). Hard cap 1.500 chars.
- **Lede**: first 60 characters MUST contain the topical anchor (regulation cite, concrete number, or named entity) — that's what shows in news feed preview.
- **Single image** (1200×630px landscape OR 1080×1080px square — landscape preferred for feed). NO carousel (that's IG surface). NO 9:16 portrait (FB strips it).
- **No link in body**: FB algorithm down-ranks posts with external links. Use Page's "first comment" pattern (post body has no link, first comment by Page admin contains the link).
- **Tone**: complete sentences, no headline-style. Read aloud test: if it reads like a press headline, rewrite to read like a colleague explaining.

### Language

- **Default**: bahasa Indonesia. FB audience skew = Indonesian community + Indonesian-speaking WNA + WNA in Indonesian language acquisition. ID-first matches platform reality.
- **English variant**: only when target audience is explicitly international (e.g. "How investors in EU read Indonesia's KEK announcement"). Mark with leading `[EN]` tag visible only in internal scheduling tool, not in post body.
- **NEVER mix ID + EN in same post body**. Choose one, stay there. Bilingual lexicon (KITAS, PT PMA etc.) remains untranslated per Article 6.5 regardless of host language.
- **Italian / Russian / French**: NEVER on this surface. Those audiences land via web + email + DM, not FB.

### Typography (image overlay only)

Same as `carousel-ig` surface for any text laid on image:

- Montserrat 700 for headings.
- Montserrat 500 for body callouts.
- NEVER use FB native font picker — produces generic system Helvetica that breaks brand consistency.
- Image overlay text: max 20% of image area (per Meta's old "20% rule" — still affects reach even after deprecation).

### Palette (image overlay)

Subset of full brand palette — FB feed crops dark images visually:

- Background overlay: `#373D42` antracite at 70-85% opacity over photo OR `#FFFFFF` flat for "explainer" posts.
- Text on antracite overlay: `#FFFFFF`.
- Text on white: `#1A1A1A`.
- Accent yellow `#F4C430` for the regulation number / concrete data point.
- Status red `#C8102E` for "deadline X" / "blocco Y" only — never decorative.

### Post types (closed set — 5 archetypes)

#### Type 1 — Regulatory micro-update

**When**: new regulation published or amended (Permenkumham, PMK, PP, Perpres).
**Body**: 2-3 sentences. (a) verbatim citation of regulation number + date; (b) what it changes in 1 sentence; (c) who is affected in 1 sentence.
**Image**: solid antracite background with regulation number in yellow Montserrat 700, 80px size, centered.
**Voice register**: `analitico`.
**First comment**: link to full Bali Zero blog article on balizero.com.
**Example body** (ID):

> Permenkumham No. 22 Tahun 2023 mengganti kode visa B211A menjadi C1 (Visa Kunjungan) dan C312 menjadi E23 (Working KITAS). Berlaku sejak 2023, masih banyak agen yang menggunakan kode lama dalam materi marketing. Jika kamu mengurus visa, pastikan dokumen referensimu sudah update.

#### Type 2 — Concrete data callout

**When**: stat, deadline, fee change, official number worth knowing.
**Body**: 3-4 sentences. Lead with the number ("Rp 150.000" / "31 Mei 2026" / "183 hari"). Explain context. State implication for user.
**Image**: white flat background with the number in `#1A1A1A` Montserrat 700 80-120px, single line of context below in 24px Montserrat 500.
**Voice register**: `tecnico` or `pedagogico`.
**First comment**: source URL (official site — DJP, BKPM, Imigrasi, JDIH).
**Example body** (ID):

> SPT Tahunan PPh Orang Pribadi TP2025 diperpanjang sampai 30 April 2026 (sebelumnya 31 Maret), bebas sanksi administrasi. Hanya untuk WP OP, Badan tidak termasuk. Berdasarkan KEP-55/PJ/2026 yang dipublikasikan DJP 27 Maret 2026, terkait implementasi penuh sistem CoreTax.

> **Source verbatim NB-4 (2026-05-18 verification)**: KEP-55/PJ/2026, scope WP OP only, deadline 30 April 2026. Earlier draft of this spec cited "KEP-71" + corporate scope + 31 May — both wrong, corrected after NB-4 query d4b2eedb-9863-4a1a-81ff-a11b0b45d853.

#### Type 3 — Pedagogical short-form

**When**: explaining a concept, process, or common misunderstanding.
**Body**: 4-6 sentences. Frame as question or common belief, then unpack. Use "kalau kamu..." / "if you..." conversational opener.
**Image**: photo of a real-world artifact (akta, NPWP card placeholder mockup, SIMBG screenshot redacted) with light overlay band containing the post title in 36px Montserrat 700.
**Voice register**: `pedagogico-divulgativo`.
**First comment**: link to deeper Bali Zero article OR "Tanya kami di WhatsApp [link]" (only when topic naturally maps to consultation, not as default).
**Example body** (ID):

> "Aku sudah lebih dari 183 hari di Indonesia tahun ini, jadi aku pajak resident, kan?" Tidak selalu. Pasal 2 UU PPh 36/2008 + PP 23/2018 melihat 3 hal: (a) jumlah hari, (b) niat untuk tinggal, (c) pusat kepentingan ekonomi. Kalau kamu masih punya rumah + pendapatan utama + keluarga di luar negeri, kamu bisa tetap non-resident meskipun lewat 183 hari. Kasus per kasus.

#### Type 4 — Community / civic

**When**: Bali Zero comments on broader civic, cultural, regional events. NON-commercial. Reaffirms positioning as part of community, not extractive service.
**Body**: 3-5 sentences. Observation + value + (optional) what Bali Zero is doing/thinking about it.
**Image**: photo (Bali landscape, local event, regulatory office, NOT stock palms-and-beaches) OR no image (text-only posts OK on FB for civic posts).
**Voice register**: `community-warm` (defined below — register added specifically for this surface).
**First comment**: usually none. Civic post is not a funnel.
**Example body** (ID):

> Minggu lalu Pemkab Badung mengumumkan moratorium PBG baru untuk vila komersial di Pecatu. Kami baca dokumen Perbup-nya sore ini. Kesan awal: bukan stop total, tapi review per-kasus dengan tim teknis baru. Akan kami tulis penjelasan lengkap minggu ini.

#### Type 5 — News-flash editorial

**When**: a major regulatory or political event happened in the last 24h that affects Bali Zero clients.
**Body**: 2-3 sentences. Lead with what happened, then "kami sedang baca dokumennya" / "we are reading the document". This is **provisional positioning** — signals Bali Zero is on the ball without making premature claims.
**Image**: solid red `#C8102E` background with "BREAKING" or "FRESH" or news source name in white Montserrat 700, plus the event verbatim. Use red sparingly — overuse breaks the signal.
**Voice register**: `militante` (only register that fits the urgency, but kept under 3 sentences to avoid melodrama).
**First comment**: link to original source (NOT Bali Zero blog yet — blog post comes later).
**Example body** (ID):

> Pemerintah baru saja membatalkan moratorium izin properti asing yang diumumkan kemarin. Pengumuman dari Menteri ATR/BPN, sumber: detik.com. Kami sedang baca dokumen aslinya — update follow-up dalam 24 jam.

### Voice register additions (FB-specific)

In addition to the 7 voice registers in `voice/register-examples.md`, FB surface introduces:

**community-warm**: warm, observational, first-person plural ("kami"). Acknowledges Bali Zero is _part of_ the community, not external observer. Sentence rhythm: medium-length (15-25 words), conversational. NO marketing CTA. NO data-density (that's `analitico`). Use only for Type 4 posts.

**Example community-warm**:

> Hari ini upacara Hari Suci Saraswati di Bali. Kantor kami buka, tapi tim Bali siang ini lebih tenang. Kalau kamu butuh dokumen mendesak, WhatsApp tetap aktif. Selamat hari Saraswati untuk semua keluarga, klien, kolega Indonesia.

### Banned FB patterns

- Hard-sell CTA: "Book now", "DM us today", "Limited slots", "Hubungi kami sekarang" — all forbidden.
- External link in post body (algorithm down-ranks → reach drops 50-70%). Use first-comment link pattern instead.
- Emoji anywhere (post body, image overlay, first comment).
- "Hi Bali friends!", "Hey everyone!", "What's up Bali?" — generic greeters. Lead with the substance.
- All-caps in body (reads aggressive, FB algo flags as "low quality").
- Stock photos: palm trees, sunset beach, surfboard, Bintang bottle. Constitution Article 5.3.
- Tagging influencers / "@" mentions of unrelated accounts for reach. Looks spammy.
- Republishing the same post within 30 days even if edited. FB dedup penalizes.
- "Repost from our IG" with the same image. Repurpose, don't recycle: same topic, FB-specific framing.
- Posting >2x per day. Reach drops on 3rd+ same-day post.

### Scheduling discipline

- **Frequency**: 3-5 posts/week is the sweet spot for FB reach decay curves. 1-2/week looks dormant; 7+/week burns audience.
- **Time of day** (Bali audience): 07:30-08:30 WITA (morning commute) OR 19:00-21:00 WITA (evening). Pre-schedule via Meta Business Suite, not native FB scheduler (Suite has better analytics).
- **Day of week**: Tue / Wed / Thu best. Saturday + Sunday lowest reach for B2B/regulatory content (different for civic/community).
- **Mix per week**: 2× Type 1-3 (regulatory/data/pedagogical), 1× Type 4 (community), 0-1× Type 5 (only when news warrants).

## Workflow: from idea to publish

1. **Topic trigger**: regulatory delta (regulatory-watcher agent), client question repeat (CRM), community event, news flash.
2. **Choose type** (1-5 above).
3. **Draft body** in Indonesian (or English if explicitly international).
4. **Compose image** in Canva using brand kit template `DAHJEkWpkzY` (same anchor as carousel) — DO NOT use FB built-in image editor (loses brand consistency).
5. **First-comment link**: identify the canonical Bali Zero blog article OR official source URL.
6. **QA checklist** (below).
7. **Schedule** via Meta Business Suite for next available slot per "Time of day" + "Day of week" rules.
8. **Antonello review**: posts touching regulation, fee changes, or government policy → Antonello approves before publish. Civic/pedagogical/concrete-data posts → Subhi publishes directly, weekly review.
9. **Telemetry**: 7 days post-publish, log reach + engagement to `~/nuzantara/research/marketing/fb-metrics/YYYY-MM-DD.json` for trend analysis.

## QA checklist (mandatory before schedule)

- [ ] Type 1-5 explicitly tagged (in scheduler note or pending JSON)
- [ ] Language is single (ID OR EN, not mixed)
- [ ] First 60 chars contain regulation cite / number / named entity
- [ ] Body ≤500 chars (or up to 1500 if necessary, justified)
- [ ] No external link in body (link is in first-comment)
- [ ] No emoji anywhere
- [ ] No forbidden phrases (cross-check `voice/forbidden-phrases.md`)
- [ ] Regulatory citation verbatim if present (cross-check Article 6.4)
- [ ] Bilingual lexicon untranslated (KITAS, PT PMA, NPWP, SPT, KBLI etc.)
- [ ] Image is brand-compliant (Montserrat, palette subset, no stock palms)
- [ ] Image text ≤20% of area
- [ ] Hard-sell CTA absent
- [ ] No "Hi Bali friends" or generic greeter
- [ ] Time-of-day scheduled within window 07:30-08:30 OR 19:00-21:00 WITA
- [ ] Antonello approval obtained IF post touches regulation/fee/policy
- [ ] First-comment text drafted (if applicable) with link

## Files in this surface

- `surfaces/fb-community-post.md` — this spec (you are here).
- `surfaces/fb-community-post/example-type1-regulatory.md` — example regulatory micro-update (TODO, author on first real post).
- `surfaces/fb-community-post/example-type2-data.md` — example concrete data callout (TODO).
- `surfaces/fb-community-post/example-type3-pedagogical.md` — example pedagogical short-form (TODO).
- `surfaces/fb-community-post/example-type4-community.md` — example community/civic (TODO).
- `surfaces/fb-community-post/example-type5-newsflash.md` — example news-flash (TODO).

Examples authored on first real publish. Subhi authors example #1 (Type 1 or 2 — most common) under Antonello review; subsequent examples accumulate organically.

## Health-check (one-time, before first publish)

Required from Antonello before Subhi schedules first post:

- [ ] Pagina balizero0 last-post date noted (Last-post >6 months ago → first post is Type 4 "we're back" soft re-entry, NOT Type 1/2 launch)
- [ ] Follower count noted (sets reach expectation baseline)
- [ ] Lingua dominante storica noted (ID/EN/mix — sets default language for Subhi's drafts)
- [ ] Any tone-shift from past posts to current strategy is acknowledged + Antonello-approved (e.g. older posts were promotional → new strategy is editorial; reader doesn't see whiplash)
- [ ] Business Manager access for Subhi (role: Content Creator) confirmed working

Record findings in `~/.claude/projects/-Users-nuzantara/memory/reference_balizero_social_accounts_2026_05_11.md` (existing memory entry).

## Cross-references

- **Constitution**: `~/.claude/skills/bali-zero-brand/constitution.md` — all Articles cited above
- **Voice registers**: `~/.claude/skills/bali-zero-brand/voice/register-examples.md` — analitico, pedagogico, tecnico, militante (community-warm added by this surface)
- **Carousel IG surface** (sister surface for visual content): full constitution applies including layout families
- **Email template surface**: similar voice palette, different format
- **Account inventory**: `~/.claude/projects/-Users-nuzantara/memory/reference_balizero_social_accounts_2026_05_11.md`
