"""Synthetic, versioned staff experiment. This is not a visa eligibility engine."""

from __future__ import annotations

import base64
import binascii
import io
from datetime import date, timedelta
from typing import Literal, Self

from fastapi import HTTPException
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CAMPAIGN_ID = "oracle-team-20260928"
PLAN_VERSION = "1"
SLOTS = tuple(f"T{i:02d}" for i in range(1, 7))
DAYS = tuple((date(2026, 9, 28) + timedelta(days=i)).isoformat() for i in range(5))
COUNTRIES = ("IT", "AU", "US", "GB", "DE", "FR")


def base_profile(country: str = "IT", category: str = "tourism") -> dict[str, str]:
    return {
        "in_indonesia": "no",
        "holds_stay_permit": "no",
        "nationalities": country,
        "birth_date": "1990-01-01",
        "category": category,
        "trip_scope": "single",
        "stay_days": "14",
        "entry_pattern": "SINGLE",
        "review_gate": "none",
    }


def remote_profile(country: str = "IT") -> dict[str, str]:
    return {
        **base_profile(country, "remote"),
        "sponsor_category": "NONE",
        "remote_clients": "foreign",
        "remote_compensation": "no",
        "work_payer": "no",
        "remote_employer_country": "IT",
        "remote_pt_pma": "no",
        "stay_days": "365",
    }


