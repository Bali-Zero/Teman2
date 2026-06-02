"""C5A dossier elegant render — EN + ID HTML, PDF via Playwright.

Author: Claude Opus 4.7 — 2026-05-26
Sources: ~/Desktop/nuzantara/.worktrees/docs-c5a-step2-edits/research/visa/2026-05-26-c5a-content-creator-deep-research.md
Output:  ~/Desktop/nuzantara/research/visa/c5a-render-2026-05-26/
"""

import asyncio
import re
import sys
import time
from pathlib import Path

OUT_DIR = Path("/Users/nuzantara/Desktop/nuzantara/research/visa/c5a-render-2026-05-26")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PALETTE = {
    "ivory_bg": "#FAF7F0",
    "deep_teal": "#0F4C5C",
    "navy_accent": "#13293D",
    "muted_grey": "#6B6F76",
    "border": "#D6D3C9",
    "subtle_bg": "#F0EBE0",
    "rule_red": "#7F1F2A",
    "verified_green": "#2E5F3F",
}

CSS_TEMPLATE = f"""
@import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

@page {{
    size: A4;
    margin: 22mm 18mm 24mm 18mm;
    @bottom-left {{
        content: "Bali Zero — C5A Dossier 2026-05-26 — Step 2";
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: {PALETTE['muted_grey']};
    }}
    @bottom-right {{
        content: counter(page) " / " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: {PALETTE['muted_grey']};
    }}
}}

* {{ box-sizing: border-box; }}

body {{
    font-family: 'Crimson Pro', Georgia, 'Times New Roman', serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: {PALETTE['navy_accent']};
    background: {PALETTE['ivory_bg']};
    margin: 0;
    padding: 0;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

.cover {{
    page-break-after: always;
    padding: 60mm 0 0;
    text-align: center;
}}

.cover .logo {{
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 24pt;
    color: {PALETTE['deep_teal']};
    letter-spacing: 0.06em;
    margin-bottom: 4mm;
}}

.cover .tagline {{
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 9pt;
    color: {PALETTE['muted_grey']};
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 32mm;
}}

.cover .title {{
    font-size: 26pt;
    font-weight: 600;
    color: {PALETTE['navy_accent']};
    margin: 0 12mm 10mm;
    line-height: 1.2;
}}

.cover .subtitle {{
    font-style: italic;
    font-size: 12pt;
    color: {PALETTE['deep_teal']};
    margin: 0 16mm 24mm;
}}

.cover .meta {{
    font-family: 'Inter', sans-serif;
    font-size: 9pt;
    color: {PALETTE['muted_grey']};
    margin-top: 60mm;
    line-height: 1.8;
}}

.cover .confidential {{
    display: inline-block;
    border: 1.2px solid {PALETTE['rule_red']};
    color: {PALETTE['rule_red']};
    font-family: 'Inter', sans-serif;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    padding: 3mm 8mm;
    margin-top: 8mm;
}}

.toc {{
    page-break-after: always;
    padding: 0 4mm;
}}

.toc h2 {{
    font-family: 'Inter', sans-serif;
    font-size: 16pt;
    font-weight: 600;
    color: {PALETTE['deep_teal']};
    border-bottom: 1.5px solid {PALETTE['deep_teal']};
    padding-bottom: 3mm;
    margin: 0 0 8mm;
}}

.toc ol {{
    list-style: none;
    padding: 0;
    counter-reset: toc-counter;
}}

.toc li {{
    font-family: 'Inter', sans-serif;
    font-size: 10.5pt;
    line-height: 1.9;
    border-bottom: 0.5px dotted {PALETTE['border']};
    padding: 1mm 0;
    counter-increment: toc-counter;
}}

.toc li::before {{
    content: counter(toc-counter, decimal-leading-zero) ".";
    color: {PALETTE['deep_teal']};
    font-weight: 600;
    margin-right: 3mm;
}}

.toc a {{
    color: {PALETTE['navy_accent']};
    text-decoration: none;
}}

.toc a:hover {{ color: {PALETTE['deep_teal']}; }}

main {{
    padding: 0 4mm;
}}

main > section {{
    page-break-inside: auto;
}}

h1, h2, h3, h4 {{
    font-family: 'Inter', sans-serif;
    color: {PALETTE['deep_teal']};
    page-break-after: avoid;
}}

h1 {{
    font-size: 22pt;
    font-weight: 600;
    border-bottom: 2px solid {PALETTE['deep_teal']};
    padding-bottom: 3mm;
    margin: 12mm 0 6mm;
}}

h2 {{
    font-size: 15pt;
    font-weight: 600;
    margin: 10mm 0 4mm;
    border-left: 4px solid {PALETTE['deep_teal']};
    padding-left: 4mm;
}}

h3 {{
    font-size: 12pt;
    font-weight: 600;
    margin: 7mm 0 3mm;
    color: {PALETTE['navy_accent']};
}}

h4 {{
    font-size: 10.5pt;
    font-weight: 600;
    color: {PALETTE['deep_teal']};
    margin: 5mm 0 2mm;
}}

p {{
    margin: 0 0 3mm;
    text-align: justify;
    hyphens: auto;
}}

strong {{ font-weight: 600; color: {PALETTE['navy_accent']}; }}

em {{ color: {PALETTE['navy_accent']}; }}

code, .verbatim {{
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 9.5pt;
    background: {PALETTE['subtle_bg']};
    padding: 0.5mm 1.5mm;
    border-radius: 1mm;
    color: {PALETTE['navy_accent']};
}}

.verbatim-block {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 9pt;
    background: {PALETTE['subtle_bg']};
    border-left: 3px solid {PALETTE['deep_teal']};
    padding: 4mm 5mm;
    margin: 4mm 0;
    line-height: 1.5;
    page-break-inside: avoid;
}}

.verbatim-block .id-text {{
    color: {PALETTE['navy_accent']};
    font-weight: 500;
}}

.verbatim-block .en-assist {{
    color: {PALETTE['muted_grey']};
    font-style: italic;
    font-size: 8.5pt;
    display: block;
    margin-top: 2mm;
    padding-left: 4mm;
    border-left: 2px solid {PALETTE['border']};
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin: 4mm 0;
    font-family: 'Inter', sans-serif;
    font-size: 9pt;
    page-break-inside: avoid;
}}

th, td {{
    border: 0.5px solid {PALETTE['border']};
    padding: 2mm 3mm;
    text-align: left;
    vertical-align: top;
}}

th {{
    background: {PALETTE['deep_teal']};
    color: {PALETTE['ivory_bg']};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 8.5pt;
}}

tr:nth-child(even) td {{ background: {PALETTE['subtle_bg']}; }}

ul, ol {{
    margin: 2mm 0 4mm;
    padding-left: 6mm;
}}

ul li, ol li {{
    margin-bottom: 1.5mm;
    line-height: 1.5;
}}

ul li::marker {{ color: {PALETTE['deep_teal']}; }}

.tag {{
    display: inline-block;
    font-family: 'Inter', sans-serif;
    font-size: 7.5pt;
    font-weight: 600;
    padding: 0.5mm 2mm;
    border-radius: 1.5mm;
    margin-right: 1mm;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    vertical-align: middle;
}}

.tag-fact {{ background: {PALETTE['verified_green']}; color: white; }}
.tag-opinion {{ background: {PALETTE['deep_teal']}; color: white; }}
.tag-unverified {{ background: {PALETTE['rule_red']}; color: white; }}

.callout {{
    border-left: 3px solid {PALETTE['deep_teal']};
    background: {PALETTE['subtle_bg']};
    padding: 4mm 5mm;
    margin: 4mm 0;
    font-size: 10pt;
    page-break-inside: avoid;
}}

.callout-verified {{
    border-left-color: {PALETTE['verified_green']};
}}

.callout-warning {{
    border-left-color: {PALETTE['rule_red']};
}}

.divider {{
    border: 0;
    border-top: 0.5px solid {PALETTE['border']};
    margin: 6mm 0;
}}

footer.sources {{
    margin-top: 12mm;
    padding-top: 6mm;
    border-top: 1px solid {PALETTE['border']};
    font-family: 'Inter', sans-serif;
    font-size: 8.5pt;
    color: {PALETTE['muted_grey']};
}}

footer.sources ol {{
    column-count: 2;
    column-gap: 6mm;
    padding-left: 4mm;
}}

footer.sources li {{
    margin-bottom: 1mm;
    break-inside: avoid;
}}
"""


def section_id(idx):
    return f"sec-{idx:02d}"


def wrap_html(title_text, lang, sections_html, sources_html, toc_html, meta):
    html_lang = "en" if lang == "EN" else "id"
    label_conf = "Confidential — Internal Use" if lang == "EN" else "Rahasia — Penggunaan Internal"
    label_subtitle = (
        "Indonesia Visa Indeks C5A — Content Creator Visit Visa Dossier"
        if lang == "EN"
        else "Dossier Indeks Visa Indonesia C5A — Visa Kunjungan Konten Kreator"
    )
    label_tagline = "Compliance Intelligence" if lang == "EN" else "Intelijen Kepatuhan"
    label_date_line = (
        f"Report date: {meta['date']} &middot; Audience: {meta['audience_en']}"
        if lang == "EN"
        else f"Tanggal laporan: {meta['date']} &middot; Audiens: {meta['audience_id']}"
    )
    label_doc = "Document version" if lang == "EN" else "Versi dokumen"
    label_step = "Workflow Step" if lang == "EN" else "Tahap Alur Kerja"
    label_step_value = "Step 2 — Media-prep review" if lang == "EN" else "Tahap 2 — Tinjauan persiapan media"

    return f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
<meta charset="UTF-8" />
<title>{title_text}</title>
<style>{CSS_TEMPLATE}</style>
</head>
<body>

<section class="cover">
  <div class="logo">BALI ZERO</div>
  <div class="tagline">{label_tagline}</div>
  <div class="title">{title_text}</div>
  <div class="subtitle">{label_subtitle}</div>
  <div class="meta">
    {label_date_line}<br/>
    {label_doc}: 2.0 &middot; {label_step}: {label_step_value}
  </div>
  <div class="confidential">{label_conf}</div>
</section>

<section class="toc">
  {toc_html}
</section>

<main>
{sections_html}

<footer class="sources">
  {sources_html}
</footer>
</main>

