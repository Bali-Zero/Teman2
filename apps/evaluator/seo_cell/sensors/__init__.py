"""SEO Cell sensors — 7 perception surfaces (6 v2.1 + lead_attribution).

  1. GSCSensor               — Google Search Console query performance
  2. GA4Sensor               — Google Analytics 4 conversion funnel
  3. CompetitorSERPSensor    — SERP positions vs Cekindo + Emerhub (cache 7gg)
  4. KGSensor                — Knowledge Graph coverage per query
  5. WarRoomEventSensor      — consumes war_room.event PG channel (Redis fanout)
  6. CannibalizationSensor   — semantic clustering of own URLs competing
  7. LeadAttributionSensor   — counts website-organic leads (Sprint 2)

The 7th sensor is NOT in the Bayesian calibrator's weight contract
(SENSOR_NAMES is still the original 6) — it feeds the pre_natal unlock
gate exclusively, not the post-graduation scoring path.
"""
from apps.evaluator.seo_cell.sensors.gsc_sensor import GSCSensor
from apps.evaluator.seo_cell.sensors.ga4_sensor import GA4Sensor
from apps.evaluator.seo_cell.sensors.competitor_serp_sensor import CompetitorSERPSensor
from apps.evaluator.seo_cell.sensors.kg_sensor import KGSensor
from apps.evaluator.seo_cell.sensors.war_room_event_sensor import WarRoomEventSensor
from apps.evaluator.seo_cell.sensors.cannibalization_sensor import CannibalizationSensor
from apps.evaluator.seo_cell.sensors.lead_attribution_sensor import LeadAttributionSensor

__all__ = [
    "GSCSensor",
    "GA4Sensor",
    "CompetitorSERPSensor",
    "KGSensor",
    "WarRoomEventSensor",
    "CannibalizationSensor",
    "LeadAttributionSensor",
]