def scenario(day: int, variant: int, tester: int) -> dict:
    """Controlled strata, not random facts or pre-labelled legal answers."""
    country = COUNTRIES[tester]
    p = base_profile(country)
    focus = "Catat pertanyaan, alasan, sumber, dan batas hasil."
    titles = (
        "Kunjungan singkat",
        "Pekerjaan jarak jauh",
        "Izin yang sudah dimiliki",
        "Tujuan dan persyaratan",
        "Tujuan campuran dan ketidakpastian",
    )
    if day == 0:
        p.update(
            stay_days=str((14, 30, 60, 180)[variant]),
            entry_pattern=("SINGLE" if variant < 2 else "MULTIPLE"),
        )
        focus = "Bandingkan durasi dan pola masuk; angka ini adalah input uji, bukan ambang hukum."
    elif day == 1:
        p = remote_profile(country)
        p["stay_days"] = str((30, 90, 180, 365, 366, 730)[tester])
        if variant == 1:
            p.update(
                remote_clients="mixed", remote_compensation="unsure", review_gate="uncertainty"
            )
        elif variant == 2:
            p.update(
                remote_clients="indonesian",
                remote_compensation="yes",
                work_payer="yes",
                remote_employer_country="ID",
                sponsor_category="EMPLOYER",
            )
        elif variant == 3:
            p.update(
                remote_clients="unsure",
                remote_compensation="unsure",
                work_payer="unsure",
                remote_employer_country="unsure",
                review_gate="uncertainty",
            )
        focus = "Apakah sumber pembayaran dan konteks kerja ditangani? Catat syarat yang belum ditanyakan."
    elif day == 2:
        p = base_profile(country) if tester < 3 else remote_profile(country)
        p.update(
            in_indonesia="yes",
            holds_stay_permit="no" if tester < 3 else "yes",
            wants_onshore_conversion="no",
            application_channel="unsure",
            stay_days="60" if tester < 3 else "365",
        )
        p["current_status_code" if tester < 3 else "stay_permit_code"] = (
            "C1" if tester < 3 else "E33G"
        )
        offsets = (14, -3, -3, None)
        offset = offsets[variant]
        p["permit_expiry"] = (
            "unsure"
            if offset is None
            else (date.fromisoformat(DAYS[day]) + timedelta(days=offset)).isoformat()
        )
        p["overstay_days"] = ("0", "3", "0", "unsure")[variant]
        p["renewal_paid"] = ("no", "no", "yes", "unsure")[variant]
        p["review_gate"] = (
            "uncertainty" if variant == 3 else ("overstay" if variant == 1 else "none")
        )
        focus = "Kelanjutan izin, bukan permohonan baru. Jangan menyamakan perpanjangan dengan konversi/bridging. Catat jika pilihan yang sesuai tidak tersedia."
    elif day == 3:
        category = ("business", "work", "study", "family", "invest", "retirement")[tester]
        p = base_profile(country, category)
        p.update(stay_days="365", sponsor_category="INDIVIDUAL")
        if category == "business":
            p.update(
                business_activity=("meetings", "negotiation", "conference", "exploring")[variant],
                work_indonesia_compensation="no",
                stay_days="30",
            )
        elif category == "work":
            p.update(
                sponsor_category="EMPLOYER",
                work_payer="yes",
                work_indonesia_compensation="yes",
                work_sponsor_confirmed="no" if variant == 2 else "yes",
            )
        elif category == "study":
            p.update(
                sponsor_category="EDUCATION",
                study_level="UNDERGRADUATE",
                study_admission_confirmed="no" if variant == 2 else "yes",
                study_sponsor_confirmed="yes",
            )
        elif category == "family":
            p.update(
                family_sponsor_confirmed="yes",
                family_relation="SPOUSE",
                marital_status="MARRIED",
                family_sponsor_nationalities="ID",
                family_marriage_registered="no" if variant == 2 else "yes",
            )
        elif category == "invest":
            p.update(
                sponsor_category="INVESTMENT",
                investment_vehicle="pt_pma",
                investment_pt_pma="yes",
                investment_currency="idr",
                investment_capital_idr="10000000000",
                investment_paid_up_capital_idr="10000000000",
                investment_role="SHAREHOLDER_DIRECTOR",
            )
            if variant == 2:
                p.update(
                    investment_pt_pma="no",
                    investment_capital_idr="0",
                    investment_paid_up_capital_idr="0",
                    investment_role="NO_OPERATIONAL_ROLE",
                )
        else:
            p.update(
                birth_date="1960-01-01",
                retirement_basis="undecided",
                retirement_undecided_basis="still_unsure",
            )
            if variant == 2:
                p.update(retirement_basis="family_sponsor", family_sponsor_confirmed="no")
        if variant == 1:
            p["sponsor_category"] = "unsure"
            p["review_gate"] = "uncertainty"
        if variant == 3:
            p.update(trip_scope="multiple", review_gate="activity_boundary")
        focus = "Uji satu cabang dan perubahan konteks. Syarat hukum belum dikalibrasi: tidak ada jawaban visa yang dianggap pasti."
        if category == "invest" and variant == 2:
            focus += " Kontras sengaja: rencana investasi melalui PT PMA, tetapi PT PMA belum ada dan modal belum disetor. Jangan mengubah jawaban no atau modal 0."
    else:
        category = ("tourism", "remote", "business", "family", "second_home", "diaspora")[tester]
        p = remote_profile(country) if category == "remote" else base_profile(country, category)
        p["stay_days"] = "30"
        if category == "business":
            p.update(business_activity="meetings", work_indonesia_compensation="no")
        elif category in {"family", "diaspora"}:
            p.update(
                family_sponsor_confirmed="yes",
                family_relation="SPOUSE",
                marital_status="MARRIED",
                family_sponsor_nationalities="ID",
                family_marriage_registered="yes",
                sponsor_category="INDIVIDUAL",
            )
            if category == "diaspora":
                p.update(diaspora_connection="family", diaspora_documents="yes")
        elif category == "second_home":
            p.update(secondhome_basis="unsure", review_gate="uncertainty")
        if variant == 0:
            p.update(trip_scope="multiple", review_gate="activity_boundary")
        elif variant == 1:
            p.update(entry_pattern="unsure", review_gate="uncertainty")
        elif variant == 2:
            p.update(nationalities=country + ",CA", review_gate="none")
        else:
            p = base_profile(country, "other")
            p.update(
                stay_days="30",
                other_purpose="volunteer",
                other_paid_activity="no",
                family_sponsor_confirmed="unsure",
                review_gate="uncertainty",
            )
        focus = "Ketidakpastian dan dua kewarganegaraan tidak boleh ditebak. Catat apakah sistem menjelaskan batasnya."
    return {
        "id": f"D{day + 1}-V{tester + 1}-{variant + 1}",
        "title": titles[day],
        "focus": focus,
        "inputs": p,
        "instructions": [
            "Profil sepenuhnya sintetis. Jangan memakai nama, dokumen, nomor atau data klien.",
            "Pilih EN di Visa Oracle agar label pertanyaan dapat dibandingkan. Catat semua pilihan persisnya.",
            "Masukkan hanya fakta yang ditanyakan. Input yang tidak muncul dicatat sebagai tidak ditanyakan.",
            "unsure berarti pilih Not sure?; jika pilihan itu tidak tersedia, jangan menebak. Catat hambatan fixture dan minta peninjau memperjelas.",
            "Pada pertanyaan pengungkapan: none = None of these apply; uncertainty = I’m not certain; activity_boundary = aktivitas melintasi kategori; overstay = A past overstay. Salin label nyata.",
            "Jika perlu fakta tambahan yang tidak ada di profil, catat pertanyaannya; jangan membuat fakta agar mencapai hasil.",
            "Jangan mengirim WhatsApp, formulir aplikasi, pembayaran atau permintaan kontak.",
        ],
    }