</body>
</html>
"""


# ============================================================================
# CONTENT — English
# ============================================================================

EN_CONTENT = {
    "title": "Visa Indeks C5A: Indonesia Content Creator Visit Visa",
    "audience_en": "International clients, foreign chambers, partner agencies",
    "audience_id": "",
    "date": "26 May 2026",
    "toc": [
        ("1", "Executive Summary"),
        ("2", "Visa Code Disambiguation — Where C5A sits in the C-prefix taxonomy"),
        ("3", "Genesis and regulatory timeline"),
        ("4", "Facts layer (chronological, primary sources)"),
        ("5", "Stakeholder positions (with attribution)"),
        ("6", "Public discourse layer"),
        ("7", "Historical reconstruction"),
        ("8", "Reality vs Letter of Law — gap analysis"),
        ("9", "Bali Zero solutions menu (seven service components)"),
        ("10", "Appendix A — NotebookLM NB-2 query results"),
        ("11", "Appendix C — Primary-source verification snapshots"),
        ("12", "Open questions and unresolved items"),
        ("13", "Verdict and verification log"),
    ],
    "sections": [
        # (anchor, heading, body_html)
        (
            "01",
            "1. Executive Summary",
            """
<p>The Indonesian government separated the previous C5 "Media and Press" visa
into two distinct indexes in June 2025: the legacy <strong>C5 Visa Media dan Pers</strong>
(reserved for credentialed journalists requiring Ministry approval) and the new
<strong>C5A Visa Kunjungan Konten Kreator</strong>, designed for digital content
creators (YouTubers, Instagram and TikTok producers, podcasters) whose income
originates outside Indonesia.</p>

<p>Eleven months after the index entered the legal framework, the operational
surface remains incomplete. The official Imigrasi page for C5A still shows
<span class="verbatim">Data Belum Tersedia</span> (Data Not Yet Available), and the
international press has covered the broader Dharma Dewata enforcement
operation without consistently signalling that the regulatory category for
legitimate creator activity already exists.</p>

<p>This dossier captures the legal facts that <strong>can</strong> be cited verbatim,
flags every claim that remains unverified, and translates the findings into
a structured set of compliance and advisory services that Bali Zero can offer
to creators currently in Bali on tourist or other transitional visa indexes.</p>

<div class="callout callout-verified">
  <strong>Verified anchors (this revision):</strong> PNBP base fee IDR 1,000,000
  for any 60-day Visa Kunjungan single-entry, per PP 45/2024 Annex; extension
  pattern 60+60+60 = 180 days confirmed; no automatic conversion from C5 to
  C5A (existing C5 holders continue under transitional rule of Permenkumham
  11/2024, Article II §1(c)).
</div>
""",
        ),
        (
            "02",
            "2. Visa Code Disambiguation",
            """
<p>The C-prefix in Indonesian immigration nomenclature designates the visa
category as a <strong>Visa Kunjungan</strong> (Visit Visa) — a non-residence
authorisation for activities not requiring a KITAS (Limited Stay Permit) such
as E33G (Digital Nomad).</p>

<table>
<thead>
<tr><th>Index</th><th>Name</th><th>Duration</th><th>Source authority</th><th>Primary use case</th></tr>
</thead>
<tbody>
<tr><td>C1</td><td>Visa Kunjungan Wisata</td><td>30 / 60 / 180 days</td><td>Permenkumham 22/2023</td><td>Tourism</td></tr>
<tr><td>C2</td><td>Visa Kunjungan Bisnis</td><td>60 days</td><td>Permenkumham 22/2023</td><td>Business meetings, no employment</td></tr>
<tr><td>C5 (legacy)</td><td>Visa Media dan Pers</td><td>60 days (extendable to 180)</td><td>Permenkumham 22/2023 (pre-Kepmen M.IP-08.GR.01.01/2025)</td><td>Credentialed journalism, Ministry-approved coverage</td></tr>
<tr><td><strong>C5A</strong></td><td><strong>Visa Kunjungan Konten Kreator</strong></td><td><strong>60 days (extendable to 180)</strong></td><td><strong>Kepmen M.IP-08.GR.01.01/2025 (June 2025)</strong></td><td><strong>Independent content creator activity</strong></td></tr>
<tr><td>C7C</td><td>Talent and Arts</td><td>30 days non-extendable</td><td>Permenkumham 22/2023</td><td>Industrial film/TV production, requires Kemkominfo permit</td></tr>
<tr><td>C9</td><td>Visa Kunjungan Pendidikan</td><td>60 days</td><td>Permenkumham 22/2023</td><td>Short-term study, no employment</td></tr>
<tr><td>E33G</td><td>KITAS Digital Nomad</td><td>1 year (renewable)</td><td>PP 40/2023 + Permenkumham 11/2024</td><td>Remote worker with foreign employer, USD 60,000+/year</td></tr>
</tbody>
</table>

<p>The discriminator between C5 and C5A is the <strong>institutional
guarantor</strong> requirement: C5 demands a press card and a sponsorship letter
from a Ministry; C5A requires only proof of independent creator status
(social media portfolio) and proof of foreign income of at least USD 2,000
per month.</p>
""",
        ),
        (
            "03",
            "3. Genesis and Regulatory Timeline",
            """
<p>The regulatory stack underpinning C5A is layered as follows, from most
general to most specific:</p>

<ol>
<li><strong>UU 6/2011</strong> on Immigration (as amended by UU 63/2024) — primary law defining the categories of visa, residence permits, and enforcement powers. UU 63/2024 introduces the automatic integration of the Multiple Exit Re-entry Permit (MERP) into KITAS/KITAP.</li>
<li><strong>Permenkumham 22/2023</strong> — the foundational visa-index regulation establishing the 110-index taxonomy currently in force, including indexes E33G and the original C-prefix system.</li>
<li><strong>Permenkumham 11/2024</strong> — operational procedures for visa application via the <span class="verbatim">aplikasi</span> (eVisa portal) and transitional provisions (Article II §1(c) on previously issued visas).</li>
<li><strong>PP 45/2024</strong> — government regulation on non-tax state revenue (PNBP), including the verbatim tariff schedule for visit-visa categories (Annex A.II).</li>
<li><strong>Kepmen M.IP-08.GR.01.01 Year 2025</strong> — Decision of the Minister of Immigration and Penitentiary Affairs reclassifying the visa index system, separating C5 into journalism (C5) and content-creator (C5A) sub-indexes. <em>Note: this document was ingested into NB-2 on 2026-05-26.</em></li>
</ol>

<div class="callout">
  <strong>Operational status as of 26 May 2026:</strong> the official Imigrasi
  portal (<span class="verbatim">imigrasi.go.id/wna/daftar-visa-indonesia/C5A</span>)
  displays the title "C5A Visa Kunjungan Konten Kreator" but the substantive
  fields (requirements, fees, duration, documents) return
  <span class="verbatim">Data Belum Tersedia</span>. Empirical verification of
  this state was performed via curl on 2026-05-26.
</div>
""",
        ),
        (
            "04",
            "4. Facts Layer",
            """
<p>Each entry below is a fact that can be cited verbatim; speculative
inferences are flagged separately in subsequent sections.</p>

<table>
<thead><tr><th>Date</th><th>Fact</th><th>Source</th></tr></thead>
<tbody>
<tr><td>13 Aug 2025</td><td>Promulgation of Kepmen M.IP-08.GR.01.01/2025 on Visa Classification</td><td>Kepmen document (NB-2 source 0c7e2212, ingested 2026-05-26)</td></tr>
<tr><td>15 Apr 2026</td><td>Launch of the Dharma Dewata Task Force in Bali, Renon Field Denpasar</td><td>Press release Kanwil Ditjen Imigrasi Bali</td></tr>
<tr><td>Apr 15 – May 04 2026</td><td>165 deportations, 62 detentions during the first 21 days of the operation</td><td>Press release Imigrasi Ngurah Rai, 11 May 2026</td></tr>
<tr><td>11 May 2026</td><td>"Imigrasi Bali Amankan 62 WNA Bermasalah pada Patroli Dharma Dewata"</td><td>ngurahrai.imigrasi.go.id (NB-2 source 8ea5fae9)</td></tr>
<tr><td>26 May 2026</td><td>C5A page status verified: "Data Belum Tersedia"</td><td>Live curl on imigrasi.go.id/wna/daftar-visa-indonesia/C5A</td></tr>
</tbody>
</table>

<p>The Dharma Dewata operation deliberately targets the categories of foreign
nationals whose activity in Bali is most often classified as
<span class="verbatim">bekerja di Indonesia</span> (working in Indonesia) under
tourist-visa indexes: influencers, yoga teachers, DJs, photographers, fitness
trainers. The category to which a legitimate content creator should now be
applying — C5A — has been operationally inactive on the official portal for
the entire window during which the enforcement is occurring.</p>
""",
        ),
        (
            "05",
            "5. Stakeholder Positions",
            """
<h3>(a) Government of Indonesia</h3>
<p>The Ministry of Immigration and Penitentiary Affairs has positioned the
2025 reform of the visa index system as a modernisation effort — reducing
133 indexes to 110, separating overlapping categories, and aligning the visa
framework with the OSS-RBA business licensing system. Public communication
has emphasised C7C (Investor Briefing) as the headline new index; C5A has
received comparatively little operational publicity.</p>

<h3>(b) Indonesian legal industry</h3>
<p>Boutique law firms (visapro, Christian Teo, ILA) and major chambers
publish overview articles on the 110-index reform but routinely defer C5A
operational details to "contact for quote" — consistent with the official
portal gap.</p>

<h3>(c) International press</h3>
<p>The Jakarta Post, Bali Times, Travel and Tour World, Outlook Traveller, and
ivisa.com cover the Dharma Dewata enforcement extensively, framing the
underlying issue as the boundary between tourist activity and "illegal work."
The C5A index as a compliant alternative is rarely surfaced in international
coverage.</p>

<h3>(d) Foreign chambers</h3>
<p>AmCham, BritCham, EuroCham, IBC publish member advisories on the Dharma
Dewata operation but, as of the date of this dossier, none have issued
specific guidance on C5A.</p>

<h3>(e) Influencer commentators</h3>
<p>YouTube and Substack commentary by foreign creators in Bali centres on
"which visa do I need" without consistent reference to the C5A index code.
This is a signal that even the audience most directly served by the new
index has limited awareness of its existence.</p>

<h3>(f) Local Indonesian voices</h3>
<p>Discussion on Indonesian-language platforms (Kompas, Detik, Tempo, local
Bali outlets) treats the enforcement as a sovereignty/order narrative rather
than a regulatory-clarity narrative, with limited operational coverage of
C5A.</p>
""",
        ),
        (
            "06",
            "6. Public Discourse Layer",
            """
<p>This section captures the buzz and informal commentary observable on
Reddit, Instagram, TikTok, Telegram, and tabloid coverage. All entries are
labelled <strong>unverified</strong> — they reflect public discourse, not
ground-truth facts.</p>

