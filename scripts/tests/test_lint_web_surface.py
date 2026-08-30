"""Guilt AND innocence for scripts/lint_web_surface.py — the executable subset of
the 116-gate web-surface floor (research/design/2026-08-31-web-design-sixteen-
lane-corpus/SYNTHESIS.md).

Every gate in the lint ships with BOTH a guilty fixture it must catch and an
innocent fixture it must NOT, per this repo's guard-conformance rule: an
over-matching guard is cicatrix superscar family #3, and the interesting cases
here are precisely the innocent ones — `100%` inside `width: 100%`, `resmi`
inside `diresmikan`, `#1` inside a hex colour, `clamp()` on hero type.

`test_every_gate_has_both_a_guilt_and_an_innocence_assertion` enforces that rule
mechanically against this file's own source, so a gate added without an
innocence case turns this suite RED rather than shipping unproven.

The innocent fixtures marked MEASURED are real strings taken from apps/mouth
that an earlier, wider version of a gate flagged. They are regression pins: if
one of them goes red again, the gate has re-widened.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "lint_web_surface.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import lint_web_surface as lint  # noqa: E402


def hits(tmp_path: Path, name: str, content: str) -> set[str]:
    """Gate IDs that fire on one fixture file."""
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {f.gate_id for f in lint.scan_file(path, name)}


def findings(tmp_path: Path, name: str, content: str) -> list[lint.Finding]:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return lint.scan_file(path, name)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    # rc read off THIS command, never after a pipe — a piped rc measures the
    # pipe's last stage, not the process under test.
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )


# ══ GATE-108-AFFILIATION ══════════════════════════════════════════════════════

class TestAffiliationClaim:
    def test_guilty_official_partner(self, tmp_path: Path) -> None:
        src = 'export const HERO = "Bali Zero is the official partner for KITAS in Bali";\n'
        assert "GATE-108-AFFILIATION" in hits(tmp_path, "a.ts", src)

    def test_guilty_agen_resmi(self, tmp_path: Path) -> None:
        src = 'export const ID_HERO = "Kami adalah agen resmi imigrasi";\n'
        assert "GATE-108-AFFILIATION" in hits(tmp_path, "b.ts", src)

    def test_guilty_authorised_reseller(self, tmp_path: Path) -> None:
        src = '<p>We are an authorised reseller of government services</p>\n'
        assert "GATE-108-AFFILIATION" in hits(tmp_path, "c.tsx", src)

    def test_innocent_resmi_as_a_legal_source_citation(self, tmp_path: Path) -> None:
        """MEASURED — visa-oracle/privacy/page.tsx:63. `resmi` means "official"
        about a LAW, not about Bali Zero's affiliation with anyone."""
        src = 'const law = "Sumber resmi UU Nomor 27 Tahun 2022";\n'
        assert "GATE-108-AFFILIATION" not in hits(tmp_path, "d.ts", src)

    def test_innocent_resmi_about_a_registered_marriage(self, tmp_path: Path) -> None:
        """MEASURED — _lib/i18n.ts:1196."""
        src = 'const q = "Apakah pernikahan tercatat secara resmi?";\n'
        assert "GATE-108-AFFILIATION" not in hits(tmp_path, "e.ts", src)

    def test_innocent_resmi_as_a_substring_of_a_longer_word(self, tmp_path: Path) -> None:
        """The substring trap the mandate names: `resmi` lives inside
        `terkonfirmasi`-class words and inside `diresmikan` / `peresmian`
        literally. A bare `in` test traps on all three."""
        src = (
            'const a = "Status terkonfirmasi oleh sistem";\n'
            'const b = "Kantor baru diresmikan bulan lalu";\n'
            'const c = "Acara peresmian gedung";\n'
        )
        assert "GATE-108-AFFILIATION" not in hits(tmp_path, "f.ts", src)

    def test_innocent_official_about_a_government_body(self, tmp_path: Path) -> None:
        src = 'const s = "Check the official government portal at oss.go.id";\n'
        assert "GATE-108-AFFILIATION" not in hits(tmp_path, "g.ts", src)


# ══ GATE-108-GUARANTEE ════════════════════════════════════════════════════════

