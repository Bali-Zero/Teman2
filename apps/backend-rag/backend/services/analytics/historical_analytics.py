"""
Historical Analytics Service
Tracks completion rates, response times, and practice performance metrics.

Features:
- Practice completion rate by type
- Average response time (inquiry to completion)
- SLA compliance tracking
- Monthly/quarterly performance reports
- Client satisfaction metrics
- Agent performance metrics

Metrics Tracked:
- Completion rate (completed / total practices)
- Avg days to completion
- Avg days inquiry -> start
- Avg days start -> completion
- Overdue rate
- Cancellation rate
- Revenue per practice type
- Client retention rate
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any

import structlog
from prometheus_client import Gauge, Histogram

logger = structlog.get_logger(__name__)

# Metrics
completion_rate = Gauge(
    "analytics_completion_rate", "Practice completion rate", ["practice_type", "period"],
)
avg_completion_days = Gauge(
    "analytics_avg_completion_days",
    "Average days to complete practice",
    ["practice_type", "period"],
)
avg_response_days = Gauge(
    "analytics_avg_response_days",
    "Average days from inquiry to start",
    ["practice_type", "period"],
)
sla_compliance_rate = Gauge(
    "analytics_sla_compliance", "SLA compliance rate", ["practice_type", "period"],
)
revenue_total = Gauge("analytics_revenue_total", "Total revenue", ["practice_type", "period"])

# Histograms for distribution analysis
completion_days_histogram = Histogram(
    "analytics_completion_days_histogram",
    "Distribution of completion days",
    ["practice_type"],
    buckets=[7, 14, 30, 60, 90, 180, 365],
)
response_days_histogram = Histogram(
    "analytics_response_days_histogram",
    "Distribution of response days",
    ["practice_type"],
    buckets=[1, 3, 7, 14, 30],
)


async def calculate_completion_rate(
    db_pool,
    practice_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Calculate practice completion rate.

    Args:
        db_pool: Database connection pool
        practice_type: Filter by practice type code (optional)
        start_date: Start date for analysis period (optional)
        end_date: End date for analysis period (optional)

    Returns:
        dict with completion metrics
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                pt.code as practice_type,
                pt.name as practice_name,
                COUNT(*) as total_practices,
                COUNT(*) FILTER (WHERE p.status = 'completed') as completed_practices,
                COUNT(*) FILTER (WHERE p.status = 'cancelled') as cancelled_practices,
                ROUND(
                    COUNT(*) FILTER (WHERE p.status = 'completed')::numeric /
                    NULLIF(COUNT(*), 0) * 100,
                    2
                ) as completion_rate_pct
            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE 1=1
        """
        params = []

        if practice_type:
            query += f" AND pt.code = ${len(params) + 1}"
            params.append(practice_type)

        if start_date:
            query += f" AND p.inquiry_date >= ${len(params) + 1}"
            params.append(start_date)

        if end_date:
            query += f" AND p.inquiry_date <= ${len(params) + 1}"
            params.append(end_date)

        query += " GROUP BY pt.code, pt.name ORDER BY completion_rate_pct DESC"

        rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(
                {
                    "practice_type": row["practice_type"],
                    "practice_name": row["practice_name"],
                    "total_practices": row["total_practices"],
                    "completed_practices": row["completed_practices"],
                    "cancelled_practices": row["cancelled_practices"],
                    "completion_rate_pct": float(row["completion_rate_pct"] or 0),
                },
            )

            # Update Prometheus metric
            period = f"{start_date}_{end_date}" if start_date and end_date else "all_time"
            completion_rate.labels(practice_type=row["practice_type"], period=period).set(
                float(row["completion_rate_pct"] or 0),
            )

        return {"results": results, "period": {"start": start_date, "end": end_date}}


