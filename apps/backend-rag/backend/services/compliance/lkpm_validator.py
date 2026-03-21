"""
LKPM Validator — deterministic validation rules for LKPM reports.

All checks are boolean/arithmetic — no AI involved.
Returns a list of ValidationAlert (green/yellow/red) per field.
"""

import logging

import asyncpg

from backend.app.models.lkpm import (
    LKPMClientConfig,
    LKPMDraft,
    LKPMValidationResult,
    ValidationAlert,
    ValidationSeverity,
)

logger = logging.getLogger(__name__)


class LKPMValidator:
    """Deterministic validator for LKPM drafts."""

    # Consecutive zero-realization quarters before red alert
    ZERO_REALIZATION_THRESHOLD = 4

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    async def validate(
        self,
        draft: LKPMDraft,
        config: LKPMClientConfig,
    ) -> LKPMValidationResult:
        """Run all validation checks and return consolidated result."""
        alerts: list[ValidationAlert] = []

        # 1. KBLI match
        kbli_alerts = await self.validate_kbli_match(draft.client_id, config.kbli_codes)
        alerts.extend(kbli_alerts)

        # 2. WNA (foreign worker) count cross-check
        wna_alerts = await self.validate_wna_count(draft.employment.tka, draft.client_id)
        alerts.extend(wna_alerts)

        # 3. Zero realization detection
        zero_alerts = await self.detect_zero_realization(draft.client_id)
        alerts.extend(zero_alerts)

        # 4. Cross-check consistency (realized ≤ planned)
        consistency_alerts = self.cross_check_consistency(draft, config)
        alerts.extend(consistency_alerts)

        # 5. Basic completeness
        completeness_alerts = self.check_completeness(draft)
        alerts.extend(completeness_alerts)

        red_count = sum(1 for a in alerts if a.severity == ValidationSeverity.RED)
        yellow_count = sum(1 for a in alerts if a.severity == ValidationSeverity.YELLOW)
        green_count = sum(1 for a in alerts if a.severity == ValidationSeverity.GREEN)

        return LKPMValidationResult(
            is_valid=red_count == 0,
            alerts=alerts,
            red_count=red_count,
            yellow_count=yellow_count,
            green_count=green_count,
        )

    async def validate_kbli_match(
        self,
        client_id: int,
        registered_kbli: list[str],
    ) -> list[ValidationAlert]:
        """Check that client's registered KBLI codes exist in our KBLI database."""
        alerts: list[ValidationAlert] = []

        if not registered_kbli:
            alerts.append(
                ValidationAlert(
                    field="kbli_codes",
                    severity=ValidationSeverity.RED,
                    message="No KBLI codes registered for this client",
                    details="LKPM requires at least one registered KBLI code",
                )
            )
            return alerts

        # Verify KBLI codes exist in kg_nodes (entity_id format: kbli:{code})
        try:
            async with self.db_pool.acquire() as conn:
                found_codes = await conn.fetch(
                    """
                    SELECT entity_id FROM kg_nodes
                    WHERE entity_id = ANY($1::text[])
                    """,
                    [f"kbli:{code}" for code in registered_kbli],
                )
                found_set = {row["entity_id"].replace("kbli:", "") for row in found_codes}
        except Exception as e:
            logger.warning(f"KBLI validation query failed: {e}")
            found_set = set()

        for code in registered_kbli:
            if code in found_set:
                alerts.append(
                    ValidationAlert(
                        field=f"kbli_{code}",
                        severity=ValidationSeverity.GREEN,
                        message=f"KBLI {code} verified",
                    )
                )
            else:
                alerts.append(
                    ValidationAlert(
                        field=f"kbli_{code}",
                        severity=ValidationSeverity.YELLOW,
                        message=f"KBLI {code} not found in knowledge base",
                        details="Code may be valid but not in our database — verify manually",
                    )
                )

        return alerts

    async def validate_wna_count(
        self,
        reported_tka: int,
        client_id: int,
    ) -> list[ValidationAlert]:
        """Cross-check reported TKA (foreign workers) count against CRM KITAS data."""
        alerts: list[ValidationAlert] = []

        # Count active KITAS records for this client from CRM
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as kitas_count
                    FROM practices
                    WHERE client_id = $1
                      AND practice_type ILIKE '%kitas%'
                      AND status IN ('active', 'in_progress', 'completed')
                    """,
                    client_id,
                )
                crm_kitas_count = row["kitas_count"] if row else 0
        except Exception as e:
            logger.warning(f"WNA count query failed: {e}")
            crm_kitas_count = -1  # Unknown

        if crm_kitas_count < 0:
            alerts.append(
                ValidationAlert(
                    field="tka_count",
                    severity=ValidationSeverity.YELLOW,
                    message="Could not verify TKA count against CRM",
                    details="Database query failed — verify manually",
                )
            )
        elif reported_tka == crm_kitas_count:
            alerts.append(
                ValidationAlert(
                    field="tka_count",
                    severity=ValidationSeverity.GREEN,
                    message=f"TKA count matches CRM ({reported_tka})",
                )
            )
        else:
            alerts.append(
                ValidationAlert(
                    field="tka_count",
                    severity=ValidationSeverity.YELLOW,
                    message=f"TKA count mismatch: reported={reported_tka}, CRM KITAS={crm_kitas_count}",
                    details="Verify foreign worker count before submission",
                )
            )

        return alerts

    async def detect_zero_realization(self, client_id: int) -> list[ValidationAlert]:
        """Count consecutive quarters with zero investment realization."""
        alerts: list[ValidationAlert] = []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT year, quarter,
                           (realized_equipment_domestic + realized_equipment_import +
                            realized_building_domestic + realized_building_import +
                            realized_vehicle_domestic + realized_vehicle_import +
                            realized_land + realized_working_capital + realized_other) as total
                    FROM lkpm_reports
                    WHERE client_id = $1
                    ORDER BY year DESC, quarter DESC
                    LIMIT 8
                    """,
                    client_id,
                )
        except Exception as e:
            logger.warning(f"Zero realization query failed: {e}")
            return alerts

        consecutive_zero = 0
        for row in rows:
            if row["total"] == 0:
                consecutive_zero += 1
            else:
                break

        if consecutive_zero >= self.ZERO_REALIZATION_THRESHOLD:
            alerts.append(
                ValidationAlert(
                    field="investment_realization",
                    severity=ValidationSeverity.RED,
                    message=f"{consecutive_zero} consecutive quarters with zero realization",
                    details=(
                        "BKPM may require explanation for prolonged zero realization. "
                        "Consider adding narrative_obstacles."
                    ),
                )
            )
        elif consecutive_zero >= 2:
            alerts.append(
                ValidationAlert(
                    field="investment_realization",
                    severity=ValidationSeverity.YELLOW,
                    message=f"{consecutive_zero} consecutive quarters with zero realization",
                    details="Consider adding explanation in narrative_obstacles",
                )
            )

        return alerts

    def cross_check_consistency(
        self,
        draft: LKPMDraft,
        config: LKPMClientConfig,
    ) -> list[ValidationAlert]:
        """Check that cumulative realized ≤ planned for each category."""
        alerts: list[ValidationAlert] = []

        checks = [
            (
                "equipment_domestic",
                draft.cumulative.equipment_domestic,
                config.planned.equipment_domestic,
            ),
            (
                "equipment_import",
                draft.cumulative.equipment_import,
                config.planned.equipment_import,
            ),
            (
                "building_domestic",
                draft.cumulative.building_domestic,
                config.planned.building_domestic,
            ),
            ("building_import", draft.cumulative.building_import, config.planned.building_import),
            (
                "vehicle_domestic",
                draft.cumulative.vehicle_domestic,
                config.planned.vehicle_domestic,
            ),
            ("vehicle_import", draft.cumulative.vehicle_import, config.planned.vehicle_import),
            ("land", draft.cumulative.land, config.planned.land),
            ("working_capital", draft.cumulative.working_capital, config.planned.working_capital),
            ("other", draft.cumulative.other, config.planned.other),
        ]

        for field_name, realized, planned in checks:
            if planned == 0 and realized == 0:
                continue  # Skip categories with no plan and no realization

            if planned > 0 and realized > planned:
                alerts.append(
                    ValidationAlert(
                        field=field_name,
                        severity=ValidationSeverity.YELLOW,
                        message=(
                            f"Cumulative {field_name} (Rp {realized:,}) "
                            f"exceeds plan (Rp {planned:,})"
                        ),
                        details="Over-realization is allowed but should be noted in narrative",
                    )
                )
            elif planned > 0:
                pct = (realized / planned) * 100
                alerts.append(
                    ValidationAlert(
                        field=field_name,
                        severity=ValidationSeverity.GREEN,
                        message=f"{field_name}: {pct:.1f}% of plan realized",
                    )
                )

        return alerts

    def check_completeness(self, draft: LKPMDraft) -> list[ValidationAlert]:
        """Check that required fields are filled."""
        alerts: list[ValidationAlert] = []

        # Check if all realization values are zero but revenue is non-zero
        if draft.realized.grand_total == 0 and draft.quarterly_revenue > 0:
            alerts.append(
                ValidationAlert(
                    field="realization_vs_revenue",
                    severity=ValidationSeverity.YELLOW,
                    message="Zero investment realization but non-zero revenue",
                    details="Company is generating revenue without investment — verify this is correct",
                )
            )

        # Check AI-categorized items
        if draft.has_ai_categorized_items:
            alerts.append(
                ValidationAlert(
                    field="ai_categorization",
                    severity=ValidationSeverity.YELLOW,
                    message=f"{draft.ai_categorized_count} transactions categorized by AI",
                    details="Review AI-categorized items before submission",
                )
            )

        # Check employment totals
        if draft.employment.tka > 0 and draft.employment.tki == 0:
            alerts.append(
                ValidationAlert(
                    field="employment",
                    severity=ValidationSeverity.YELLOW,
                    message="Foreign workers reported but zero local workers",
                    details="PT PMA must employ local workers — verify employment data",
                )
            )

        return alerts