class TestGuaranteeClaim:
    def test_guilty_guaranteed(self, tmp_path: Path) -> None:
        src = 'const s = "Approval guaranteed in 5 working days";\n'
        assert "GATE-108-GUARANTEE" in hits(tmp_path, "a.ts", src)

    def test_guilty_dijamin(self, tmp_path: Path) -> None:
        src = 'const s = "Kami dijamin approve.";\n'
        assert "GATE-108-GUARANTEE" in hits(tmp_path, "b.ts", src)

    def test_guilty_tanpa_risiko(self, tmp_path: Path) -> None:
        src = '<span>Proses tanpa risiko untuk Anda</span>\n'
        assert "GATE-108-GUARANTEE" in hits(tmp_path, "c.tsx", src)

    def test_innocent_guarantee_as_a_product_noun(self, tmp_path: Path) -> None:
        """MEASURED — second-home/components/GuaranteePanel.tsx. The Day-90
        Guarantee Gate is a real contractual feature; `guarantee` the noun is not
        `guaranteed` the promise."""
        src = (
            'import type { GuaranteeInfo } from "@/lib/api/secondhome";\n'
            'export const TITLE = "Day-90 Guarantee Gate";\n'
            "const days = guarantee.days_remaining;\n"
        )
        assert "GATE-108-GUARANTEE" not in hits(tmp_path, "d.ts", src)

    def test_innocent_no_risk_tier_is_not_the_claim_no_risk(self, tmp_path: Path) -> None:
        """MEASURED — components/kbli/LicensingSection.tsx:1346. "no risk tier is
        shown" is the ABSENCE of a risk classification, the opposite of a promise."""
        src = (
            "<p>\n"
            "  which is why no risk tier or licensing route is shown above.\n"
            "</p>\n"
        )
        assert "GATE-108-GUARANTEE" not in hits(tmp_path, "e.tsx", src)

    def test_innocent_claim_inside_a_code_comment(self, tmp_path: Path) -> None:
        """Comments are blanked before any copy gate runs — a note about a rule
        must never trip the rule."""
        src = "// never write guaranteed or dijamin in shipped copy\n/* no risk */\n"
        assert "GATE-108-GUARANTEE" not in hits(tmp_path, "f.ts", src)


# ══ GATE-108-ABSOLUTE ═════════════════════════════════════════════════════════

class TestAbsoluteClaim:
    def test_guilty_100_percent_guaranteed(self, tmp_path: Path) -> None:
        src = 'const s = "Visa approval 100% guaranteed";\n'
        assert "GATE-108-ABSOLUTE" in hits(tmp_path, "a.ts", src)

    def test_guilty_100_percent_approval(self, tmp_path: Path) -> None:
        src = 'const s = "100% approval rate since 2019";\n'
        assert "GATE-108-ABSOLUTE" in hits(tmp_path, "b.ts", src)

    def test_guilty_reverse_order_indonesian(self, tmp_path: Path) -> None:
        src = '<p>Prosesnya aman 100% untuk semua klien</p>\n'
        assert "GATE-108-ABSOLUTE" in hits(tmp_path, "c.tsx", src)

    def test_innocent_css_width_100_percent(self, tmp_path: Path) -> None:
        """The mandate's headline innocence case."""
        src = 'const style = { width: "100%", height: 260 };\n'
        assert "GATE-108-ABSOLUTE" not in hits(tmp_path, "d.ts", src)

    def test_innocent_gradient_stop_and_tailwind_arbitrary_value(self, tmp_path: Path) -> None:
        src = (
            'const g = "linear-gradient(145deg, rgba(35,35,40,0.6) 0%, rgba(25,25,30,0.3) 100%)";\n'
            'const c = "w-[100%] flex items-center";\n'
        )
        assert "GATE-108-ABSOLUTE" not in hits(tmp_path, "e.ts", src)

    def test_innocent_100_percent_foreign_ownership_is_a_statement_of_law(
        self, tmp_path: Path
    ) -> None:
        """MEASURED, and the reason this gate is scoped to the CLAIM sense: the
        bare string produced 18 hits on apps/mouth of which 17 were regulatory
        facts of exactly this shape. SYNTHESIS gate 110 protects the conditioned
        claim; "wholly foreign-owned" is a legal term of art, not an absolute."""
        src = (
            'const a = "See which sectors allow 100% foreign ownership";\n'
            'const b = "PMA: 100% open nationally — but not open to a PT PMA in Bali.";\n'
            'const c = "100% of the RMMG (statutory minimum wage) for the principal applicant";\n'
        )
        assert "GATE-108-ABSOLUTE" not in hits(tmp_path, "f.ts", src)

    def test_innocent_css_block_in_a_template_literal(self, tmp_path: Path) -> None:
        """MEASURED — visa/page.tsx:135, SavePlanBar.tsx:23, EmptyStampReveal.tsx:54.
        A `<style>{`...`}` template literal is a stylesheet, not copy."""
        src = (
            "const PRINT_STYLES = `\n"
            "  @page { size: A4; margin: 12mm; }\n"
            "  .sheet { width: 100%; background: #fff; }\n"
            "`;\n"
        )
        assert "GATE-108-ABSOLUTE" not in hits(tmp_path, "g.ts", src)


# ══ GATE-108-RANK ═════════════════════════════════════════════════════════════