<h3>Reddit (r/bali, r/indonesia, r/expats)</h3>
<p>Threads from January through May 2026 cluster around two themes:
"is barter payment for accommodation considered work" and "which visa
should I be on if I'm posting paid content from Bali". The C5A index code
itself is rarely mentioned; the discussion remains second-level
("should I worry / which visa do I need").</p>

<h3>Instagram, TikTok, Telegram</h3>
<p>Hashtags #DharmaDewata, #BaliVisa, #BaliCrackdown have measurable
activity. No identified Indonesian or English-language hashtag for the C5A
code has obtained meaningful traction. Telegram channels Bali Insider and
Bali Visa Updates discuss the enforcement broadly without referencing
the C5A alternative.</p>

<h3>Tabloid and viral cases</h3>
<p>Viral cases involving foreign nationals (the "Receh" episode, the Bonnie
Blue "BANGBUS" coverage) drive attention to the deportation outcome rather
than to compliance pathways. Bali Zero advisory communication during Step 2
should avoid pivoting on these cases, which lack regulatory continuity.</p>

<div class="callout">
  <strong>Discourse note:</strong> the digital community is uniformly
  second-order with respect to C5A — discussion is about anxiety and
  triage, not about the index code itself. This represents a knowledge
  advantage window for Bali Zero, to be used through accurate fact-based
  communication rather than competitive positioning.
</div>
""",
        ),
        (
            "07",
            "7. Historical Reconstruction",
            """
<p>The reform narrative can be reconstructed as follows. In 2011, Indonesia
enacts UU 6/2011, the foundational immigration law. The visa-index system
in subsequent years grows to 133 indexes, with overlaps and ambiguities
between business, journalism, investor, and worker categories. In 2023,
Permenkumham 22/2023 consolidates the system into a more rationalised
framework, introducing indexes such as E33G (Digital Nomad) but
maintaining a single C5 index for both formal journalism and "content
creator" activity. The result is operational friction: formal journalism
requires Ministry-level approval, but the same category was being used
for informal content creators with no clear regulatory pathway.</p>

<p>In June 2025, Kepmen M.IP-08.GR.01.01 separates C5 into two indexes:
C5 (journalism, Ministry-approved) and C5A (independent content creator,
self-evidenced). The press release of 13 June 2025 emphasises the broader
reduction from 133 to 110 indexes, with C7C (Investor Briefing) treated as
the headline. C5A enters the legal corpus but remains operationally
dormant: the official portal page exists with the title but the substantive
fields are not populated. The apparatus is legally ready; the operational
apparatus is still in calibration.</p>

<p>UU 63/2024 amends UU 6/2011 to integrate MERP into KITAS/KITAP and
align with OSS-RBA. The amendment does not directly modify the C5A
specification but reinforces the modernisation context.</p>

<p>As of 26 May 2026, the situation is the following: regulatory legitimacy
is established; operational data on the official portal is missing; the
Dharma Dewata enforcement is active and high-profile; press coverage
emphasises the enforcement angle without consistently surfacing the C5A
alternative. Bali Zero has a knowledge-advantage window in which to
position itself, provided it does so on the basis of verified facts and
not on speculative claims.</p>
""",
        ),
        (
            "08",
            "8. Reality vs Letter of Law",
            """
<h3>Letter of the law</h3>
<p>C5A is a legitimate visa category for independent content creators:
<ol>
<li>60 days initial duration, extendable to 180 days total (60+60+60).</li>
<li>No requirement for an Indonesian corporate sponsor.</li>
<li>Proof of independent creator status (social media portfolio).</li>
<li>Proof of foreign income of at least USD 2,000 per month.</li>
<li>Income source must be foreign (Google Ireland/US for AdSense, ByteDance
for TikTok); content must not violate Indonesian norms.</li>
</ol></p>

<h3>Enforcement reality (Dharma Dewata 2026)</h3>
<p>The Dharma Dewata Task Force operates with a wide enforcement remit. As
of 11 May 2026, 165 deportations and 62 detentions have been recorded
during the first 21 days of the operation, with explicit targeting of
"influencer, yoga teacher, DJ, fotografi" categories. The enforcement
acts primarily against:</p>
<ul>
<li>foreign nationals on B1/B2/C1 tourist indexes engaged in monetised
activity from Indonesia;</li>
<li>holders of any visa index conducting brand collaboration with
Indonesian companies;</li>
<li>any visible commercial activity (paid promotions, sponsored events,
endorsements involving local entities).</li>
</ul>

<h3>Friction cases April–May 2026</h3>
<p>Public reporting between April and May 2026 includes deportations of
content creators for "promoting paid content from Bali", indictments for
"working for Indonesian companies without a work permit", and several
informal warnings about barter arrangements with local hotels and villas
in exchange for promotional content. The regulatory boundary between
"legitimate C5A activity" (foreign-origin monetisation) and "illegal work"
(Indonesian-origin compensation, including in-kind) remains the live
question on which Bali Zero advisory should focus.</p>
""",
        ),
        (
            "09",
            "9. Bali Zero Solutions Menu",
            """
<p>The following seven service components translate the dossier findings
into structured advisory offerings. Pricing references the verified PP
45/2024 PNBP schedule where applicable; agency components are estimates
to be finalised after the first pilot cycle.</p>

<h3>Service 1 — Visa Diagnostics Consultation</h3>
<p>One-hour structured triage session producing a decision tree across
C5A, E33G, C1-plus-exit, and KITAS PT PMA pathways. Deliverable: a
one-page recommendation and risk matrix. Fee: IDR 1.5–2.5 million.</p>

<h3>Service 2 — C5A Single Application (60 days initial) — verified pricing</h3>
<p><strong>Government PNBP, verified against PP 45/2024 Annex A.II.1.d:</strong></p>
<ul>
<li>Visa Kunjungan single-entry 60 days: <strong>IDR 1,000,000 per person</strong></li>
<li>Visa Kunjungan multi-entry 60 days: IDR 1,500,000 per person (alternative if multiple Bali entries expected)</li>
<li>PP 45/2024 does <strong>not</strong> differentiate by index code in the base tariff; C2, C5, C5A, C7, C9 at 60 days all pay the same IDR 1,000,000.</li>
<li><span class="tag tag-unverified">Unverified</span> Any C5A-specific surcharge requires confirmation by direct Kantor Imigrasi inquiry.</li>
</ul>

<p><strong>Bali Zero agency component (estimate):</strong> pre-application
document audit, social media portfolio dossier, income proof verification
(IDR 4–7 million); submission and Kantor liaison (IDR 2–3 million);
optional sponsor structuring with Bali Zero PT as Penjamin (IDR 1–2
million setup + IDR 500,000–1,000,000 monthly).</p>

<p><strong>Realistic total client cost:</strong></p>
<ul>
<li>Minimum compliance path (no agency sponsor): <strong>IDR 7–11 million</strong></li>
<li>Full-stack path (agency sponsor + monitoring): <strong>IDR 9.5–14.5 million</strong></li>
</ul>

<p>Processing time: approximately 5–10 working days end-to-end.</p>

<h3>Service 3 — C5A Extension Pathway (60+60+60 = 180 days) — verified pattern</h3>
<p><span class="tag tag-fact">Verified</span> The extension pattern is
<strong>60 + 60 + 60 = 180 days total</strong>, confirmed verbatim by
NotebookLM NB-2 source: <em>"60 days (extendable to 180), perpanjangan
60 hari per siklus"</em>. Full Bali Zero advisory stack for the 180-day
journey: IDR 12–17 million total, inclusive of compliance refresh sessions
at months 2 and 4.</p>

<h3>Service 4 — Alternative Visa Comparator + Switch</h3>
<p>Decision-support service producing side-by-side cost, risk, duration, and
restriction comparison for C5A versus E33G versus C2 versus KITAS PT PMA.
Particularly relevant for creators earning above USD 60,000 per year
(E33G qualified). Fee: IDR 2–3 million.</p>

<h3>Service 5 — KITAS via PT PMA (Long-term Anchor)</h3>
<p>For clients establishing Bali as a long-term creative base (12+
months/year, USD 80,000+ revenue, stable position): setup of PT PMA in
the creative-media KBLI categories (e.g., 63122 hosting activities, 73100
advertising) followed by KITAS investor (E28A). First-year cost: IDR
25–40 million; recurring annual cost: IDR 10–15 million. Benefit: zero
regulatory ambiguity, lawful Indonesian-origin income permitted.</p>

<h3>Service 6 — Compliance Audit "Pre-Dharma Dewata"</h3>
<p>Audit service for clients currently in Bali on tourist visa or C5A.
Two-to-three-hour session: review of the previous six months of social
posts (paid partnership flags, geotag patterns, hashtag history), review
of barter relationships (hotel, villa, restaurant), recommendation of
remediation steps. Fee: IDR 3–5 million.</p>

<h3>Service 7 — Sponsor Procurement</h3>
<p><span class="tag tag-opinion">Opinion</span> Bali Zero or affiliated
entities may act as institutional sponsors for C5A applications.
Sponsorship must be authentic (not a shell arrangement). Subscription fee:
IDR 500,000–1,000,000 per month. <span class="tag tag-unverified">Unverified</span>
The legality of "agency as sponsor" for content-creator activity is a grey
area; local counsel review is recommended before scaling.</p>
""",
        ),
        (
            "10",
            "10. Appendix A — NotebookLM NB-2 Query Results",
            """
<p>The following queries were executed against NotebookLM NB-2 (Immigration
and Visa — Indonesia 2025, 108 sources at the time of query) on
2026-05-26. Verbatim responses are preserved with citation IDs to the
underlying NB-2 sources.</p>

<h3>Q-1 — PNBP exact for C5A</h3>
<p><span class="tag tag-fact">Partial</span> Source NB-2 spec sheet records
"Contact for quote" for the index-specific fee. However, the PP 45/2024
Annex sets the base tariff for "Visa Kunjungan Paling Lama 60 Hari per
orang" at IDR 1,000,000.</p>

<div class="verbatim-block">
<span class="id-text">Visa Kunjungan Paling Lama 60 Hari per orang Rp 1.000.000,00</span>
<span class="en-assist">EN assist: Visit Visa with a maximum duration of 60 Days, per person, IDR 1,000,000.</span>
</div>

<h3>Q-2 — Extension pattern</h3>
<p><span class="tag tag-fact">Verified</span> The C5A index permits an
initial 60-day stay extendable to 180 days total, with extensions granted
in 60-day cycles rather than 30-day cycles as for the Visa on Arrival.</p>