async def calculate_response_times(
    db_pool,
    practice_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Calculate average response times (inquiry to start, start to completion).

    Args:
        db_pool: Database connection pool
        practice_type: Filter by practice type code (optional)
        start_date: Start date for analysis period (optional)
        end_date: End date for analysis period (optional)

    Returns:
        dict with response time metrics
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                pt.code as practice_type,
                pt.name as practice_name,
                COUNT(*) as total_practices,

                -- Inquiry to Start
                ROUND(AVG(EXTRACT(EPOCH FROM (p.start_date - p.inquiry_date)) / 86400), 2)
                    as avg_days_inquiry_to_start,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (p.start_date - p.inquiry_date)) / 86400), 2)
                    as median_days_inquiry_to_start,

                -- Start to Completion
                ROUND(AVG(EXTRACT(EPOCH FROM (p.completion_date - p.start_date)) / 86400), 2)
                    as avg_days_start_to_completion,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (p.completion_date - p.start_date)) / 86400), 2)
                    as median_days_start_to_completion,

                -- Total Cycle Time
                ROUND(AVG(EXTRACT(EPOCH FROM (p.completion_date - p.inquiry_date)) / 86400), 2)
                    as avg_days_total_cycle,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (p.completion_date - p.inquiry_date)) / 86400), 2)
                    as median_days_total_cycle

            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.status = 'completed'
              AND p.start_date IS NOT NULL
              AND p.completion_date IS NOT NULL
        """
        params = []

        if practice_type:
            query += f" AND pt.code = ${len(params) + 1}"
            params.append(practice_type)

        if start_date:
            query += f" AND p.inquiry_date >= ${len(params) + 1}"
            params.append(start_date)

        if end_date:
            query += f" AND p.inquiry_date <= ${len(params) + 1}"
            params.append(end_date)

        query += " GROUP BY pt.code, pt.name ORDER BY avg_days_total_cycle ASC"

        rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(
                {
                    "practice_type": row["practice_type"],
                    "practice_name": row["practice_name"],
                    "total_practices": row["total_practices"],
                    "avg_days_inquiry_to_start": float(row["avg_days_inquiry_to_start"] or 0),
                    "median_days_inquiry_to_start": float(row["median_days_inquiry_to_start"] or 0),
                    "avg_days_start_to_completion": float(row["avg_days_start_to_completion"] or 0),
                    "median_days_start_to_completion": float(
                        row["median_days_start_to_completion"] or 0,
                    ),
                    "avg_days_total_cycle": float(row["avg_days_total_cycle"] or 0),
                    "median_days_total_cycle": float(row["median_days_total_cycle"] or 0),
                },
            )

            # Update Prometheus metrics
            period = f"{start_date}_{end_date}" if start_date and end_date else "all_time"
            avg_response_days.labels(practice_type=row["practice_type"], period=period).set(
                float(row["avg_days_inquiry_to_start"] or 0),
            )
            avg_completion_days.labels(practice_type=row["practice_type"], period=period).set(
                float(row["avg_days_total_cycle"] or 0),
            )

        return {"results": results, "period": {"start": start_date, "end": end_date}}


async def calculate_sla_compliance(
    db_pool,
    practice_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Calculate SLA compliance rate (practices completed within expected duration).

    Args:
        db_pool: Database connection pool
        practice_type: Filter by practice type code (optional)
        start_date: Start date for analysis period (optional)
        end_date: End date for analysis period (optional)

    Returns:
        dict with SLA compliance metrics
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                pt.code as practice_type,
                pt.name as practice_name,
                pt.duration_days as expected_duration,
                COUNT(*) as total_completed,
                COUNT(*) FILTER (
                    WHERE EXTRACT(EPOCH FROM (p.completion_date - p.inquiry_date)) / 86400 <= pt.duration_days
                ) as within_sla,
                ROUND(
                    COUNT(*) FILTER (
                        WHERE EXTRACT(EPOCH FROM (p.completion_date - p.inquiry_date)) / 86400 <= pt.duration_days
                    )::numeric / NULLIF(COUNT(*), 0) * 100,
                    2
                ) as sla_compliance_pct
            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.status = 'completed'
              AND p.completion_date IS NOT NULL
              AND pt.duration_days IS NOT NULL
        """
        params = []

        if practice_type:
            query += f" AND pt.code = ${len(params) + 1}"
            params.append(practice_type)

        if start_date:
            query += f" AND p.inquiry_date >= ${len(params) + 1}"
            params.append(start_date)

        if end_date:
            query += f" AND p.inquiry_date <= ${len(params) + 1}"
            params.append(end_date)

        query += " GROUP BY pt.code, pt.name, pt.duration_days ORDER BY sla_compliance_pct DESC"

        rows = await conn.fetch(query, *params)

        results = []
        for row in rows:
            results.append(
                {
                    "practice_type": row["practice_type"],
                    "practice_name": row["practice_name"],
                    "expected_duration": row["expected_duration"],
                    "total_completed": row["total_completed"],
                    "within_sla": row["within_sla"],
                    "sla_compliance_pct": float(row["sla_compliance_pct"] or 0),
                },
            )

            # Update Prometheus metric
            period = f"{start_date}_{end_date}" if start_date and end_date else "all_time"
            sla_compliance_rate.labels(practice_type=row["practice_type"], period=period).set(
                float(row["sla_compliance_pct"] or 0),
            )

        return {"results": results, "period": {"start": start_date, "end": end_date}}