class TestRankClaim:
    def test_guilty_the_live_site_title(self, tmp_path: Path) -> None:
        """The exact string SYNTHESIS §4.1 item 3 names, live at
        apps/mouth/src/app/layout.tsx:96."""
        src = 'export const metadata = { title: "Bali Zero | #1 Visa & PT PMA Experts in Bali" };\n'
        assert "GATE-108-RANK" in hits(tmp_path, "a.ts", src)

    def test_guilty_first_reseller(self, tmp_path: Path) -> None:
        src = '<p>The first reseller of e-VOA in Bali</p>\n'
        assert "GATE-108-RANK" in hits(tmp_path, "b.tsx", src)

    def test_innocent_hash_one_inside_a_hex_colour(self, tmp_path: Path) -> None:
        src = 'const tokens = { accent: "#1a2b3c", ink: "#123456", deep: "#1E1E1E" };\n'
        assert "GATE-108-RANK" not in hits(tmp_path, "c.ts", src)

    def test_innocent_hash_one_as_an_anchor_href(self, tmp_path: Path) -> None:
        src = '<a href="#1">jump</a>\n'
        assert "GATE-108-RANK" not in hits(tmp_path, "d.tsx", src)

    def test_innocent_ordinal_locator_entry_hash_one(self, tmp_path: Path) -> None:
        """MEASURED — data/kbli-perpres-slice-disclosures.json:22. An ordinal
        pointer into a regulation table is not a primacy claim."""
        src = '{"locator": "Perpres 49/2021 Lampiran III (Daftar Bidang Usaha) entry #1"}\n'
        assert "GATE-108-RANK" not in hits(tmp_path, "e.json", src)

    def test_innocent_hash_one_in_a_code_comment(self, tmp_path: Path) -> None:
        """MEASURED — _lib/flow.ts:726, secondhome-studio/copy.ts:75."""
        src = "// Finding #1 (adversarial review 2026-07-17): back/edit truncate\n"
        assert "GATE-108-RANK" not in hits(tmp_path, "f.ts", src)


# ══ GATE-057-PARSEFLOAT ═══════════════════════════════════════════════════════

class TestParseFloatOnPrice:
    def test_guilty_dot_grouped_literal(self, tmp_path: Path) -> None:
        src = 'const n = parseFloat("790.000");\n'
        assert "GATE-057-PARSEFLOAT" in hits(tmp_path, "a.ts", src)

    def test_guilty_price_named_identifier(self, tmp_path: Path) -> None:
        src = "const total = parseFloat(totalPrice);\n"
        assert "GATE-057-PARSEFLOAT" in hits(tmp_path, "b.ts", src)

    def test_guilty_number_parsefloat_on_harga(self, tmp_path: Path) -> None:
        src = "const v = Number.parseFloat(hargaString);\n"
        assert "GATE-057-PARSEFLOAT" in hits(tmp_path, "c.ts", src)

    def test_innocent_coordinates_and_form_values(self, tmp_path: Path) -> None:
        """MEASURED — api/prime/zoning/route.ts:21, Calculator.tsx:389,
        AddCompanyModal.tsx:134."""
        src = (
            "const latNum = parseFloat(lat);\n"
            "const pct = parseFloat(formData.ownership_percentage);\n"
            "onChange={(e) => onChange(parseFloat(e.target.value) || 0)}\n"
        )
        assert "GATE-057-PARSEFLOAT" not in hits(tmp_path, "d.tsx", src)

    def test_innocent_plain_decimal_literal(self, tmp_path: Path) -> None:
        src = 'const ratio = parseFloat("1.5");\n'
        assert "GATE-057-PARSEFLOAT" not in hits(tmp_path, "e.ts", src)

    def test_innocent_camelcase_substring_trap(self, tmp_path: Path) -> None:
        """`cost` lives inside `costume`; a `\\bcost\\b` regex ALSO fails on
        `costValue`. Token-splitting is the only form that gets both right."""
        src = "const a = parseFloat(costumeSize);\n"
        assert "GATE-057-PARSEFLOAT" not in hits(tmp_path, "f.ts", src)


# ══ GATE-056-COMPACT ══════════════════════════════════════════════════════════