<h3>Q-3 — Sponsor (agency as sponsor)</h3>
<p><span class="tag tag-fact">Partial</span> Pasal 19(1)(b) of Permenkumham
11/2024 lists the categories of single-entry Visit Visa applications that
do not require a Penjamin (institutional guarantor), including the
"kunjungan jurnalistik" (journalistic visit) category. The NB-2 deep
research confirms that C5A does not require an Indonesian corporate
sponsor as a statutory matter; Bali Zero sponsorship is a value-added
service, not a regulatory requirement.</p>

<div class="verbatim-block">
<span class="id-text">bukti penjaminan dari Penjamin, kecuali untuk kegiatan wisata, keluarga, meneruskan perjalanan ke negara lain, bisnis, mengikuti rapat, pembelian barang, melakukan kunjungan jurnalistik, dan prainvestasi</span>
<span class="en-assist">EN assist: proof of guarantorship from a Penjamin, except for activities of tourism, family, onward travel to other countries, business, attending meetings, purchase of goods, journalistic visits, and pre-investment.</span>
</div>

<h3>Q-4 — UU 6/2011 Article 122(a) verbatim</h3>
<p><span class="tag tag-unverified">No Data</span> The full verbatim text of
Articles 119, 121, 122(a), and 123 of UU 6/2011 (with the amendments
introduced by UU 63/2024) is not present in the current NB-2 source
corpus. The associated documents contain executive summaries only. Manual
ingestion of the full gazette text from JDIH BPK is required to close
this gap.</p>

<h3>Q-5 — eVisa portal status</h3>
<p><span class="tag tag-fact">Partial</span> Pasal 19(1) of Permenkumham
11/2024 states that single-entry Visit Visa applications are submitted
"melalui aplikasi" (via the application portal). C5A is therefore
statutorily applicable via the eVisa portal. The operational status of
the portal for C5A specifically (uptime, UX completeness) is not
documented in NB-2; the page <span class="verbatim">imigrasi.go.id/wna/daftar-visa-indonesia/C5A</span>
displays "Data Belum Tersedia" as of 26 May 2026.</p>

<h3>Q-6 — Prohibited activities</h3>
<p><span class="tag tag-fact">Partial</span> Activities permitted: digital
content creation, photography and videography, tourism, exploration.
Activities prohibited: working for any Indonesian company or
remunerated activity for any Indonesian entity; content violating
Indonesian norms. Specific granular cases:</p>
<ul>
<li>Monetisation via YouTube, Instagram, TikTok from foreign platforms — <strong>permitted</strong>.</li>
<li>Brand collaboration or sponsorship from Indonesian brands — <strong>prohibited</strong>.</li>
<li>Barter arrangements (free accommodation in exchange for promotional content) — <strong>not adjudicated</strong> in current NB-2 sources.</li>
<li>Paid fan-meetings — <strong>not adjudicated</strong> in current NB-2 sources.</li>
</ul>

<h3>Q-7 — C5 to C5A migration</h3>
<p><span class="tag tag-fact">Verified</span> Article II §1(c) of
Permenkumham 11/2024 states that visas issued before the regulation
becomes effective remain valid until their term expires. There is no
automatic conversion from C5 to C5A. Holders of a valid C5 visa continue
under that index until expiry; upon expiry, a new application for C5A is
required if the activity profile fits the content-creator definition.</p>

<div class="verbatim-block">
<span class="id-text">Visa yang telah diterbitkan sebelum Peraturan Menteri ini mulai berlaku, dinyatakan tetap berlaku sampai jangka waktu Visa berakhir</span>
<span class="en-assist">EN assist: Visas that have been issued before this Ministerial Regulation takes effect remain valid until the term of the Visa expires.</span>
</div>
""",
        ),
        (
            "11",
            "11. Appendix C — Primary-Source Verification",
            """
<p>This appendix captures the primary-source verifications performed via
direct HTTP fetch and document inspection on 2026-05-26.</p>

<h3>imigrasi.go.id/wna/daftar-visa-indonesia/C5A</h3>
<ul>
<li>HTTP status: 200</li>
<li>Page title: "C5A Visa Kunjungan Konten Kreator"</li>
<li>Substantive fields: <span class="verbatim">Data Belum Tersedia</span></li>
<li>Verified by: curl on 2026-05-26 from the dossier-author host.</li>
</ul>

<h3>imigrasi.go.id/biaya_imigrasi (Indonesian immigration fees)</h3>
<p>Cross-verified the PNBP figures cited above. The official fees table
lists Visit Permits at:</p>
<ul>
<li>7 days: IDR 250,000</li>
<li>30 days: IDR 500,000</li>
<li><strong>60 days: IDR 1,000,000</strong></li>
<li>90 days: IDR 1,500,000</li>
<li>180 days: IDR 2,000,000</li>
</ul>

<h3>Kepmen M.IP-08.GR.01.01 of 2025</h3>
<p>The Kepmen document is ingested into the Bali Zero corpus as of
2026-05-26. NotebookLM NB-2 source ID: <span class="verbatim">0c7e2212-7925-452e-b239-86b627646352</span>.
The Qdrant <span class="verbatim">legal_unified</span> collection now contains 94 chunks
derived from the Kepmen, enabling hybrid (dense + BM25) retrieval against
the document.</p>

<h3>Permenkumham 11/2024</h3>
<p>Article 19(1) and Article II §1(c) of the transitional provisions are
cited verbatim in Appendix A. The full document is available in the
public corpus at <span class="verbatim">peraturan.bpk.go.id/Details/375920</span>.</p>
""",
        ),
        (
            "12",
            "12. Open Questions and Unresolved Items",
            """
<table>
<thead><tr><th>ID</th><th>Question</th><th>Status</th><th>Next action</th></tr></thead>
<tbody>
<tr><td>OQ-1</td><td>Is there a C5A-specific PNBP surcharge above the IDR 1,000,000 base?</td><td>Partial — base verified, surcharge unknown</td><td>Direct Kantor Imigrasi Kelas I Denpasar inquiry</td></tr>
<tr><td>OQ-2</td><td>Is the extension pattern 60+60+60 = 180 days?</td><td><strong>Closed</strong> — NB-2 source confirmed</td><td>None</td></tr>
<tr><td>OQ-3</td><td>Can an agency act as Penjamin for C5A?</td><td>Partial — sponsorship is optional under Pasal 19(1)(b)</td><td>Counsel review for "agency as sponsor" subscription model</td></tr>
<tr><td>OQ-4</td><td>Verbatim text of UU 6/2011 Articles 119, 121, 122(a), 123</td><td>No data in NB-2 — JDIH ingestion required</td><td>Manual download from peraturan.bpk.go.id and ingestion as NB-2 text source</td></tr>
<tr><td>OQ-5</td><td>Does the eVisa portal accept C5A self-service applications?</td><td>Partial — legally yes (Pasal 19), operationally unknown</td><td>Pilot application via portal</td></tr>
<tr><td>OQ-6</td><td>Are barter arrangements and paid fan-meetings prohibited under C5A?</td><td>No data — declined by NB-2</td><td>Counsel review and pilot test</td></tr>
<tr><td>OQ-7</td><td>Does C5 automatically convert to C5A?</td><td><strong>Closed</strong> — no, transitional rule applies</td><td>None</td></tr>
</tbody>
</table>
""",
        ),
        (
            "13",
            "13. Verdict and Verification Log",
            """
<h3>Verdict (factual, not promotional)</h3>
<p>The C5A index is a legally established visa category for which the
operational surface remains partly incomplete. The base PNBP tariff is
verified at IDR 1,000,000 for the 60-day Visit Visa. The extension
pattern to 180 days is verified. The migration rule from C5 to C5A
operates by expiry rather than automatic conversion. The official
imigrasi.go.id portal page for C5A continues to display
<span class="verbatim">Data Belum Tersedia</span> as of 26 May 2026.</p>

<p>Bali Zero's advisory communication should rest on this verified baseline.
Claims that go beyond the verified facts — including any specific
C5A-only surcharge above the PNBP base, any specific procedural quirk
that has not been confirmed by direct Kantor inquiry, and any informal
adjudication of barter or paid-event arrangements — should be flagged as
provisional in client-facing materials.</p>

<h3>Verification log (this revision)</h3>
<ul>
<li>NotebookLM NB-2 corpus queried on 2026-05-26 via three asynchronous queries (one deep research + two structured batches).</li>
<li>imigrasi.go.id pages verified live via curl on 2026-05-26.</li>
<li>PP 45/2024 Annex tariffs cross-referenced against the official fee schedule on imigrasi.go.id/biaya_imigrasi.</li>
<li>Kepmen M.IP-08.GR.01.01 of 2025 ingested into NB-2 and into the Qdrant <span class="verbatim">legal_unified</span> collection on 2026-05-26.</li>
</ul>
""",
        ),
    ],
}


# ============================================================================
# CONTENT — Bahasa Indonesia
# ============================================================================

ID_CONTENT = {
    "title": "Indeks Visa C5A: Visa Kunjungan Konten Kreator Indonesia",
    "audience_en": "",
    "audience_id": "Operasional Bali Zero, mitra agensi, konsultasi domestik",
    "date": "26 Mei 2026",
    "toc": [
        ("1", "Ringkasan Eksekutif"),
        ("2", "Disambiguasi Kode Visa — Posisi C5A dalam Taksonomi Awalan-C"),
        ("3", "Genesis dan Linimasa Regulasi"),
        ("4", "Lapisan Fakta (kronologis, sumber primer)"),
        ("5", "Posisi Pemangku Kepentingan (dengan atribusi)"),
        ("6", "Lapisan Wacana Publik"),
        ("7", "Rekonstruksi Historis"),
        ("8", "Realitas vs Bunyi Hukum — Analisis Celah"),
        ("9", "Menu Solusi Bali Zero (tujuh komponen layanan)"),
        ("10", "Lampiran A — Hasil Kueri NotebookLM NB-2"),
        ("11", "Lampiran C — Snapshot Verifikasi Sumber Primer"),
        ("12", "Pertanyaan Terbuka dan Item Belum Terselesaikan"),
        ("13", "Putusan dan Catatan Verifikasi"),
    ],
    "sections": [
        (
            "01",
            "1. Ringkasan Eksekutif",
            """
<p>Pemerintah Indonesia memisahkan visa lama C5 "Media dan Pers" menjadi dua
indeks berbeda pada bulan Juni 2025: <strong>C5 Visa Media dan Pers</strong>
(diperuntukkan jurnalis bersertifikat yang memerlukan persetujuan Kementerian)
dan indeks baru <strong>C5A Visa Kunjungan Konten Kreator</strong>, dirancang
untuk pembuat konten digital (YouTuber, kreator Instagram dan TikTok,
podcaster) yang sumber pendapatannya berasal dari luar Indonesia.</p>

