from cell_observatory.storage import Storage


async def compute_daily_rollup(storage: Storage, day: str) -> None:
    """Aggregate pulse_events + classifications into pulse_daily_rollup for `day` (YYYY-MM-DD WITA)."""
    sql = """
    INSERT OR REPLACE INTO pulse_daily_rollup
        (day, cell_id, n_pulse, n_self_green, n_self_yellow, n_self_red,
         n_classified, n_anomaly, n_critical, n_disagree, cost_usd)
    SELECT
        ?, e.cell_id,
        COUNT(*),
        SUM(CASE WHEN e.classifier_self='green' THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.classifier_self='yellow' THEN 1 ELSE 0 END),
        SUM(CASE WHEN e.classifier_self='red' THEN 1 ELSE 0 END),
        COUNT(c.outbox_id),
        SUM(CASE WHEN c.label='anomaly' THEN 1 ELSE 0 END),
        SUM(CASE WHEN c.label='critical' THEN 1 ELSE 0 END),
        SUM(CASE WHEN c.label_diff='disagree' THEN 1 ELSE 0 END),
        COALESCE(SUM(c.cost_usd), 0.0)
    FROM pulse_events e
    LEFT JOIN pulse_classifications c ON c.outbox_id = e.outbox_id
    WHERE date(e.pulse_timestamp/1000, 'unixepoch', '+8 hours') = ?
    GROUP BY e.cell_id
    """
    assert storage._conn is not None
    await storage._conn.execute(sql, (day, day))
    await storage._conn.commit()