class TestCompactCurrency:
    def test_guilty_compact_with_currency_options(self, tmp_path: Path) -> None:
        src = (
            'const f = new Intl.NumberFormat("id-ID", {\n'
            '  style: "currency", currency: "IDR", notation: "compact",\n'
            "});\n"
        )
        assert "GATE-056-COMPACT" in hits(tmp_path, "a.ts", src)

    def test_guilty_compact_under_a_money_named_formatter(self, tmp_path: Path) -> None:
        """`formatIDRCompact` really exists in @balizero/core/utils and is called
        from two apps/mouth surfaces; the name is the currency evidence."""
        src = (
            "export const formatIDRCompact = (n: number) =>\n"
            '  new Intl.NumberFormat("id-ID", { notation: "compact" }).format(n);\n'
        )
        assert "GATE-056-COMPACT" in hits(tmp_path, "b.ts", src)

    def test_innocent_compact_on_a_count(self, tmp_path: Path) -> None:
        """MEASURED — clients/analytics/page.tsx:547. Compacting a case COUNT is
        not compacting a price."""
        src = (
            "const formatCompact = (num: number) => {\n"
            '  return new Intl.NumberFormat("id-ID", { notation: "compact" }).format(num);\n'
            "};\n"
        )
        assert "GATE-056-COMPACT" not in hits(tmp_path, "c.ts", src)

    def test_innocent_currency_without_compact(self, tmp_path: Path) -> None:
        src = (
            'const f = new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR" });\n'
        )
        assert "GATE-056-COMPACT" not in hits(tmp_path, "d.ts", src)


# ══ GATE-042-CLAMP ════════════════════════════════════════════════════════════

class TestClampOnPriceVerdictBody:
    def test_guilty_the_live_oracle_price_rule(self, tmp_path: Path) -> None:
        """The real violation, live at
        apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css:1288. A
        `(?<![\\w-])price(?![\\w-])` boundary CANNOT see this selector — which is
        why the gate matches on split tokens instead."""
        src = ".oracle-price__value {\n  font-size: clamp(1.75rem, 4vw, 2.25rem);\n  font-weight: 700;\n}\n"
        assert "GATE-042-CLAMP" in hits(tmp_path, "a.css", src)

    def test_guilty_body_copy_custom_property(self, tmp_path: Path) -> None:
        src = ":root {\n  --font-size-body: clamp(1rem, 1.4vw, 1.125rem);\n}\n"
        assert "GATE-042-CLAMP" in hits(tmp_path, "b.css", src)

    def test_guilty_inline_style_on_a_price_element(self, tmp_path: Path) -> None:
        src = (
            "const priceStyle = {\n"
            '  fontSize: "clamp(1.75rem, 4vw, 2.25rem)",\n'
            "};\n"
        )
        assert "GATE-042-CLAMP" in hits(tmp_path, "c.tsx", src)

    def test_innocent_clamp_on_hero_and_headline_type(self, tmp_path: Path) -> None:
        """MEASURED — oracle.css:181/287. Gate 42 permits clamp() on display/hero
        precisely because nobody QAs those at in-between widths."""
        src = (
            ".oracle-headline {\n  font-size: clamp(1.75rem, 4vw, 2.75rem);\n}\n"
            ".oracle-policy h1 {\n  font-size: clamp(2rem, 7vw, 4.5rem);\n}\n"
        )
        assert "GATE-042-CLAMP" not in hits(tmp_path, "d.css", src)

    def test_innocent_copy_to_clipboard_button_is_not_body_copy(self, tmp_path: Path) -> None:
        """MEASURED — oracle.css:1451. `.oracle-copy-cta` is a copy-to-clipboard
        control; `copy` is deliberately NOT in the forbidden token set."""
        src = '.oracle-copy-cta[data-copy-state="copied"] {\n  font-size: clamp(0.9rem, 2vw, 1rem);\n}\n'
        assert "GATE-042-CLAMP" not in hits(tmp_path, "e.css", src)

    def test_innocent_clamp_on_a_non_fontsize_property(self, tmp_path: Path) -> None:
        """MEASURED — oracle.css:287 ships `padding-block: clamp(...)` inside a
        price-adjacent block; the gate is about TYPE, not spacing."""
        src = ".oracle-price {\n  padding-block: clamp(2rem, 7vw, 5rem);\n}\n"
        assert "GATE-042-CLAMP" not in hits(tmp_path, "f.css", src)


# ══ GATE-088-ASTERISK ═════════════════════════════════════════════════════════

class TestAsteriskOnPrice:
    def test_guilty_asterisk_after_a_rendered_amount(self, tmp_path: Path) -> None:
        src = '<p>IDR 790.000*</p>\n'
        assert "GATE-088-ASTERISK" in hits(tmp_path, "a.tsx", src)

    def test_guilty_asterisk_after_a_price_interpolation(self, tmp_path: Path) -> None:
        src = "<span>{formattedPrice}*</span>\n"
        assert "GATE-088-ASTERISK" in hits(tmp_path, "b.tsx", src)

    def test_innocent_markdown_bold_around_a_price(self, tmp_path: Path) -> None:
        src = 'const s = "**IDR 790.000** all-inclusive";\n'
        assert "GATE-088-ASTERISK" not in hits(tmp_path, "c.ts", src)

    def test_innocent_multiplication(self, tmp_path: Path) -> None:
        src = "const line = {unitPrice} * {qty};\nconst t = 'IDR 790.000 * 2';\n"
        assert "GATE-088-ASTERISK" not in hits(tmp_path, "d.ts", src)