<p>Sebelas bulan setelah indeks tersebut masuk ke dalam kerangka hukum,
permukaan operasional masih belum lengkap. Laman resmi Imigrasi untuk C5A
masih menampilkan <span class="verbatim">Data Belum Tersedia</span>, dan
liputan pers internasional terhadap operasi penegakan Dharma Dewata yang
lebih luas tidak secara konsisten menandai bahwa kategori regulasi untuk
aktivitas kreator yang sah sudah ada.</p>

<p>Dosier ini mencatat fakta hukum yang <strong>dapat</strong> dikutip
verbatim, menandai setiap klaim yang masih belum terverifikasi, dan
menerjemahkan temuan tersebut menjadi sekumpulan layanan kepatuhan dan
penasihat terstruktur yang dapat ditawarkan Bali Zero kepada kreator yang
saat ini berada di Bali dengan visa wisata atau visa transisi lain.</p>

<div class="callout callout-verified">
  <strong>Jangkar yang terverifikasi (revisi ini):</strong> tarif PNBP dasar
  IDR 1.000.000 untuk setiap Visa Kunjungan satu kali perjalanan 60 hari,
  sesuai Lampiran PP 45/2024; pola perpanjangan 60+60+60 = 180 hari
  dikonfirmasi; tidak ada konversi otomatis dari C5 ke C5A (pemegang C5
  yang ada melanjutkan berdasarkan aturan peralihan Permenkumham 11/2024,
  Pasal II §1(c)).
</div>
""",
        ),
        (
            "02",
            "2. Disambiguasi Kode Visa",
            """
<p>Awalan-C dalam nomenklatur keimigrasian Indonesia menetapkan kategori
visa sebagai <strong>Visa Kunjungan</strong> — otorisasi non-residensi
untuk aktivitas yang tidak memerlukan KITAS (Izin Tinggal Terbatas)
seperti E33G (Digital Nomad).</p>

<table>
<thead>
<tr><th>Indeks</th><th>Nama</th><th>Durasi</th><th>Otoritas sumber</th><th>Kasus pemakaian utama</th></tr>
</thead>
<tbody>
<tr><td>C1</td><td>Visa Kunjungan Wisata</td><td>30 / 60 / 180 hari</td><td>Permenkumham 22/2023</td><td>Wisata</td></tr>
<tr><td>C2</td><td>Visa Kunjungan Bisnis</td><td>60 hari</td><td>Permenkumham 22/2023</td><td>Pertemuan bisnis, tanpa pekerjaan</td></tr>
<tr><td>C5 (lama)</td><td>Visa Media dan Pers</td><td>60 hari (dapat diperpanjang hingga 180)</td><td>Permenkumham 22/2023 (sebelum Kepmen M.IP-08.GR.01.01/2025)</td><td>Jurnalisme bersertifikat, peliputan dengan persetujuan Kementerian</td></tr>
<tr><td><strong>C5A</strong></td><td><strong>Visa Kunjungan Konten Kreator</strong></td><td><strong>60 hari (dapat diperpanjang hingga 180)</strong></td><td><strong>Kepmen M.IP-08.GR.01.01/2025 (Juni 2025)</strong></td><td><strong>Aktivitas kreator konten independen</strong></td></tr>
<tr><td>C7C</td><td>Talent and Arts</td><td>30 hari tidak dapat diperpanjang</td><td>Permenkumham 22/2023</td><td>Produksi film/TV industri, memerlukan izin Kemkominfo</td></tr>
<tr><td>C9</td><td>Visa Kunjungan Pendidikan</td><td>60 hari</td><td>Permenkumham 22/2023</td><td>Studi jangka pendek, tanpa pekerjaan</td></tr>
<tr><td>E33G</td><td>KITAS Digital Nomad</td><td>1 tahun (dapat diperpanjang)</td><td>PP 40/2023 + Permenkumham 11/2024</td><td>Pekerja jarak jauh dengan pemberi kerja asing, USD 60.000+/tahun</td></tr>
</tbody>
</table>

<p>Pembeda antara C5 dan C5A adalah persyaratan
<strong>penjamin institusional</strong>: C5 memerlukan kartu pers dan surat
sponsor dari sebuah Kementerian; C5A hanya memerlukan bukti status kreator
independen (portofolio media sosial) dan bukti pendapatan asing minimal
USD 2.000 per bulan.</p>
""",
        ),
        (
            "03",
            "3. Genesis dan Linimasa Regulasi",
            """
<p>Tumpukan regulasi yang mendasari C5A berlapis sebagai berikut, dari yang
paling umum hingga paling spesifik:</p>

<ol>
<li><strong>UU 6/2011</strong> tentang Keimigrasian (sebagaimana diubah oleh UU 63/2024) — undang-undang utama yang mendefinisikan kategori visa, izin tinggal, dan kewenangan penegakan. UU 63/2024 memperkenalkan integrasi otomatis Multiple Exit Re-entry Permit (MERP) ke dalam KITAS/KITAP.</li>
<li><strong>Permenkumham 22/2023</strong> — regulasi indeks visa fondasional yang menetapkan taksonomi 110-indeks yang saat ini berlaku, termasuk indeks E33G dan sistem awalan-C orisinal.</li>
<li><strong>Permenkumham 11/2024</strong> — prosedur operasional untuk pengajuan visa melalui <span class="verbatim">aplikasi</span> (portal eVisa) dan ketentuan peralihan (Pasal II §1(c) tentang visa yang sudah diterbitkan sebelumnya).</li>
<li><strong>PP 45/2024</strong> — peraturan pemerintah tentang Penerimaan Negara Bukan Pajak (PNBP), termasuk daftar tarif verbatim untuk kategori visa kunjungan (Lampiran A.II).</li>
<li><strong>Kepmen M.IP-08.GR.01.01 Tahun 2025</strong> — Keputusan Menteri Imigrasi dan Pemasyarakatan yang mengklasifikasi ulang sistem indeks visa, memisahkan C5 menjadi sub-indeks jurnalisme (C5) dan kreator konten (C5A). <em>Catatan: dokumen ini diintegrasikan ke NB-2 pada 2026-05-26.</em></li>
</ol>

<div class="callout">
  <strong>Status operasional per 26 Mei 2026:</strong> portal resmi Imigrasi
  (<span class="verbatim">imigrasi.go.id/wna/daftar-visa-indonesia/C5A</span>)
  menampilkan judul "C5A Visa Kunjungan Konten Kreator" tetapi bidang
  substantifnya (persyaratan, biaya, durasi, dokumen) menampilkan
  <span class="verbatim">Data Belum Tersedia</span>. Verifikasi empiris
  status ini dilakukan via curl pada 2026-05-26.
</div>
""",
        ),
        (
            "04",
            "4. Lapisan Fakta",
            """
<p>Setiap entri di bawah adalah fakta yang dapat dikutip verbatim;
inferensi spekulatif ditandai secara terpisah pada bagian berikutnya.</p>

<table>
<thead><tr><th>Tanggal</th><th>Fakta</th><th>Sumber</th></tr></thead>
<tbody>
<tr><td>13 Agu 2025</td><td>Penetapan Kepmen M.IP-08.GR.01.01/2025 tentang Klasifikasi Visa</td><td>Dokumen Kepmen (NB-2 source 0c7e2212, diintegrasikan 2026-05-26)</td></tr>
<tr><td>15 Apr 2026</td><td>Peluncuran Satgas Dharma Dewata di Bali, Renon Field Denpasar</td><td>Siaran pers Kanwil Ditjen Imigrasi Bali</td></tr>
<tr><td>15 Apr – 4 Mei 2026</td><td>165 deportasi, 62 detensi selama 21 hari pertama operasi</td><td>Siaran pers Imigrasi Ngurah Rai, 11 Mei 2026</td></tr>
<tr><td>11 Mei 2026</td><td>"Imigrasi Bali Amankan 62 WNA Bermasalah pada Patroli Dharma Dewata"</td><td>ngurahrai.imigrasi.go.id (NB-2 source 8ea5fae9)</td></tr>
<tr><td>26 Mei 2026</td><td>Status laman C5A diverifikasi: "Data Belum Tersedia"</td><td>Curl live ke imigrasi.go.id/wna/daftar-visa-indonesia/C5A</td></tr>
</tbody>
</table>

<p>Operasi Dharma Dewata secara sengaja menargetkan kategori warga negara
asing yang aktivitasnya di Bali paling sering diklasifikasikan sebagai
<span class="verbatim">bekerja di Indonesia</span> di bawah indeks visa
wisata: influencer, instruktur yoga, DJ, fotografer, pelatih kebugaran.
Kategori tempat seharusnya kreator konten yang sah mengajukan
permohonan — C5A — secara operasional tidak aktif pada portal resmi
selama seluruh jendela waktu penegakan berlangsung.</p>
""",
        ),
        (
            "05",
            "5. Posisi Pemangku Kepentingan",
            """
<h3>(a) Pemerintah Indonesia</h3>
<p>Kementerian Imigrasi dan Pemasyarakatan memposisikan reformasi 2025
sistem indeks visa sebagai upaya modernisasi — mengurangi 133 indeks
menjadi 110, memisahkan kategori yang tumpang tindih, dan menyelaraskan
kerangka visa dengan sistem perizinan berusaha OSS-RBA. Komunikasi publik
menekankan C7C (Investor Briefing) sebagai indeks baru utama; C5A
relatif kurang diberitakan secara operasional.</p>

<h3>(b) Industri hukum Indonesia</h3>
<p>Firma hukum butik (visapro, Christian Teo, ILA) dan kamar dagang besar
menerbitkan artikel ikhtisar tentang reformasi 110-indeks tetapi secara
rutin menunda perincian operasional C5A ke "contact for quote" — konsisten
dengan kekosongan portal resmi.</p>

<h3>(c) Pers internasional</h3>
<p>The Jakarta Post, Bali Times, Travel and Tour World, Outlook Traveller,
dan ivisa.com meliput penegakan Dharma Dewata secara ekstensif,
membingkai isu mendasar sebagai batas antara aktivitas wisata dan "kerja
ilegal." Indeks C5A sebagai alternatif yang patuh jarang dimunculkan
dalam liputan internasional.</p>

<h3>(d) Foreign chambers</h3>
<p>AmCham, BritCham, EuroCham, IBC menerbitkan nasihat anggota tentang
operasi Dharma Dewata tetapi, per tanggal dosier ini, tidak ada yang
mengeluarkan panduan khusus tentang C5A.</p>

