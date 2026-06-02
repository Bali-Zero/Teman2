#!/usr/bin/env python3
"""Render the official Bali Zero visa-guidance document for Marc Buckner to PDF.
Brand: antracite #2C2F38, accent yellow #F4C430, status red #C8102E, Montserrat.
Logo: bali-zero-brand cortex circle 400 (base64 inline)."""
import base64
import pathlib

BRAND = pathlib.Path.home() / ".claude/skills/bali-zero-brand/surfaces/internal-print-a4/assets"
OUT_DIR = pathlib.Path.home() / "Desktop/nuzantara/research/visa/clients"
LOGO_PNG = BRAND / "balizero_logo_circle_400.png"

logo_b64 = base64.b64encode(LOGO_PNG.read_bytes()).decode()
logo_data_uri = f"data:image/png;base64,{logo_b64}"

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: A4; margin: 0; }}
body {{ font-family:'Montserrat','Inter',sans-serif; color:#2C2F38; background:#fff; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:210mm; min-height:297mm; padding:16mm 17mm 14mm; position:relative; page-break-after:always; }}
.page.last {{ page-break-after:auto; min-height:0; }}

.header {{ display:flex; align-items:center; gap:16px; border-bottom:3px solid #F4C430; padding-bottom:14px; margin-bottom:20px; }}
.header img {{ width:60px; height:60px; }}
.header .brand {{ font-weight:800; font-size:22px; letter-spacing:.04em; color:#2C2F38; }}
.header .brand span {{ color:#C8102E; }}
.header .tag {{ font-size:10.5px; color:#6b7280; letter-spacing:.12em; text-transform:uppercase; margin-top:2px; }}
.header .meta {{ margin-left:auto; text-align:right; font-size:10px; color:#6b7280; line-height:1.5; }}

h1 {{ font-size:26px; font-weight:800; letter-spacing:.01em; line-height:1.15; margin-bottom:6px; }}
.subtitle {{ font-size:13px; color:#6b7280; font-weight:600; margin-bottom:18px; }}
.greeting {{ font-size:12.5px; line-height:1.6; margin-bottom:16px; }}

h2 {{ font-size:15px; font-weight:800; color:#2C2F38; margin:14px 0 8px; padding-left:12px; border-left:4px solid #F4C430; letter-spacing:.01em; }}
p {{ font-size:11.5px; line-height:1.58; margin-bottom:8px; }}
.lead {{ font-size:12px; }}

.box {{ border-radius:8px; padding:12px 15px; margin:10px 0; font-size:11px; line-height:1.55; }}
.box-clean {{ background:#f0f7f0; border-left:4px solid #2e7d32; }}
.box-warn {{ background:#fdf6e3; border-left:4px solid #F4C430; }}
.box-stop {{ background:#fdeaec; border-left:4px solid #C8102E; }}
.box .label {{ font-weight:800; font-size:10px; letter-spacing:.08em; text-transform:uppercase; display:block; margin-bottom:5px; }}
.box-clean .label {{ color:#2e7d32; }}
.box-warn .label {{ color:#b8860b; }}
.box-stop .label {{ color:#C8102E; }}

table.opt {{ width:100%; border-collapse:collapse; margin:10px 0; font-size:10.5px; }}
table.opt th {{ background:#2C2F38; color:#fff; text-align:left; padding:8px 11px; font-weight:700; font-size:10px; letter-spacing:.03em; }}
table.opt td {{ padding:7px 11px; border-bottom:1px solid #e5e7eb; vertical-align:top; line-height:1.45; }}
table.opt tr:nth-child(even) td {{ background:#fafafa; }}
.yes {{ color:#2e7d32; font-weight:700; }}

.regbox {{ font-family:'IBM Plex Mono',monospace; font-size:9.5px; background:#2C2F38; color:#e8e8e8; border-radius:6px; padding:10px 14px; margin:8px 0; line-height:1.5; }}
.regbox .k {{ color:#F4C430; }}

.req {{ background:#f7f8fa; border:1px solid #e5e7eb; border-radius:8px; padding:11px 18px; margin:8px 0; }}
.req ol {{ counter-reset:step; list-style:none; padding:0; }}
.req ol li {{ counter-increment:step; font-size:11.5px; line-height:1.55; margin-bottom:6px; list-style:none; padding-left:22px; position:relative; }}
.req ol li::before {{ content:counter(step)'.'; color:#2C2F38; font-weight:800; position:absolute; left:0; }}

.footer {{ position:absolute; bottom:11mm; left:17mm; right:17mm; border-top:1px solid #e5e7eb; padding-top:10px; display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace; font-size:8.5px; color:#9CA3AF; letter-spacing:.02em; }}
.footer-flow {{ margin-top:10px; border-top:1px solid #e5e7eb; padding-top:8px; display:flex; justify-content:space-between; font-family:'IBM Plex Mono',monospace; font-size:8.5px; color:#9CA3AF; letter-spacing:.02em; }}
.disclaimer {{ font-size:8.8px; color:#6b7280; line-height:1.48; font-style:italic; border-top:1px dashed #d1d5db; padding-top:9px; margin-top:10px; }}
.sign {{ margin-top:12px; font-size:11.5px; line-height:1.55; }}
.sign .name {{ font-weight:800; color:#2C2F38; }}
</style></head><body>

<!-- PAGE 1 -->
<div class="page">
  <div class="header">
    <img src="{logo_data_uri}" alt="Bali Zero">
    <div>
      <div class="brand">BALI <span>ZERO</span></div>
      <div class="tag">Immigration · Company · Tax · Property — Indonesia</div>
    </div>
    <div class="meta">
      Confidential client guidance<br>
      Prepared: 31 May 2026<br>
      For: Marc Buckner (@marcbuckner)
    </div>
  </div>

  <h1>Visa Guidance for Content Creation in Bali</h1>
  <div class="subtitle">3-month stay · June–September 2026 · South African content creator</div>

  <p class="greeting lead">Dear Marc,<br><br>
  Thank you for the detail you shared — it allows us to give you a precise answer based on the
  actual Indonesian immigration regulation (the 2025 visa classification decree, cited verbatim
  in this document), not generic guidance. We would rather be straight with you than recommend
  the wrong route.</p>

  <h2>First: clearing one misconception</h2>

  <div class="box box-warn">
    <span class="label">⚠ The C7 visa is the wrong category</span>
    The C7 / C7C is the <em>Arts &amp; Culture</em> visit visa (performances, cultural skills, demonstrations).
    It does not match travel / lifestyle / fitness content creation, so we will not place you under a category
    that does not reflect your actual activity — that creates exposure for you, not protection.
  </div>

  <h2>The honest answer: today there is no clean visa for your exact profile</h2>
  <p>We will not sell you the wrong permit to close a deal. Here is the real picture for a
  <strong>global freelance creator</strong> — someone who earns from scattered brand deals,
  AdSense and collaborations rather than from one fixed employer:</p>

  <div class="box box-warn">
    <span class="label">→ The category built for you is the C5A — but it is not operational</span>
    Indonesia did create a dedicated visa for exactly your case: the <strong>C5A "Content Creator"</strong>
    visit visa. The problem is that it exists only on paper — it is not selectable on the eVisa portal,
    has no implementing guidance, and its detail page has read "Data Belum Tersedia" for over 11 months.
    Right now it cannot be applied for, and there is no firm timeline.
  </div>

  <div class="box box-stop">
    <span class="label">✕ The E33G "Remote Worker" visa is not your category</span>
    Some agencies will offer you the E33G. Be careful: the regulation requires a genuine
    <strong>employment / service contract with a company based outside Indonesia</strong> (a "hubungan
    kerja"). It is built for the person who works remotely for one defined foreign employer — not for a
    global influencer living on assorted brand deals. This is precisely <strong>why the government created
    the C5A as a separate category</strong>. Forcing your profile onto an E33G is a stretch, not a clean fit.
  </div>

  <div class="footer">
    <span>BALI ZERO — zantara@balizero.com</span>
    <span>Visa guidance · Marc Buckner · 2026-05-31 · p. 1/2</span>
  </div>
</div>

<!-- PAGE 2 -->
<div class="page last">
  <div class="header">
    <img src="{logo_data_uri}" alt="Bali Zero">
    <div>
      <div class="brand">BALI <span>ZERO</span></div>
      <div class="tag">Immigration · Company · Tax · Property — Indonesia</div>
    </div>
    <div class="meta">
      Confidential client guidance<br>
      Prepared: 31 May 2026<br>
      For: Marc Buckner (@marcbuckner)
    </div>
  </div>

  <h2>Your real options today</h2>
  <table class="opt">
    <tr><th>Option</th><th>What it means</th><th>Reality</th></tr>
    <tr>
      <td><strong>1. Wait for the C5A</strong></td>
      <td>The visa actually designed for you. Monitor for it becoming operational.</td>
      <td>No firm timeline — estimates 3–6 months, uncertain.</td>
    </tr>
    <tr>
      <td><strong>2. Visit as a tourist, do not monetise in Indonesia</strong></td>
      <td>Come on a tourist visa, enjoy Bali, post as a private traveller.</td>
      <td>No barter, no brand work tied to Indonesian businesses. Limits what you came to do.</td>
    </tr>
    <tr>
      <td><strong>3. Build a real structure</strong></td>
      <td>If your income has a contractable backbone, or you want an ongoing presence.</td>
      <td>Worth assessing case-by-case — this is the conversation below.</td>
    </tr>
  </table>

  <div class="box box-stop">
    <span class="label">✕ One thing is illegal on every visa: barter with Bali businesses</span>
    Collaborating with Bali hotels, resorts or gyms <strong>in exchange for accommodation, services or
    exposure</strong> is treated by law as work for an Indonesian beneficiary — even with no money involved.
    <strong>"I'm not getting paid" is not a defence.</strong> This is exactly what the "Operasi Dharma Dewata"
    task force has been deporting foreigners for since April 2026 (62 detained in the first three weeks,
    influencers included), with re-entry bans of 5 years, 10 years, or life. Whatever route you take, this
    stays off the table.
  </div>

  <div class="box box-warn">
    <span class="label">⚠ A word of caution on the "easy E33G" pitch</span>
    If another agency tells you the E33G is a simple yes for an influencer, ask them to show you the foreign
    <strong>employment contract</strong> the regulation requires. A genuine, contractable relationship with a
    foreign company can sometimes qualify — but a loose set of brand deals usually does not, and a forced
    application is a risk we will not put your name on.
  </div>

  <h2>What we propose</h2>
  <p class="lead">A short consultation. We will look at how your income is actually structured — whether any
  part of it is contractable enough to open a legitimate route — and we will keep you informed the moment the
  C5A becomes applicable. Either way, you get the honest answer, not the convenient one.</p>

  <div class="sign">
    Tell us how your brand work is invoiced and we will map the realistic options, with cost and timeline,
    in writing.<br>
    Warm regards,<br>
    <span class="name">Bali Zero</span> &nbsp;·&nbsp;
    <span style="color:#6b7280;font-size:10px;">zantara@balizero.com</span>
  </div>

  <div class="disclaimer">
    Preliminary guidance based on Indonesian immigration regulation in force as of 31 May 2026
    (Kepmen M.IP-08.GR.01.01/2025; Permenkumham 11/2024 Pasal 63 for E33G; PP 40/2023 &amp; PP 63/2023).
    Not a binding quote or legal opinion. The C5A "Content Creator" visit visa is legally classified but
    not operational as of this date. The E33G "Remote Worker" KITAS requires a documented employment/service
    contract with a company based outside Indonesia.
  </div>

  <div class="footer-flow">
    <span>BALI ZERO — zantara@balizero.com</span>
    <span>Visa guidance · Marc Buckner · 2026-05-31 · p. 2/2</span>
  </div>
</div>

</body></html>"""

html_path = OUT_DIR / "2026-05-31-marc-buckner-visa-guidance.html"
pdf_path = OUT_DIR / "2026-05-31-marc-buckner-visa-guidance.pdf"
html_path.write_text(HTML, encoding="utf-8")

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(f"file://{html_path}", wait_until="networkidle")
    page.wait_for_timeout(1500)
    heights = page.eval_on_selector_all(".page", "els => els.map(e => Math.round(e.getBoundingClientRect().height))")
    page.pdf(path=str(pdf_path), format="A4", print_background=True,
             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    browser.close()

print(f"PDF:  {pdf_path}")
print(f"PDF size: {pdf_path.stat().st_size} bytes")
print(f"page px heights: {heights}  (A4 = 1123px)")