# ══ GATE-030-DELAY ════════════════════════════════════════════════════════════

class TestArtificialDelay:
    def test_guilty_settimeout_sets_the_success_state(self, tmp_path: Path) -> None:
        src = (
            "const onSubmit = () => {\n"
            "  setTimeout(() => {\n"
            '    setStatus("success");\n'
            "  }, 1200);\n"
            "};\n"
        )
        assert "GATE-030-DELAY" in hits(tmp_path, "a.tsx", src)

    def test_guilty_awaited_delay_before_a_success_toast(self, tmp_path: Path) -> None:
        """MEASURED as a REAL DEFECT — settings/backup/page.tsx:124 waits 2000ms
        and then reports "Your data has been downloaded successfully.\""""
        src = (
            "const handleExport = async () => {\n"
            "  // Simulate export for other data\n"
            "  await new Promise((resolve) => setTimeout(resolve, 2000));\n"
            '  success("Export completed", "Your data has been downloaded successfully.");\n'
            "};\n"
        )
        assert "GATE-030-DELAY" in hits(tmp_path, "b.tsx", src)

    def test_innocent_auto_dismissing_an_already_shown_toast(self, tmp_path: Path) -> None:
        """Hiding a success toast after it has been READ is not a fake delay —
        the defect is a timer that CAUSES the success state."""
        src = "setTimeout(() => setShowSuccess(false), 3000);\n"
        assert "GATE-030-DELAY" not in hits(tmp_path, "c.tsx", src)

    def test_innocent_short_yield_and_plain_debounce(self, tmp_path: Path) -> None:
        src = (
            "await new Promise((r) => setTimeout(r, 50));\n"
            "const t = setTimeout(fetchData, 400);\n"
        )
        assert "GATE-030-DELAY" not in hits(tmp_path, "d.ts", src)


# ══ GATE-059-ELLIPSIS ═════════════════════════════════════════════════════════

class TestEllipsisTruncation:
    def test_guilty_ellipsis_on_a_price_rule(self, tmp_path: Path) -> None:
        src = ".oracle-price__value {\n  text-overflow: ellipsis;\n  overflow: hidden;\n}\n"
        assert "GATE-059-ELLIPSIS" in hits(tmp_path, "a.css", src)

    def test_guilty_tailwind_truncate_on_a_price_element(self, tmp_path: Path) -> None:
        src = '<span className="truncate">{totalPrice}</span>\n'
        assert "GATE-059-ELLIPSIS" in hits(tmp_path, "b.tsx", src)

    def test_innocent_ellipsis_on_an_article_title(self, tmp_path: Path) -> None:
        src = ".article-title {\n  text-overflow: ellipsis;\n  white-space: nowrap;\n}\n"
        assert "GATE-059-ELLIPSIS" not in hits(tmp_path, "c.css", src)

    def test_innocent_truncate_on_a_client_name(self, tmp_path: Path) -> None:
        src = '<td className="truncate max-w-[200px]">{client.name}</td>\n'
        assert "GATE-059-ELLIPSIS" not in hits(tmp_path, "d.tsx", src)


# ══ GATE-062-FLAG ═════════════════════════════════════════════════════════════

class TestFlagLanguageSwitcher:
    def test_guilty_flag_emoji_in_a_language_switcher(self, tmp_path: Path) -> None:
        src = (
            "export function LanguageSwitcher() {\n"
            "  const locales = [\n"
            '    { code: "en", flag: "\U0001F1EC\U0001F1E7" },\n'
            '    { code: "id", flag: "\U0001F1EE\U0001F1E9" },\n'
            "  ];\n"
            "}\n"
        )
        assert "GATE-062-FLAG" in hits(tmp_path, "LanguageSwitcher.tsx", src)

    def test_guilty_flag_image_asset_in_a_locale_switch(self, tmp_path: Path) -> None:
        src = (
            "function LocaleSwitch() {\n"
            '  return <img src="/flags/id.svg" alt="Bahasa" onClick={setLocale} />;\n'
            "}\n"
        )
        assert "GATE-062-FLAG" in hits(tmp_path, "a.tsx", src)

    def test_innocent_nationality_picker_flags(self, tmp_path: Path) -> None:
        """MEASURED — src/lib/utils/nationality-flags.ts and
        visa-oracle/nationalities.ts. A flag beside a NATIONALITY names a
        country, which is exactly what a flag is for."""
        src = (
            "export const NATIONALITY_FLAGS: Record<string, string> = {\n"
            '  ID: "\U0001F1EE\U0001F1E9",\n'
            '  GB: "\U0001F1EC\U0001F1E7",\n'
            "};\n"
            "// passport country of issue\n"
        )
        assert "GATE-062-FLAG" not in hits(tmp_path, "nationality-flags.ts", src)

    def test_innocent_flag_emoji_in_ordinary_prose(self, tmp_path: Path) -> None:
        src = '<p>Indonesia \U0001F1EE\U0001F1E9 raised its visa-on-arrival fee.</p>\n'
        assert "GATE-062-FLAG" not in hits(tmp_path, "b.tsx", src)


