"""SEO Cell sensors — 6 perception surfaces per v2.1 design.

  1. GSCSensor              — Google Search Console query performance
  2. GA4Sensor              — Google Analytics 4 conversion funnel
  3. CompetitorSERPSensor   — SERP positions vs Cekindo + Emerhub (cache 7gg)
  4. KGSensor               — Knowledge Graph coverage per query
  5. WarRoomEventSensor     — consumes war_room.event PG channel (Redis fanout)
  6. CannibalizationSensor  — semantic clustering of own URLs competing

Sprint 1 state: all are STUBS that return yellow status with metadata
{"stub": True}. Real I/O lands in Sprint 2, guarded by pre_natal gate
(sensors always read; the thinker ignores them until graduation).
"""
from apps.evaluator.seo_cell.sensors.gsc_sensor import GSCSensor
from apps.evaluator.seo_cell.sensors.ga4_sensor import GA4Sensor
from apps.evaluator.seo_cell.sensors.competitor_serp_sensor import CompetitorSERPSensor
from apps.evaluator.seo_cell.sensors.kg_sensor import KGSensor
from apps.evaluator.seo_cell.sensors.war_room_event_sensor import WarRoomEventSensor
from apps.evaluator.seo_cell.sensors.cannibalization_sensor import CannibalizationSensor

__all__ = [
    "GSCSensor",
    "GA4Sensor",
    "CompetitorSERPSensor",
    "KGSensor",
    "WarRoomEventSensor",
    "CannibalizationSensor",
]