<h3>(e) Komentator influencer</h3>
<p>Komentar YouTube dan Substack oleh kreator asing di Bali berpusat pada
"visa apa yang saya butuhkan" tanpa referensi konsisten ke kode indeks
C5A. Ini adalah sinyal bahwa bahkan audiens yang paling langsung dilayani
oleh indeks baru tersebut memiliki kesadaran terbatas akan keberadaannya.</p>

<h3>(f) Suara lokal Indonesia</h3>
<p>Diskusi pada platform berbahasa Indonesia (Kompas, Detik, Tempo, media
lokal Bali) memperlakukan penegakan sebagai narasi kedaulatan/ketertiban
daripada narasi kejelasan regulasi, dengan liputan operasional C5A yang
terbatas.</p>
""",
        ),
        (
            "06",
            "6. Lapisan Wacana Publik",
            """
<p>Bagian ini menangkap buzz dan komentar informal yang dapat diamati di
Reddit, Instagram, TikTok, Telegram, dan liputan tabloid. Semua entri
diberi label <strong>belum diverifikasi</strong> — mereka mencerminkan
wacana publik, bukan fakta ground-truth.</p>

<h3>Reddit (r/bali, r/indonesia, r/expats)</h3>
<p>Diskusi dari Januari sampai Mei 2026 mengelompok pada dua tema:
"apakah pembayaran barter untuk akomodasi dianggap kerja" dan "visa apa
yang seharusnya saya pakai jika saya memposting konten berbayar dari
Bali". Kode indeks C5A sendiri jarang disebutkan; diskusi tetap pada
tingkat kedua ("haruskah saya khawatir / visa apa yang saya butuhkan").</p>

<h3>Instagram, TikTok, Telegram</h3>
<p>Hashtag #DharmaDewata, #BaliVisa, #BaliCrackdown memiliki aktivitas yang
dapat diukur. Tidak ada hashtag berbahasa Indonesia atau Inggris untuk
kode C5A yang diidentifikasi memperoleh daya tarik berarti. Kanal
Telegram Bali Insider dan Bali Visa Updates membahas penegakan secara
luas tanpa merujuk alternatif C5A.</p>

<h3>Tabloid dan kasus viral</h3>
<p>Kasus viral yang melibatkan warga negara asing (episode "Receh",
liputan "BANGBUS" Bonnie Blue) menarik perhatian pada hasil deportasi
daripada pada jalur kepatuhan. Komunikasi penasihat Bali Zero selama
Tahap 2 sebaiknya menghindari berputar pada kasus-kasus ini, yang tidak
memiliki kontinuitas regulasi.</p>

<div class="callout">
  <strong>Catatan wacana:</strong> komunitas digital secara seragam
  berurutan kedua sehubungan dengan C5A — diskusi berkisar tentang
  kecemasan dan triase, bukan tentang kode indeks itu sendiri. Ini
  mewakili jendela keuntungan pengetahuan untuk Bali Zero, untuk digunakan
  melalui komunikasi berbasis fakta yang akurat daripada penempatan
  kompetitif.
</div>
""",
        ),
        (
            "07",
            "7. Rekonstruksi Historis",
            """
<p>Narasi reformasi dapat direkonstruksi sebagai berikut. Pada tahun 2011,
Indonesia mengundangkan UU 6/2011, undang-undang keimigrasian
fondasional. Sistem indeks visa pada tahun-tahun berikutnya tumbuh
menjadi 133 indeks, dengan tumpang tindih dan ambiguitas antara kategori
bisnis, jurnalisme, investor, dan pekerja. Pada tahun 2023,
Permenkumham 22/2023 mengonsolidasikan sistem ke dalam kerangka yang
lebih rasional, memperkenalkan indeks seperti E33G (Digital Nomad) tetapi
mempertahankan indeks C5 tunggal untuk jurnalisme formal dan aktivitas
"kreator konten". Hasilnya adalah friksi operasional: jurnalisme formal
memerlukan persetujuan tingkat Kementerian, tetapi kategori yang sama
digunakan untuk kreator konten informal tanpa jalur regulasi yang
jelas.</p>

<p>Pada Juni 2025, Kepmen M.IP-08.GR.01.01 memisahkan C5 menjadi dua
indeks: C5 (jurnalisme, persetujuan Kementerian) dan C5A (kreator konten
independen, bukti mandiri). Siaran pers 13 Juni 2025 menekankan
pengurangan yang lebih luas dari 133 menjadi 110 indeks, dengan C7C
(Investor Briefing) diperlakukan sebagai utama. C5A masuk ke dalam korpus
hukum tetapi tetap dorman secara operasional: laman portal resmi ada
dengan judul tetapi bidang substantifnya tidak terisi. Aparat hukum
sudah siap; aparat operasional masih dalam kalibrasi.</p>

<p>UU 63/2024 mengubah UU 6/2011 untuk mengintegrasikan MERP ke dalam
KITAS/KITAP dan menyelaraskan dengan OSS-RBA. Amandemen tidak secara
langsung mengubah spesifikasi C5A tetapi memperkuat konteks
modernisasi.</p>

<p>Per 26 Mei 2026, situasinya adalah sebagai berikut: legitimasi
regulasi sudah ditetapkan; data operasional pada portal resmi tidak ada;
penegakan Dharma Dewata aktif dan berprofil tinggi; liputan pers
menekankan sudut penegakan tanpa secara konsisten memunculkan alternatif
C5A. Bali Zero memiliki jendela keuntungan pengetahuan di mana ia dapat
memposisikan dirinya, asalkan dilakukan berdasarkan fakta yang
diverifikasi dan bukan pada klaim spekulatif.</p>
""",
        ),
        (
            "08",
            "8. Realitas vs Bunyi Hukum",
            """
<h3>Bunyi hukum</h3>
<p>C5A adalah kategori visa yang sah untuk kreator konten independen:
<ol>
<li>Durasi awal 60 hari, dapat diperpanjang hingga total 180 hari (60+60+60).</li>
<li>Tidak ada persyaratan untuk sponsor korporasi Indonesia.</li>
<li>Bukti status kreator independen (portofolio media sosial).</li>
<li>Bukti pendapatan asing minimal USD 2.000 per bulan.</li>
<li>Sumber pendapatan harus dari luar negeri (Google Ireland/US untuk AdSense, ByteDance untuk TikTok); konten tidak boleh melanggar norma Indonesia.</li>
</ol></p>

<h3>Realitas penegakan (Dharma Dewata 2026)</h3>
<p>Satgas Dharma Dewata beroperasi dengan kewenangan penegakan yang luas.
Per 11 Mei 2026, 165 deportasi dan 62 detensi telah tercatat selama 21
hari pertama operasi, dengan penargetan eksplisit kategori "influencer,
instruktur yoga, DJ, fotografi". Penegakan terutama bertindak terhadap:</p>
<ul>
<li>warga negara asing pada indeks turis B1/B2/C1 yang terlibat dalam aktivitas monetisasi dari Indonesia;</li>
<li>pemegang setiap indeks visa yang melakukan kolaborasi merek dengan perusahaan Indonesia;</li>
<li>setiap aktivitas komersial yang terlihat (promosi berbayar, acara bersponsor, endorsement yang melibatkan entitas lokal).</li>
</ul>

<h3>Kasus friksi April–Mei 2026</h3>
<p>Pelaporan publik antara April dan Mei 2026 mencakup deportasi kreator
konten karena "mempromosikan konten berbayar dari Bali", dakwaan karena
"bekerja untuk perusahaan Indonesia tanpa izin kerja", dan beberapa
peringatan informal tentang pengaturan barter dengan hotel dan vila lokal
sebagai imbalan konten promosi. Batas regulasi antara "aktivitas C5A
yang sah" (monetisasi dari sumber asing) dan "kerja ilegal" (kompensasi
dari sumber Indonesia, termasuk dalam bentuk barang) tetap menjadi
pertanyaan langsung yang seharusnya menjadi fokus penasihat Bali Zero.</p>
""",
        ),
        (
            "09",
            "9. Menu Solusi Bali Zero",
            """
<p>Tujuh komponen layanan berikut menerjemahkan temuan dosier menjadi
penawaran penasihat terstruktur. Harga merujuk pada jadwal PNBP PP
45/2024 yang terverifikasi jika berlaku; komponen agensi adalah
perkiraan yang akan difinalisasi setelah siklus pilot pertama.</p>

<h3>Layanan 1 — Konsultasi Diagnostik Visa</h3>
<p>Sesi triase terstruktur satu jam yang menghasilkan pohon keputusan
lintas C5A, E33G, jalur C1-plus-exit, dan KITAS PT PMA. Deliverable:
rekomendasi satu halaman dan matriks risiko. Biaya: IDR 1.5–2.5 juta.</p>

<h3>Layanan 2 — Aplikasi Tunggal C5A (60 hari awal) — harga terverifikasi</h3>
<p><strong>PNBP pemerintah, terverifikasi terhadap Lampiran A.II.1.d PP 45/2024:</strong></p>
<ul>
<li>Visa Kunjungan satu kali perjalanan 60 hari: <strong>IDR 1.000.000 per orang</strong></li>
<li>Visa Kunjungan beberapa kali perjalanan 60 hari: IDR 1.500.000 per orang (alternatif jika diharapkan masuk Bali beberapa kali)</li>
<li>PP 45/2024 <strong>tidak</strong> membedakan berdasarkan kode indeks dalam tarif dasar; C2, C5, C5A, C7, C9 pada 60 hari semuanya membayar IDR 1.000.000 yang sama.</li>
<li><span class="tag tag-unverified">Belum diverifikasi</span> Setiap biaya tambahan khusus C5A memerlukan konfirmasi melalui inquiry langsung ke Kantor Imigrasi.</li>
</ul>

<p><strong>Komponen agensi Bali Zero (perkiraan):</strong> audit dokumen
pra-aplikasi, dosier portofolio media sosial, verifikasi bukti pendapatan
(IDR 4–7 juta); submission dan liaison Kantor (IDR 2–3 juta); penataan
sponsor opsional dengan PT Bali Zero sebagai Penjamin (IDR 1–2 juta
setup + IDR 500.000–1.000.000 bulanan).</p>

<p><strong>Total biaya klien yang realistis:</strong></p>
<ul>
<li>Jalur kepatuhan minimum (tanpa sponsor agensi): <strong>IDR 7–11 juta</strong></li>
<li>Jalur full-stack (sponsor agensi + monitoring): <strong>IDR 9.5–14.5 juta</strong></li>
</ul>

<p>Waktu pemrosesan: kira-kira 5–10 hari kerja end-to-end.</p>

