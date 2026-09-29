"""Authenticated staff test campaign; never calls or mutates the visa engine."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from PIL import Image

from backend.app.dependencies import get_database_pool, require_team_member
from backend.app.deps.owner import OWNER_EMAILS
from backend.app.utils.service_accounts import TEAM_ROLES, is_human_team_member
from backend.services.visa_oracle_testing import (
    CAMPAIGN_ID,
    DAYS,
    PLAN_VERSION,
    SLOTS,
    ResultPayload,
    ReviewPayload,
    SlotPayload,
    StartPayload,
    authorize_record,
    make_assignments,
    validate_submission,
)

router = APIRouter(prefix="/api/visa-oracle/testing", tags=["visa-oracle-testing"])
PLAN = {row["id"]: row for row in make_assignments()}


def bali_today() -> str:
    return datetime.now(ZoneInfo("Asia/Makassar")).date().isoformat()


async def expectation_days(conn, who: dict) -> set[str]:
    rows = await conn.fetch(
        "SELECT assigned_day::text AS day FROM visa_oracle_test_runs WHERE campaign_id=$1 AND member_id=$2 GROUP BY assigned_day HAVING count(*)=5",
        CAMPAIGN_ID,
        who["id"],
    )
    return {r["day"] for r in rows}


async def review_days(conn, who: dict) -> set[str]:
    """Days this actor may review — the admin any day, a tester only a day they have
    fully locked (self-review still waits for all five personal expectations first).
    Gates the /review day-lock check ONLY; it does not grant peer visibility — see
    `authorize_record(..., review=True)` for who may review WHICH record.
    """
    if not who["can_review"]:
        return set()
    if who["slot"] is None:
        return set(DAYS)
    return await expectation_days(conn, who)


def decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


async def actor(conn, user: dict) -> dict:
    row = await conn.fetchrow(
        "SELECT id::text AS id, role FROM team_members WHERE lower(email)=$1 AND active=true",
        str(user.get("email") or "").lower(),
    )
    if not row or not is_human_team_member(row["role"]):
        raise HTTPException(403, "Active staff membership required")
    owner = str(user.get("email") or "").lower() in OWNER_EMAILS
    slot = await conn.fetchrow(
        "SELECT slot, reviewer FROM visa_oracle_test_slots WHERE member_id=$1", row["id"]
    )
    return {
        "id": row["id"],
        "slot": slot["slot"] if slot else None,
        "can_configure": owner,
        # Self-review (2026-09-30): any assigned tester may review their OWN submitted
        # runs, so `can_review` no longer gates on the (now vestigial) slot `reviewer`
        # flag — it is true for the admin and for anyone holding a slot. What is still
        # gated is WHICH record: see `authorize_record(..., review=True)`.
        "can_review": owner or slot is not None,
    }


def assignment(key: str) -> dict:
    if key not in PLAN:
        raise HTTPException(404, "Unknown assignment")
    return PLAN[key]


async def writable_slot(conn, who: dict, case: dict) -> None:
    # Serialize start vs roster reassignment using the SAME row lock.
    slot = await conn.fetchrow(
        "SELECT member_id FROM visa_oracle_test_slots WHERE slot=$1 FOR UPDATE", case["slot"]
    )
    if not slot or slot["member_id"] != who["id"]:
        raise HTTPException(403, "Assignment belongs to another tester")


async def view(conn, who: dict) -> dict:
    slots = [
        dict(r)
        for r in await conn.fetch(
            "SELECT slot, member_id, reviewer FROM visa_oracle_test_slots ORDER BY slot"
        )
    ]
    rows = await conn.fetch(
        "SELECT assignment_id,slot,member_id,assigned_day,scenario,expected,status,started_at,submitted_at,review,"
        "result,screenshot IS NOT NULL AS has_image "
        "FROM visa_oracle_test_runs WHERE campaign_id=$1",
        CAMPAIGN_ID,
    )
    ready_days = await expectation_days(conn, who)
    stored = {r["assignment_id"]: r for r in rows}
    cases = []
    for case in PLAN.values():
        row = stored.get(case["id"])
        record = None
        if row:
            record = {
                "status": row["status"],
                "started_at": row["started_at"].isoformat(),
                "submitted_at": row["submitted_at"].isoformat() if row["submitted_at"] else None,
            }
            # Shared status, but blind test content: under self-review only the admin
            # (auditing) and the tester's OWN record carry full content — another
            # tester never sees a peer's answers, since they never review them.
            if who["can_configure"] or row["member_id"] == who["id"]:
                result = decoded(row["result"])
                if result:
                    result = {
                        **result,
                        "screenshot_available": row["has_image"],
                    }
                    result.pop("screenshot_base64", None)
                    result.pop("evidence_removed_by", None)
                review = decoded(row["review"])
                if review:
                    review = {k: v for k, v in review.items() if k != "reviewer_member_id"}
                record.update(expected=decoded(row["expected"]), result=result, review=review)
        cases.append(
            {
                **case,
                "can_start": case["day"] == bali_today(),
                "can_record_results": case["slot"] == who["slot"] and case["day"] in ready_days,
                "scenario": decoded(row["scenario"]) if row else case["scenario"],
                "record": record,
            }
        )
    candidates = []
    if who["can_configure"]:
        candidates = [
            dict(r)
            for r in await conn.fetch(
                "SELECT id::text AS id, COALESCE(full_name,name,'Staff') AS label, role FROM team_members WHERE active=true AND lower(btrim(role))=ANY($1::text[]) ORDER BY id",
                sorted(TEAM_ROLES),
            )
            if is_human_team_member(r["role"])
        ]
        for c in candidates:
            c.pop("role", None)
    else:
        slots = [{**s, "member_id": "assigned" if s["member_id"] else None} for s in slots]
    reviews = [decoded(r["review"]) for r in rows if r["review"]]
    progress = [
        {
            "slot": slot,
            "day": day,
            "planned": 5,
            "submitted": sum(
                r["status"] == "submitted" and r["slot"] == slot and str(r["assigned_day"]) == day
                for r in rows
            ),
            "reviewed": sum(
                bool(r["review"]) and r["slot"] == slot and str(r["assigned_day"]) == day
                for r in rows
            ),
        }
        for slot in SLOTS
        for day in DAYS
    ]
    return {
        "campaign": {
            "id": CAMPAIGN_ID,
            "start_date": DAYS[0],
            "end_date": DAYS[-1],
            "timezone": "Asia/Makassar",
            "planned": 150,
            "per_day": 5,
            "plan_version": PLAN_VERSION,
        },
        "viewer": {k: v for k, v in who.items() if k != "id"},
        "slots": slots,
        "staff_candidates": candidates,
        "assignments": cases,
        "progress": progress,
        "counts": {
            "planned": 150,
            "started": len(rows),
            "submitted": sum(r["status"] == "submitted" for r in rows),
            "reproduced": sum(
                bool(r.get("reproduced")) and r.get("verdict") == "confirmed_issue" for r in reviews
            ),
            "reviewed": len(reviews),
            "reached": sum(
                r["status"] == "submitted"
                and (decoded(r["result"]) or {}).get("actual_state")
                in {"supported", "needs_input", "human_review", "no_path"}
                for r in rows
            ),
            "blocked": sum(
                r["status"] == "submitted"
                and (decoded(r["result"]) or {}).get("actual_state") in {"blocked", "unavailable"}
                for r in rows
            ),
        },
    }


@router.get("")
async def campaign(
    user: dict = Depends(require_team_member), pool: asyncpg.Pool = Depends(get_database_pool)
):
    async with pool.acquire() as conn:
        return await view(conn, await actor(conn, user))


@router.get("/export")
async def export(
    user: dict = Depends(require_team_member), pool: asyncpg.Pool = Depends(get_database_pool)
):
    async with pool.acquire() as conn:
        who = await actor(conn, user)
        if not who["can_review"]:
            raise HTTPException(403, "Reviewer required")
        data = await view(conn, who)
        # Roster identities do not belong in a portable findings export.
        data.pop("staff_candidates", None)
        data["slots"] = [{"slot": s["slot"], "reviewer": s["reviewer"]} for s in data["slots"]]
        return data


@router.put("/slots/{slot}")
async def configure_slot(
    slot: str,
    body: SlotPayload,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    if slot not in SLOTS:
        raise HTTPException(404, "Unknown slot")
    async with pool.acquire() as conn, conn.transaction():
        who = await actor(conn, user)
        if not who["can_configure"]:
            raise HTTPException(403, "Owner required")
        old = await conn.fetchrow(
            "SELECT member_id FROM visa_oracle_test_slots WHERE slot=$1 FOR UPDATE", slot
        )
        if body.member_id:
            member = await conn.fetchrow(
                "SELECT role FROM team_members WHERE id::text=$1 AND active=true", body.member_id
            )
            if not member or not is_human_team_member(member["role"]):
                raise HTTPException(422, "Assign active human staff only")
        if old["member_id"] != body.member_id and await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM visa_oracle_test_runs WHERE slot=$1 OR review->>'reviewer_slot'=$1)",
            slot,
        ):
            raise HTTPException(409, "Slot already has test history")
        try:
            await conn.execute(
                "UPDATE visa_oracle_test_slots SET member_id=$2,reviewer=$3 WHERE slot=$1",
                slot,
                body.member_id,
                body.reviewer,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(409, "Staff already assigned to another slot") from exc
    return {"ok": True}


@router.post("/{key}/start")
async def start(
    key: str,
    body: StartPayload,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    case = assignment(key)
    if case["day"] != bali_today():
        raise HTTPException(
            409,
            "Start this case on its assigned Bali date; saved observations can be completed later",
        )
    payload = body.model_dump(exclude={"synthetic_only"})
    async with pool.acquire() as conn, conn.transaction():
        who = await actor(conn, user)
        await writable_slot(conn, who, case)
        prior = await conn.fetchrow(
            "SELECT member_id,expected FROM visa_oracle_test_runs WHERE assignment_id=$1", key
        )
        if prior:
            authorize_record(who["id"], prior["member_id"])
            if decoded(prior["expected"]) != payload:
                raise HTTPException(409, "Expectation already locked")
        else:
            await conn.execute(
                "INSERT INTO visa_oracle_test_runs (assignment_id,campaign_id,plan_version,slot,member_id,assigned_day,scenario,expected) VALUES($1,$2,$3,$4,$5,$6::text::date,$7::jsonb,$8::jsonb)",
                key,
                CAMPAIGN_ID,
                PLAN_VERSION,
                case["slot"],
                who["id"],
                case["day"],
                json.dumps(case["scenario"]),
                json.dumps(payload),
            )
    return {"ok": True}


@router.put("/{key}/result")
async def result(
    key: str,
    body: ResultPayload,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    case = assignment(key)
    payload = body.model_dump(exclude={"submit", "synthetic_only", "screenshot_base64"})
    image_bytes = base64.b64decode(body.screenshot_base64) if body.screenshot_base64 else None
    async with pool.acquire() as conn, conn.transaction():
        who = await actor(conn, user)
        await writable_slot(conn, who, case)
        row = await conn.fetchrow(
            "SELECT member_id,status,result,screenshot FROM visa_oracle_test_runs WHERE assignment_id=$1 FOR UPDATE",
            key,
        )
        if not row:
            raise HTTPException(409, "Lock expectation before recording results")
        authorize_record(who["id"], row["member_id"])
        if case["day"] not in await expectation_days(conn, who):
            raise HTTPException(
                409, "Lock all five personal expectations for this day before recording results"
            )
        if body.submit:
            validate_submission(body, has_stored_image=row["screenshot"] is not None)
        prior = decoded(row["result"]) or {}
        # Evidence-removal audit fields are server owned and never part of an edit.
        content = {k: v for k, v in prior.items() if not k.startswith("evidence_removed_")}
        if row["status"] == "submitted":
            if (
                not body.submit
                or content != payload
                or (image_bytes is not None and image_bytes != row["screenshot"])
            ):
                raise HTTPException(409, "Submitted result is immutable")
        else:
            await conn.execute(
                "UPDATE visa_oracle_test_runs SET result=$2::jsonb,status=$3,submitted_at=CASE WHEN $4 THEN NOW() ELSE NULL END,screenshot=COALESCE($5::bytea,screenshot) WHERE assignment_id=$1",
                key,
                json.dumps(
                    {
                        **{k: v for k, v in prior.items() if k.startswith("evidence_removed_")},
                        **payload,
                    }
                ),
                "submitted" if body.submit else "started",
                body.submit,
                image_bytes,
            )
    return {"ok": True}


@router.patch("/{key}/review")
async def review(
    key: str,
    body: ReviewPayload,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    assignment(key)
    if body.reproduced and len(body.reproduction_evidence.strip()) < 8:
        raise HTTPException(422, "Reproduction requires an independent evidence record")
    async with pool.acquire() as conn, conn.transaction():
        who = await actor(conn, user)
        if not who["can_review"]:
            raise HTTPException(403, "Reviewer required")
        row = await conn.fetchrow(
            "SELECT member_id,status,review,assigned_day FROM visa_oracle_test_runs WHERE assignment_id=$1 FOR UPDATE",
            key,
        )
        if not row or row["status"] != "submitted":
            raise HTTPException(409, "Only submitted tests can be reviewed")
        authorize_record(who["id"], row["member_id"], review=True, override=who["can_configure"])
        if str(row["assigned_day"]) not in await review_days(conn, who):
            raise HTTPException(
                409, "Lock all five personal expectations for this day before reviewing peers"
            )
        if row["review"]:
            prior = decoded(row["review"])
            if prior.get("reviewer_member_id") == who["id"] and all(
                prior.get(k) == v for k, v in body.model_dump().items()
            ):
                return {"ok": True}
            raise HTTPException(409, "Review already recorded")
        payload = {
            **body.model_dump(),
            "reviewed_at": datetime.now(ZoneInfo("UTC")).isoformat(),
            "reviewer_slot": who["slot"] or "OWNER",
            "reviewer_member_id": who["id"],
        }
        await conn.execute(
            "UPDATE visa_oracle_test_runs SET review=$2::jsonb WHERE assignment_id=$1",
            key,
            json.dumps(payload),
        )
    return {"ok": True}


@router.get("/{key}/screenshot")
async def screenshot(
    key: str,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    assignment(key)
    async with pool.acquire() as conn:
        who = await actor(conn, user)
        row = await conn.fetchrow(
            "SELECT member_id,screenshot FROM visa_oracle_test_runs WHERE assignment_id=$1", key
        )
        # Self-review: only the admin (auditing) or the tester's own evidence.
        if not row or not (who["can_configure"] or who["id"] == row["member_id"]):
            raise HTTPException(404, "Evidence unavailable")
        value = row["screenshot"]
        if not value:
            raise HTTPException(404, "Evidence unavailable")
        image_bytes = value
        with Image.open(io.BytesIO(image_bytes)) as im:
            media_type = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}[im.format]
        return Response(
            image_bytes,
            media_type=media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


@router.delete("/{key}/screenshot")
async def remove_screenshot(
    key: str,
    user: dict = Depends(require_team_member),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    assignment(key)
    async with pool.acquire() as conn, conn.transaction():
        who = await actor(conn, user)
        row = await conn.fetchrow(
            "SELECT member_id FROM visa_oracle_test_runs WHERE assignment_id=$1 FOR UPDATE", key
        )
        if not row or not (who["id"] == row["member_id"] or who["can_configure"]):
            raise HTTPException(404, "Evidence unavailable")
        await conn.execute(
            "UPDATE visa_oracle_test_runs SET screenshot=NULL,result=COALESCE(result,'{}'::jsonb) || jsonb_build_object('evidence_removed_at',NOW(),'evidence_removed_by',$2::text) WHERE assignment_id=$1 AND screenshot IS NOT NULL",
            key,
            who["id"],
        )
    return {"ok": True}