# ══ GATE-113-OVERLAY ══════════════════════════════════════════════════════════

class TestAccessibilityOverlay:
    def test_guilty_accessibe_script_host(self, tmp_path: Path) -> None:
        src = '<script src="https://acsbapp.com/apps/app/dist/js/app.js" async></script>\n'
        assert "GATE-113-OVERLAY" in hits(tmp_path, "a.html", src)

    def test_guilty_userway_widget_and_package(self, tmp_path: Path) -> None:
        src = (
            '<script src="https://cdn.userway.org/widget.js" data-account="x"></script>\n'
        )
        assert "GATE-113-OVERLAY" in hits(tmp_path, "b.html", src)

    def test_innocent_naming_the_vendor_in_prose(self, tmp_path: Path) -> None:
        """The gate matches HOSTS and package specifiers, never the vendor NAME —
        a doc or a warning that says "never install accessiBe" must stay clean,
        or the rule cannot be written down anywhere."""
        src = (
            'const NOTE = "Never install an accessibility overlay such as accessiBe or UserWay.";\n'
        )
        assert "GATE-113-OVERLAY" not in hits(tmp_path, "c.ts", src)


# ══ GATE-058-FIXEDWIDTH ═══════════════════════════════════════════════════════

class TestFixedWidthControl:
    def test_guilty_css_fixed_width_button(self, tmp_path: Path) -> None:
        src = ".btn-primary {\n  width: 180px;\n  padding: 12px;\n}\n"
        assert "GATE-058-FIXEDWIDTH" in hits(tmp_path, "a.css", src)

    def test_guilty_tailwind_arbitrary_width_on_a_cta(self, tmp_path: Path) -> None:
        src = '<button className="cta rounded-lg w-[140px] py-2">Ajukan</button>\n'
        assert "GATE-058-FIXEDWIDTH" in hits(tmp_path, "b.tsx", src)

    def test_innocent_square_icon_button(self, tmp_path: Path) -> None:
        """A control with no text has nothing to expand."""
        src = ".btn-icon {\n  width: 40px;\n  height: 40px;\n}\n"
        assert "GATE-058-FIXEDWIDTH" not in hits(tmp_path, "c.css", src)

    def test_innocent_min_and_max_width(self, tmp_path: Path) -> None:
        """MEASURED — clients/new/page.tsx:932. `min-w-[140px]` is the PRESCRIBED
        form; a guard that cannot tell it from `w-[140px]` bans its own fix."""
        src = (
            ".btn-primary {\n  min-width: 140px;\n}\n"
        )
        assert "GATE-058-FIXEDWIDTH" not in hits(tmp_path, "d.css", src)

    def test_innocent_tailwind_min_width_on_a_button(self, tmp_path: Path) -> None:
        src = '<button className="btn min-w-[140px] max-w-[220px]">Kirim</button>\n'
        assert "GATE-058-FIXEDWIDTH" not in hits(tmp_path, "e.tsx", src)

    def test_innocent_fixed_width_on_a_non_control(self, tmp_path: Path) -> None:
        src = ".sidebar-rail {\n  width: 72px;\n}\n"
        assert "GATE-058-FIXEDWIDTH" not in hits(tmp_path, "f.css", src)


# ══ GATE-068-NUMBERINPUT ══════════════════════════════════════════════════════

class TestNumberInput:
    def test_guilty_type_number_input(self, tmp_path: Path) -> None:
        src = '<input type="number" value={days} onChange={onChange} />\n'
        assert "GATE-068-NUMBERINPUT" in hits(tmp_path, "a.tsx", src)

    def test_innocent_type_number_in_a_schema_object(self, tmp_path: Path) -> None:
        """A JSON-schema / column definition uses a COLON, an HTML attribute an
        EQUALS. That single character is the whole distinction."""
        src = 'const field = { name: "days", type: "number", required: true };\n'
        assert "GATE-068-NUMBERINPUT" not in hits(tmp_path, "b.ts", src)

    def test_innocent_prescribed_replacement(self, tmp_path: Path) -> None:
        src = '<input type="text" inputMode="numeric" pattern="[0-9]*" />\n'
        assert "GATE-068-NUMBERINPUT" not in hits(tmp_path, "c.tsx", src)


# ══ suppression contract ══════════════════════════════════════════════════════