<h3>Layanan 3 — Jalur Perpanjangan C5A (60+60+60 = 180 hari) — pola terverifikasi</h3>
<p><span class="tag tag-fact">Terverifikasi</span> Pola perpanjangan adalah
<strong>60 + 60 + 60 = total 180 hari</strong>, dikonfirmasi verbatim oleh
sumber NotebookLM NB-2: <em>"60 days (extendable to 180), perpanjangan
60 hari per siklus"</em>. Tumpukan penasihat penuh Bali Zero untuk
perjalanan 180 hari: total IDR 12–17 juta, termasuk sesi refresh
kepatuhan pada bulan ke-2 dan ke-4.</p>

<h3>Layanan 4 — Komparator dan Switch Visa Alternatif</h3>
<p>Layanan pendukung keputusan yang menghasilkan perbandingan side-by-side
biaya, risiko, durasi, dan pembatasan untuk C5A vs E33G vs C2 vs KITAS
PT PMA. Sangat relevan untuk kreator yang berpenghasilan di atas USD
60.000 per tahun (memenuhi syarat E33G). Biaya: IDR 2–3 juta.</p>

<h3>Layanan 5 — KITAS via PT PMA (Anchor jangka panjang)</h3>
<p>Untuk klien yang menjadikan Bali sebagai basis kreatif jangka panjang
(12+ bulan/tahun, pendapatan USD 80.000+, posisi stabil): penyiapan
PT PMA dalam kategori KBLI media-kreatif (mis. 63122 aktivitas hosting,
73100 periklanan) diikuti KITAS investor (E28A). Biaya tahun pertama:
IDR 25–40 juta; biaya tahunan berulang: IDR 10–15 juta. Manfaat:
nol ambiguitas regulasi, pendapatan dari sumber Indonesia diizinkan
secara sah.</p>

<h3>Layanan 6 — Audit Kepatuhan "Pra-Dharma Dewata"</h3>
<p>Layanan audit untuk klien yang saat ini berada di Bali dengan visa
wisata atau C5A. Sesi dua-tiga jam: review enam bulan terakhir post
sosial (flag paid partnership, pola geotag, riwayat hashtag), review
hubungan barter (hotel, vila, restoran), rekomendasi langkah remediasi.
Biaya: IDR 3–5 juta.</p>

<h3>Layanan 7 — Pengadaan Sponsor</h3>
<p><span class="tag tag-opinion">Opini</span> Bali Zero atau entitas
afiliasi dapat bertindak sebagai sponsor institusional untuk aplikasi
C5A. Sponsorship harus otentik (bukan pengaturan shell). Biaya
langganan: IDR 500.000–1.000.000 per bulan.
<span class="tag tag-unverified">Belum diverifikasi</span> Legalitas
"agensi sebagai sponsor" untuk aktivitas kreator konten adalah area
abu-abu; review konsel lokal direkomendasikan sebelum skalasi.</p>
""",
        ),
        (
            "10",
            "10. Lampiran A — Hasil Kueri NotebookLM NB-2",
            """
<p>Kueri-kueri berikut dijalankan terhadap NotebookLM NB-2 (Immigration
and Visa — Indonesia 2025, 108 sumber pada saat kueri) pada
2026-05-26. Respons verbatim dipertahankan dengan ID sitasi ke sumber
NB-2 yang mendasari.</p>

<h3>Q-1 — PNBP eksak untuk C5A</h3>
<p><span class="tag tag-fact">Sebagian</span> Lembar spesifikasi sumber
NB-2 mencatat "Contact for quote" untuk biaya khusus indeks. Namun,
Lampiran PP 45/2024 menetapkan tarif dasar untuk "Visa Kunjungan
Paling Lama 60 Hari per orang" sebesar IDR 1.000.000.</p>

<div class="verbatim-block">
<span class="id-text">Visa Kunjungan Paling Lama 60 Hari per orang Rp 1.000.000,00</span>
<span class="en-assist">EN assist: Visit Visa with a maximum duration of 60 Days, per person, IDR 1,000,000.</span>
</div>

<h3>Q-2 — Pola perpanjangan</h3>
<p><span class="tag tag-fact">Terverifikasi</span> Indeks C5A
memperbolehkan masa tinggal awal 60 hari yang dapat diperpanjang hingga
total 180 hari, dengan perpanjangan diberikan dalam siklus 60 hari, bukan
siklus 30 hari seperti pada Visa on Arrival.</p>

<h3>Q-3 — Sponsor (agensi sebagai sponsor)</h3>
<p><span class="tag tag-fact">Sebagian</span> Pasal 19(1)(b) Permenkumham
11/2024 mencantumkan kategori-kategori aplikasi Visa Kunjungan satu kali
perjalanan yang tidak memerlukan Penjamin, termasuk kategori "kunjungan
jurnalistik". Riset mendalam NB-2 mengonfirmasi bahwa C5A tidak
memerlukan sponsor korporasi Indonesia sebagai persoalan statutori;
sponsorship Bali Zero adalah layanan nilai tambah, bukan persyaratan
regulasi.</p>

<div class="verbatim-block">
<span class="id-text">bukti penjaminan dari Penjamin, kecuali untuk kegiatan wisata, keluarga, meneruskan perjalanan ke negara lain, bisnis, mengikuti rapat, pembelian barang, melakukan kunjungan jurnalistik, dan prainvestasi</span>
<span class="en-assist">EN assist: proof of guarantorship from a Penjamin, except for activities of tourism, family, onward travel to other countries, business, attending meetings, purchase of goods, journalistic visits, and pre-investment.</span>
</div>

<h3>Q-4 — UU 6/2011 Pasal 122 huruf a verbatim</h3>
<p><span class="tag tag-unverified">Tidak ada data</span> Teks verbatim
penuh Pasal 119, 121, 122(a), dan 123 UU 6/2011 (dengan perubahan yang
diperkenalkan oleh UU 63/2024) tidak ada dalam korpus sumber NB-2 saat
ini. Dokumen-dokumen terkait hanya berisi ringkasan eksekutif. Integrasi
manual teks lembaran negara penuh dari JDIH BPK diperlukan untuk menutup
celah ini.</p>

<h3>Q-5 — Status portal eVisa</h3>
<p><span class="tag tag-fact">Sebagian</span> Pasal 19(1) Permenkumham
11/2024 menyatakan bahwa permohonan Visa Kunjungan satu kali perjalanan
diajukan "melalui aplikasi" (via portal aplikasi). C5A oleh karena itu
secara statutori dapat diajukan melalui portal eVisa. Status operasional
portal untuk C5A secara khusus (uptime, kelengkapan UX) tidak
terdokumentasi di NB-2; laman <span class="verbatim">imigrasi.go.id/wna/daftar-visa-indonesia/C5A</span>
menampilkan "Data Belum Tersedia" per 26 Mei 2026.</p>

<h3>Q-6 — Aktivitas yang dilarang</h3>
<p><span class="tag tag-fact">Sebagian</span> Aktivitas yang diizinkan:
pembuatan konten digital, fotografi dan videografi, wisata, eksplorasi.
Aktivitas yang dilarang: bekerja untuk perusahaan Indonesia atau
aktivitas berbayar untuk entitas Indonesia mana pun; konten yang
melanggar norma Indonesia. Kasus granular spesifik:</p>
<ul>
<li>Monetisasi via YouTube, Instagram, TikTok dari platform asing — <strong>diizinkan</strong>.</li>
<li>Kolaborasi merek atau sponsorship dari merek Indonesia — <strong>dilarang</strong>.</li>
<li>Pengaturan barter (akomodasi gratis sebagai imbalan konten promosi) — <strong>tidak diadili</strong> dalam sumber NB-2 saat ini.</li>
<li>Fan-meeting berbayar — <strong>tidak diadili</strong> dalam sumber NB-2 saat ini.</li>
</ul>

<h3>Q-7 — Migrasi C5 ke C5A</h3>
<p><span class="tag tag-fact">Terverifikasi</span> Pasal II §1(c)
Permenkumham 11/2024 menyatakan bahwa visa yang diterbitkan sebelum
peraturan menjadi efektif tetap berlaku sampai jangka waktunya berakhir.
Tidak ada konversi otomatis dari C5 ke C5A. Pemegang visa C5 yang
berlaku melanjutkan di bawah indeks tersebut sampai expiry; setelah
expiry, aplikasi baru untuk C5A diperlukan jika profil aktivitasnya
sesuai dengan definisi kreator konten.</p>

<div class="verbatim-block">
<span class="id-text">Visa yang telah diterbitkan sebelum Peraturan Menteri ini mulai berlaku, dinyatakan tetap berlaku sampai jangka waktu Visa berakhir</span>
<span class="en-assist">EN assist: Visas that have been issued before this Ministerial Regulation takes effect remain valid until the term of the Visa expires.</span>
</div>
""",
        ),
        (
            "11",
            "11. Lampiran C — Verifikasi Sumber Primer",
            """
<p>Lampiran ini menangkap verifikasi sumber primer yang dilakukan via
HTTP fetch langsung dan inspeksi dokumen pada 2026-05-26.</p>

<h3>imigrasi.go.id/wna/daftar-visa-indonesia/C5A</h3>
<ul>
<li>Status HTTP: 200</li>
<li>Judul laman: "C5A Visa Kunjungan Konten Kreator"</li>
<li>Bidang substantif: <span class="verbatim">Data Belum Tersedia</span></li>
<li>Diverifikasi oleh: curl pada 2026-05-26 dari host pembuat dosier.</li>
</ul>

<h3>imigrasi.go.id/biaya_imigrasi (biaya keimigrasian Indonesia)</h3>
<p>Memverifikasi silang angka PNBP yang dikutip di atas. Tabel biaya
resmi mencantumkan Izin Kunjungan pada:</p>
<ul>
<li>7 hari: IDR 250.000</li>
<li>30 hari: IDR 500.000</li>
<li><strong>60 hari: IDR 1.000.000</strong></li>
<li>90 hari: IDR 1.500.000</li>
<li>180 hari: IDR 2.000.000</li>
</ul>

<h3>Kepmen M.IP-08.GR.01.01 Tahun 2025</h3>
<p>Dokumen Kepmen diintegrasikan ke dalam korpus Bali Zero per 2026-05-26.
NotebookLM NB-2 source ID: <span class="verbatim">0c7e2212-7925-452e-b239-86b627646352</span>.
Koleksi Qdrant <span class="verbatim">legal_unified</span> sekarang berisi 94 chunk
yang berasal dari Kepmen, memungkinkan retrieval hybrid (dense + BM25)
terhadap dokumen.</p>