def make_assignments() -> list[dict]:
    rows = []
    for d, day in enumerate(DAYS):
        reference = scenario(d, 0, 0)
        # Identical across staff, distinct from their four contrasting cases.
        reference["inputs"]["stay_days"] = ("21", "365", "45", "14", "14")[d]
        if d == 2:
            reference["inputs"]["permit_expiry"] = (
                date.fromisoformat(day) + timedelta(days=7)
            ).isoformat()
        reference["id"] = f"D{d + 1}-REF"
        reference["title"] = "Acuan bersama · " + reference["title"]
        for tester, slot in enumerate(SLOTS):
            for index in range(5):
                rows.append(
                    {
                        "id": f"D{d + 1}-{slot}-{index}",
                        "slot": slot,
                        "day": day,
                        "index": index,
                        "scenario": reference if index == 0 else scenario(d, index - 1, tester),
                    }
                )
    return rows


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StartPayload(StrictPayload):
    text: str = Field(min_length=8, max_length=2000)
    basis: Literal["hypothesis", "official", "expert", "needs_review"]
    reference: str = Field(default="", max_length=1000)
    browser: str = Field(min_length=2, max_length=100)
    device: str = Field(min_length=2, max_length=100)
    displayed_version: str = Field(default="unknown", min_length=1, max_length=100)
    synthetic_only: Literal[True]

    @model_validator(mode="after")
    def require_claim_basis(self) -> Self:
        if self.basis in {"official", "expert"} and len(self.reference) < 8:
            raise ValueError("An official or expert expectation requires a reference")
        return self


class ResultPayload(StrictPayload):
    steps: str = Field(default="", max_length=8000)
    actual_state: Literal[
        "supported", "needs_input", "human_review", "no_path", "unavailable", "blocked", "other"
    ] = "other"
    actual: str = Field(default="", max_length=4000)
    source_notes: str = Field(default="", max_length=2000)
    uncertainty: str = Field(default="", max_length=2000)
    comment: str = Field(default="", max_length=2000)
    category: Literal[
        "none",
        "eligibility",
        "missing_question",
        "explanation",
        "reference",
        "navigation",
        "privacy",
    ] = "none"
    severity: Literal["none", "low", "medium", "high"] = "none"
    certainty: Literal["observation", "hypothesis", "expert"] = "observation"
    reproducibility: Literal["not_retried", "same", "different", "blocked"] = "not_retried"
    evidence_ref: str = Field(default="", max_length=1500)
    screenshot_base64: str = Field(default="", max_length=820000)
    submit: bool = False
    synthetic_only: Literal[True]

    @field_validator("screenshot_base64")
    @classmethod
    def validate_image(cls, value: str) -> str:
        if not value:
            return value
        try:
            raw = base64.b64decode(value, validate=True)
            if len(raw) > 600 * 1024:
                raise ValueError("Image evidence maximum 600 KiB")
            with Image.open(io.BytesIO(raw)) as im:
                if im.format not in {"PNG", "JPEG", "WEBP"} or im.width * im.height > 16_000_000:
                    raise ValueError("Invalid image dimensions")
                im.verify()
            with Image.open(io.BytesIO(raw)) as im:
                pixels = ImageOps.exif_transpose(im).convert(
                    "RGBA" if "A" in im.getbands() else "RGB"
                )
                clean = Image.new(pixels.mode, pixels.size)
                clean.paste(pixels)
                buffer = io.BytesIO()
                clean.save(buffer, format="PNG")
                raw = buffer.getvalue()
                if len(raw) > 600 * 1024:
                    raise ValueError("Clean image evidence maximum 600 KiB")
        except (binascii.Error, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ValueError("Invalid PNG, JPEG or WebP evidence") from exc
        return base64.b64encode(raw).decode("ascii")


class ReviewPayload(StrictPayload):
    verdict: Literal["confirmed_issue", "not_issue", "needs_expert_review"]
    comment: str = Field(min_length=8, max_length=2000)
    reproduced: bool = False
    reproduction_evidence: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def consistent_reproduction(self) -> Self:
        if self.reproduced and self.verdict != "confirmed_issue":
            raise ValueError("Reproduction applies only to confirmed issues")
        return self


class SlotPayload(StrictPayload):
    member_id: str | None = Field(default=None, min_length=1, max_length=100)
    reviewer: bool = False


def authorize_record(actor: str, owner: str, *, review: bool = False) -> None:
    if (actor == owner) if review else (actor != owner):
        raise HTTPException(
            403, "Cannot review own test" if review else "Assignment belongs to another tester"
        )


def validate_submission(value: ResultPayload, *, has_stored_image: bool = False) -> None:
    if any(len(x.strip()) < 8 for x in (value.steps, value.actual, value.comment)):
        raise HTTPException(422, "Record exact inputs, actual behavior and an actionable comment")
    if not value.source_notes or not value.uncertainty:
        raise HTTPException(422, "Record sources and uncertainty, including when not shown")
    if value.category == "none" and value.severity != "none":
        raise HTTPException(422, "Severity requires a finding category")
    if value.category != "none" and value.severity == "none":
        raise HTTPException(422, "A finding requires impact severity")
    if value.reproducibility == "same" and not (
        value.evidence_ref or value.screenshot_base64 or has_stored_image
    ):
        raise HTTPException(422, "Repeated findings need evidence")