class TestSuppression:
    GUILTY = 'const t = "Bali Zero | #1 Visa & PT PMA Experts in Bali";'

    def test_suppression_with_a_reason_silences_that_gate(self, tmp_path: Path) -> None:
        src = f"{self.GUILTY}  // lint-web-surface: ignore GATE-108-RANK -- SEO title frozen by owner, rewrite tracked in PENDING-ARMS\n"
        got = hits(tmp_path, "a.ts", src)
        assert "GATE-108-RANK" not in got
        assert "GATE-SUPPRESSION-NO-REASON" not in got

    def test_suppression_on_the_line_above_also_covers(self, tmp_path: Path) -> None:
        src = (
            "// lint-web-surface: ignore GATE-108-RANK -- owner-approved legacy title, see ticket 4711\n"
            f"{self.GUILTY}\n"
        )
        assert "GATE-108-RANK" not in hits(tmp_path, "b.ts", src)

    def test_a_reasonless_suppression_is_itself_a_finding(self, tmp_path: Path) -> None:
        src = f"{self.GUILTY}  // lint-web-surface: ignore GATE-108-RANK\n"
        got = hits(tmp_path, "c.ts", src)
        assert "GATE-SUPPRESSION-NO-REASON" in got

    def test_a_reasonless_suppression_suppresses_nothing(self, tmp_path: Path) -> None:
        """The load-bearing half: if a bare `ignore` still silenced the gate, the
        reason requirement would be decoration and the gate would die quietly."""
        src = f"{self.GUILTY}  // lint-web-surface: ignore GATE-108-RANK\n"
        assert "GATE-108-RANK" in hits(tmp_path, "d.ts", src)

    def test_a_too_short_reason_does_not_count(self, tmp_path: Path) -> None:
        src = f"{self.GUILTY}  // lint-web-surface: ignore GATE-108-RANK -- ok\n"
        got = hits(tmp_path, "e.ts", src)
        assert "GATE-SUPPRESSION-NO-REASON" in got
        assert "GATE-108-RANK" in got

    def test_a_suppression_names_exactly_one_gate(self, tmp_path: Path) -> None:
        """No blanket ignore: suppressing a DIFFERENT gate leaves this one red."""
        src = f"{self.GUILTY}  // lint-web-surface: ignore GATE-042-CLAMP -- unrelated, this line has no clamp at all\n"
        assert "GATE-108-RANK" in hits(tmp_path, "f.ts", src)

    def test_suppression_reports_the_gate_it_failed_to_name(self, tmp_path: Path) -> None:
        src = "// lint-web-surface: ignore GATE-042-CLAMP\n"
        found = findings(tmp_path, "g.ts", src)
        assert [f.gate_id for f in found] == ["GATE-SUPPRESSION-NO-REASON"]
        assert "GATE-042-CLAMP" in found[0].message
        assert found[0].line == 1


# ══ CLI contract ══════════════════════════════════════════════════════════════