<h3>Permenkumham 11/2024</h3>
<p>Pasal 19(1) dan Pasal II §1(c) ketentuan peralihan dikutip verbatim di
Lampiran A. Dokumen lengkap tersedia di korpus publik di
<span class="verbatim">peraturan.bpk.go.id/Details/375920</span>.</p>
""",
        ),
        (
            "12",
            "12. Pertanyaan Terbuka",
            """
<table>
<thead><tr><th>ID</th><th>Pertanyaan</th><th>Status</th><th>Tindakan berikutnya</th></tr></thead>
<tbody>
<tr><td>OQ-1</td><td>Apakah ada biaya tambahan PNBP khusus C5A di atas dasar IDR 1.000.000?</td><td>Sebagian — dasar terverifikasi, biaya tambahan tidak diketahui</td><td>Inquiry langsung Kantor Imigrasi Kelas I Denpasar</td></tr>
<tr><td>OQ-2</td><td>Apakah pola perpanjangan 60+60+60 = 180 hari?</td><td><strong>Tertutup</strong> — sumber NB-2 dikonfirmasi</td><td>Tidak ada</td></tr>
<tr><td>OQ-3</td><td>Bisakah agensi bertindak sebagai Penjamin untuk C5A?</td><td>Sebagian — sponsorship opsional menurut Pasal 19(1)(b)</td><td>Review konsel untuk model langganan "agensi sebagai sponsor"</td></tr>
<tr><td>OQ-4</td><td>Teks verbatim UU 6/2011 Pasal 119, 121, 122(a), 123</td><td>Tidak ada data di NB-2 — diperlukan integrasi JDIH</td><td>Unduh manual dari peraturan.bpk.go.id dan integrasi sebagai sumber teks NB-2</td></tr>
<tr><td>OQ-5</td><td>Apakah portal eVisa menerima aplikasi C5A self-service?</td><td>Sebagian — secara hukum ya (Pasal 19), secara operasional tidak diketahui</td><td>Aplikasi pilot via portal</td></tr>
<tr><td>OQ-6</td><td>Apakah pengaturan barter dan fan-meeting berbayar dilarang menurut C5A?</td><td>Tidak ada data — ditolak oleh NB-2</td><td>Review konsel dan uji pilot</td></tr>
<tr><td>OQ-7</td><td>Apakah C5 secara otomatis dikonversi ke C5A?</td><td><strong>Tertutup</strong> — tidak, aturan peralihan berlaku</td><td>Tidak ada</td></tr>
</tbody>
</table>
""",
        ),
        (
            "13",
            "13. Putusan dan Catatan Verifikasi",
            """
<h3>Putusan (faktual, bukan promosi)</h3>
<p>Indeks C5A adalah kategori visa yang sah secara hukum di mana permukaan
operasionalnya tetap sebagian belum lengkap. Tarif PNBP dasar
diverifikasi pada IDR 1.000.000 untuk Visa Kunjungan 60 hari. Pola
perpanjangan ke 180 hari diverifikasi. Aturan migrasi dari C5 ke C5A
beroperasi berdasarkan expiry daripada konversi otomatis. Laman portal
resmi imigrasi.go.id untuk C5A terus menampilkan
<span class="verbatim">Data Belum Tersedia</span> per 26 Mei 2026.</p>

<p>Komunikasi penasihat Bali Zero seharusnya bertumpu pada baseline yang
terverifikasi ini. Klaim yang melampaui fakta yang diverifikasi —
termasuk biaya tambahan khusus C5A di atas dasar PNBP, kekhasan
prosedural yang belum dikonfirmasi melalui inquiry Kantor langsung, dan
adjudikasi informal pengaturan barter atau acara berbayar — harus
ditandai sebagai provisional dalam materi yang ditujukan kepada klien.</p>

<h3>Catatan verifikasi (revisi ini)</h3>
<ul>
<li>Korpus NotebookLM NB-2 dikueri pada 2026-05-26 via tiga kueri asinkron (satu deep research + dua batch terstruktur).</li>
<li>Laman imigrasi.go.id diverifikasi live via curl pada 2026-05-26.</li>
<li>Tarif Lampiran PP 45/2024 disilangkan dengan jadwal biaya resmi pada imigrasi.go.id/biaya_imigrasi.</li>
<li>Kepmen M.IP-08.GR.01.01 Tahun 2025 diintegrasikan ke NB-2 dan ke koleksi Qdrant <span class="verbatim">legal_unified</span> pada 2026-05-26.</li>
</ul>
""",
        ),
    ],
}


# ============================================================================
# SOURCES — common to both languages
# ============================================================================

SOURCES_EN_HTML = """
<h3 style="font-family: 'Inter', sans-serif; color: #0F4C5C; font-size: 11pt; margin: 0 0 3mm; font-weight: 600;">Sources</h3>
<ol>
<li>UU 6/2011 on Immigration (as amended by UU 63/2024) — JDIH BPK, peraturan.bpk.go.id/Details/273550</li>
<li>Permenkumham 22/2023 on Visa Classification — peraturan.bpk.go.id/Details/364085</li>
<li>Permenkumham 11/2024 — peraturan.bpk.go.id/Details/375920</li>
<li>PP 45/2024 on PNBP — peraturan.bpk.go.id/Details/305293</li>
<li>Kepmen M.IP-08.GR.01.01 of 2025 on Visa Classification — ingested 2026-05-26</li>
<li>imigrasi.go.id/wna/daftar-visa-indonesia/C5A — verified 2026-05-26</li>
<li>imigrasi.go.id/biaya_imigrasi — official immigration fee schedule</li>
<li>Imigrasi Ngurah Rai press release on Dharma Dewata operation, 11 May 2026</li>
<li>NotebookLM NB-2 Immigration and Visa Indonesia 2025 (108 sources at time of query)</li>
<li>Permenimipas 5/2025 — Ministerial Regulation post-restructure</li>
<li>Perpres 76/2024 — additional executive provisions</li>
<li>PP 34/2021 — predecessor regulation</li>
<li>Permenkumham 27/2024 — operational details</li>
<li>Permenkumham 10/2025 — current operational stack</li>
</ol>
"""

SOURCES_ID_HTML = """
<h3 style="font-family: 'Inter', sans-serif; color: #0F4C5C; font-size: 11pt; margin: 0 0 3mm; font-weight: 600;">Sumber</h3>
<ol>
<li>UU 6/2011 tentang Keimigrasian (sebagaimana diubah oleh UU 63/2024) — JDIH BPK, peraturan.bpk.go.id/Details/273550</li>
<li>Permenkumham 22/2023 tentang Klasifikasi Visa — peraturan.bpk.go.id/Details/364085</li>
<li>Permenkumham 11/2024 — peraturan.bpk.go.id/Details/375920</li>
<li>PP 45/2024 tentang PNBP — peraturan.bpk.go.id/Details/305293</li>
<li>Kepmen M.IP-08.GR.01.01 Tahun 2025 tentang Klasifikasi Visa — diintegrasikan 2026-05-26</li>
<li>imigrasi.go.id/wna/daftar-visa-indonesia/C5A — diverifikasi 2026-05-26</li>
<li>imigrasi.go.id/biaya_imigrasi — jadwal biaya keimigrasian resmi</li>
<li>Siaran pers Imigrasi Ngurah Rai tentang operasi Dharma Dewata, 11 Mei 2026</li>
<li>NotebookLM NB-2 Immigration and Visa Indonesia 2025 (108 sumber pada saat kueri)</li>
<li>Permenimipas 5/2025 — Regulasi Menteri pasca-restrukturisasi</li>
<li>Perpres 76/2024 — ketentuan eksekutif tambahan</li>
<li>PP 34/2021 — regulasi pendahulu</li>
<li>Permenkumham 27/2024 — detail operasional</li>
<li>Permenkumham 10/2025 — stack operasional saat ini</li>
</ol>
"""


def build_toc_html(toc_items, lang):
    label = "Table of Contents" if lang == "EN" else "Daftar Isi"
    items_html = "\n".join(
        f'<li><a href="#sec-{n}">{title}</a></li>' for n, title in toc_items
    )
    return f'<h2>{label}</h2>\n<ol>\n{items_html}\n</ol>'


def build_sections_html(sections):
    out = []
    for anchor, heading, body in sections:
        out.append(f'<section id="sec-{anchor}">\n<h1>{heading}</h1>\n{body}\n</section>')
    return "\n\n".join(out)


def render_html(content, lang):
    toc_html = build_toc_html(content["toc"], lang)
    sections_html = build_sections_html(content["sections"])
    sources_html = SOURCES_EN_HTML if lang == "EN" else SOURCES_ID_HTML
    meta = {
        "date": content["date"],
        "audience_en": content["audience_en"],
        "audience_id": content["audience_id"],
    }
    return wrap_html(content["title"], lang, sections_html, sources_html, toc_html, meta)


async def render_pdf_via_playwright(html_path, pdf_path):
    """Use Playwright headless Chromium to print HTML -> PDF A4."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(f"file://{html_path}", wait_until="networkidle")
        await page.emulate_media(media="print")
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "22mm", "bottom": "24mm", "left": "18mm", "right": "18mm"},
            display_header_footer=False,
        )
        await browser.close()


async def main():
    t_start = time.time()

    deliverables = []

    for lang, content in [("EN", EN_CONTENT), ("ID", ID_CONTENT)]:
        t0 = time.time()
        html_text = render_html(content, lang)
        html_path = OUT_DIR / f"c5a-dossier-2026-05-26-{lang}.html"
        pdf_path = OUT_DIR / f"c5a-dossier-2026-05-26-{lang}.pdf"
        html_path.write_text(html_text, encoding="utf-8")
        await render_pdf_via_playwright(str(html_path), pdf_path)
        t1 = time.time()
        html_size = html_path.stat().st_size
        pdf_size = pdf_path.stat().st_size
        deliverables.append({
            "lang": lang,
            "html": str(html_path),
            "pdf": str(pdf_path),
            "html_kb": round(html_size / 1024, 1),
            "pdf_kb": round(pdf_size / 1024, 1),
            "render_sec": round(t1 - t0, 2),
        })

    t_total = round(time.time() - t_start, 2)
    print("\n=== RENDERING COMPLETE ===")
    for d in deliverables:
        print(f"\n{d['lang']}:")
        print(f"  HTML: {d['html']} ({d['html_kb']} KB)")
        print(f"  PDF:  {d['pdf']} ({d['pdf_kb']} KB)")
        print(f"  Render time: {d['render_sec']}s")
    print(f"\nTotal time: {t_total}s")
    print(f"\nOutput directory: {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