async def calculate_revenue_metrics(
    db_pool,
    practice_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """
    Calculate revenue metrics by practice type.

    Args:
        db_pool: Database connection pool
        practice_type: Filter by practice type code (optional)
        start_date: Start date for analysis period (optional)
        end_date: End date for analysis period (optional)

    Returns:
        dict with revenue metrics
    """
    async with db_pool.acquire() as conn:
        query = """
            SELECT
                pt.code as practice_type,
                pt.name as practice_name,
                COUNT(*) as total_practices,
                SUM(p.actual_price) as total_revenue,
                AVG(p.actual_price) as avg_revenue_per_practice,
                SUM(p.paid_amount) as total_paid,
                SUM(p.actual_price - p.paid_amount) as total_outstanding,
                COUNT(*) FILTER (WHERE p.payment_status = 'paid') as fully_paid_count,
                ROUND(
                    COUNT(*) FILTER (WHERE p.payment_status = 'paid')::numeric /
                    NULLIF(COUNT(*), 0) * 100,
                    2
                ) as payment_completion_rate_pct
            FROM practices p
            JOIN practice_types pt ON p.practice_type_id = pt.id
            WHERE p.status IN ('completed', 'in_progress')
              AND p.actual_price IS NOT NULL
              AND p.actual_price > 0
        """
        params = []

        if practice_type:
            query += f" AND pt.code = ${len(params) + 1}"
            params.append(practice_type)

        if start_date:
            query += f" AND p.inquiry_date >= ${len(params) + 1}"
            params.append(start_date)

        if end_date:
            query += f" AND p.inquiry_date <= ${len(params) + 1}"
            params.append(end_date)

        query += " GROUP BY pt.code, pt.name ORDER BY total_revenue DESC"

        rows = await conn.fetch(query, *params)

        results = []
        total_all_types = 0
        for row in rows:
            total_rev = float(row["total_revenue"] or 0)
            total_all_types += total_rev

            results.append(
                {
                    "practice_type": row["practice_type"],
                    "practice_name": row["practice_name"],
                    "total_practices": row["total_practices"],
                    "total_revenue": total_rev,
                    "avg_revenue_per_practice": float(row["avg_revenue_per_practice"] or 0),
                    "total_paid": float(row["total_paid"] or 0),
                    "total_outstanding": float(row["total_outstanding"] or 0),
                    "fully_paid_count": row["fully_paid_count"],
                    "payment_completion_rate_pct": float(row["payment_completion_rate_pct"] or 0),
                },
            )

            # Update Prometheus metric
            period = f"{start_date}_{end_date}" if start_date and end_date else "all_time"
            revenue_total.labels(practice_type=row["practice_type"], period=period).set(total_rev)

        return {
            "results": results,
            "total_revenue_all_types": total_all_types,
            "period": {"start": start_date, "end": end_date},
        }


async def generate_monthly_report(db_pool, year: int, month: int) -> dict:
    """
    Generate comprehensive monthly analytics report.

    Args:
        db_pool: Database connection pool
        year: Year (e.g., 2026)
        month: Month (1-12)

    Returns:
        dict with full monthly report
    """
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    logger.info(f"Generating monthly report for {year}-{month:02d}")

    # Run all analytics in parallel
    completion, response_times, sla, revenue = await asyncio.gather(
        calculate_completion_rate(db_pool, start_date=start_date, end_date=end_date),
        calculate_response_times(db_pool, start_date=start_date, end_date=end_date),
        calculate_sla_compliance(db_pool, start_date=start_date, end_date=end_date),
        calculate_revenue_metrics(db_pool, start_date=start_date, end_date=end_date),
    )

    report = {
        "period": {"year": year, "month": month, "start_date": start_date, "end_date": end_date},
        "completion_rates": completion,
        "response_times": response_times,
        "sla_compliance": sla,
        "revenue": revenue,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"Monthly report generated: {len(completion['results'])} practice types analyzed")

    return report


async def main() -> Any:
    """Entry point for direct execution (generate report)"""
    import asyncpg

    from backend.app.core.config import settings

    db_pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)

    try:
        # Generate current month report
        now = datetime.now(timezone.utc)
        report = await generate_monthly_report(db_pool, now.year, now.month)

        # Print summary
        logger.info("=" * 60)
        logger.info(f"MONTHLY REPORT: {report['period']['year']}-{report['period']['month']:02d}")
        logger.info("=" * 60)

        logger.info("\n📊 COMPLETION RATES:")
        for item in report["completion_rates"]["results"][:5]:
            logger.info(
                f"  {item['practice_name']}: {item['completion_rate_pct']}% ({item['completed_practices']}/{item['total_practices']})",
            )

        logger.info("\n⏱️  RESPONSE TIMES:")
        for item in report["response_times"]["results"][:5]:
            logger.info(
                f"  {item['practice_name']}: {item['avg_days_total_cycle']} days avg cycle time",
            )

        logger.info("\n✅ SLA COMPLIANCE:")
        for item in report["sla_compliance"]["results"][:5]:
            logger.info(f"  {item['practice_name']}: {item['sla_compliance_pct']}% within SLA")

        logger.info("\n💰 REVENUE:")
        for item in report["revenue"]["results"][:5]:
            logger.info(f"  {item['practice_name']}: Rp {item['total_revenue']:,.0f} total revenue")

        logger.info(f"\n💵 TOTAL REVENUE: Rp {report['revenue']['total_revenue_all_types']:,.0f}")

        return report

    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