class TestCli:
    def test_exit_zero_and_clean_message_on_a_clean_tree(self, tmp_path: Path) -> None:
        (tmp_path / "ok.ts").write_text('export const HELLO = "Selamat datang";\n')
        r = run_cli(str(tmp_path))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "clean" in r.stdout

    def test_exit_one_and_the_finding_line_format(self, tmp_path: Path) -> None:
        (tmp_path / "bad.ts").write_text('const t = "We are the official partner of Imigrasi";\n')
        r = run_cli(str(tmp_path))
        assert r.returncode == 1, r.stdout + r.stderr
        assert "bad.ts:1: [GATE-108-AFFILIATION]" in r.stdout
        assert "(source: SYNTHESIS §3.10, gate 108)" in r.stdout

    def test_exit_two_on_a_blind_scan(self, tmp_path: Path) -> None:
        """Zero files read is a BROKEN scan, not a clean one — the W97 lesson."""
        (tmp_path / "notes.rst").write_text("nothing in scope here\n")
        r = run_cli(str(tmp_path))
        assert r.returncode == 2, r.stdout + r.stderr
        assert "BLIND SCAN" in r.stderr

    def test_json_shape(self, tmp_path: Path) -> None:
        (tmp_path / "bad.tsx").write_text('<input type="number" />\n')
        r = run_cli(str(tmp_path), "--json")
        assert r.returncode == 1, r.stdout + r.stderr
        payload = json.loads(r.stdout)
        assert payload["schema"] == 1
        assert payload["scanned_files"] == 1
        assert payload["blind_scan"] is False
        assert payload["skipped_oversize"] == []
        assert {"path", "line", "gate", "message", "source"} == set(payload["findings"][0])
        assert payload["findings"][0]["gate"] == "GATE-068-NUMBERINPUT"
        assert {g["id"] for g in payload["gates"]} == {g.id for g in lint.GATES}

    def test_list_gates_names_every_implemented_gate(self) -> None:
        r = run_cli("--list-gates")
        assert r.returncode == 0, r.stdout + r.stderr
        for gate in lint.GATES:
            assert gate.id in r.stdout
            assert gate.source in r.stdout
        assert lint.SUPPRESSION_GATE_ID in r.stdout

    def test_only_filters_to_one_gate(self, tmp_path: Path) -> None:
        (tmp_path / "bad.tsx").write_text(
            '<input type="number" />\nconst t = "the official partner of nobody";\n'
        )
        r = run_cli(str(tmp_path), "--only", "GATE-068-NUMBERINPUT", "--json")
        assert r.returncode == 1
        assert {f["gate"] for f in json.loads(r.stdout)["findings"]} == {"GATE-068-NUMBERINPUT"}

    def test_unknown_gate_id_is_rejected(self, tmp_path: Path) -> None:
        r = run_cli(str(tmp_path), "--only", "GATE-DOES-NOT-EXIST")
        assert r.returncode == 4
        assert "unknown gate id" in r.stderr

    def test_oversize_files_are_skipped_but_reported(self, tmp_path: Path) -> None:
        """A 37MB KBLI dataset really is in apps/mouth. Skipping it silently would
        be the blind-scan failure wearing a clean face."""
        big = tmp_path / "data.json"
        big.write_text('{"note": "x' + "y" * 2000 + '"}\n')
        r = run_cli(str(tmp_path), "--max-bytes", "100", "--json")
        payload = json.loads(r.stdout)
        assert payload["scanned_files"] == 0
        assert any(p.endswith("data.json") for p in payload["skipped_oversize"])
        assert r.returncode == 2  # nothing was actually read

    def test_mdx_is_opt_in_not_default(self, tmp_path: Path) -> None:
        """Article prose is out of default scope on purpose: `resmi` appears in
        317 apps/mouth articles as reported fact, never as a Bali Zero claim."""
        (tmp_path / "post.mdx").write_text("Pemerintah menunjuk agen resmi untuk layanan ini.\n")
        assert run_cli(str(tmp_path)).returncode == 2  # nothing in scope -> blind
        r = run_cli(str(tmp_path), "--ext", ".mdx", "--json")
        assert r.returncode == 1
        assert json.loads(r.stdout)["findings"][0]["gate"] == "GATE-108-AFFILIATION"

    def test_test_files_are_excluded_by_default(self, tmp_path: Path) -> None:
        """This repo's own forbidden-claims guard ships "Kami dijamin approve."
        as a fixture; a lint that fires on another guard's guilty fixtures is
        noise, and noise gets suppressed rather than fixed."""
        (tmp_path / "claims.test.ts").write_text('const bad = "Kami dijamin approve.";\n')
        assert run_cli(str(tmp_path)).returncode == 2
        r = run_cli(str(tmp_path), "--include-tests", "--json")
        assert r.returncode == 1
        assert json.loads(r.stdout)["findings"][0]["gate"] == "GATE-108-GUARANTEE"


# ══ the guard-conformance meta-test ═══════════════════════════════════════════

class TestGuardConformance:
    def test_every_gate_has_both_a_guilt_and_an_innocence_assertion(self) -> None:
        """The rule this suite exists to enforce, applied to the suite itself: a
        gate may not ship with only a guilty fixture. Reads this file's own
        source so a gate added tomorrow without an innocence case turns it RED.
        """
        import re

        source = Path(__file__).read_text(encoding="utf-8")
        guilty = set(re.findall(r'assert "(GATE-[A-Z0-9-]+)" in ', source))
        innocent = set(re.findall(r'assert "(GATE-[A-Z0-9-]+)" not in ', source))
        expected = {g.id for g in lint.GATES} | {lint.SUPPRESSION_GATE_ID}
        assert expected - guilty == set(), f"gates with no GUILTY fixture: {expected - guilty}"
        assert expected - innocent == set(), f"gates with no INNOCENT fixture: {expected - innocent}"

    def test_gate_ids_are_unique_and_stable_shaped(self) -> None:
        ids = [g.id for g in lint.GATES]
        assert len(ids) == len(set(ids))
        for gate in lint.GATES:
            assert gate.id.startswith("GATE-"), gate.id
            # Every gate cites the floor it came from — a finding whose provenance
            # nobody can check gets suppressed rather than fixed.
            assert gate.source.startswith("SYNTHESIS §"), gate.id
            assert gate.title.strip(), gate.id

    def test_a_comment_can_never_trip_any_gate(self, tmp_path: Path) -> None:
        """One fixture, every blocked construct, all inside comments. This is the
        single most common way a lint like this becomes unusable: it fires on the
        documentation of its own rules."""
        src = (
            "// guaranteed dijamin 100% guaranteed #1 official partner tanpa risiko\n"
            "/* IDR 790.000* — parseFloat(priceString) — acsbapp.com/apps/app.js\n"
            '   type="number" and text-overflow: ellipsis on a price */\n'
        )
        assert hits(tmp_path, "notes.ts", src) == set()
