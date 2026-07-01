-- 241_wa_lid_phone_resolution_group_senders.sql
--
-- Extend the wa_lid_phone_resolution materialized view to also resolve GROUP
-- SENDER LIDs, not just counterpart LIDs. Until now ~86 group senders showed as
-- "Contatto sconosciuto" in the WA dashboard even though their real phone was
-- present in the message key (participant <-> participantAlt pairing).
--
-- Also: this view was created ad-hoc directly on the DB and never lived in the
-- repo. This migration versions it (idempotent DROP + CREATE) so its definition
-- is finally source-controlled.
--
-- v1 branch (unchanged): counterpart_lid, phone anywhere in raw_baileys_event.
-- v2 branch (new): group sender_lid mapped to phone via the EXACT Baileys key
--   pairing  key.participant ("<lid>@lid")  <->  key.participantAlt ("<phone>@s.whatsapp.net").
-- Team-member phones are excluded; the most frequent phone per LID wins (rk=1).
--
-- Verified on live nuzantara_dev before shipping: 569 -> 659 rows (+90 resolved),
-- 0 changed-phone regressions, 0 lost resolutions.
--
DROP MATERIALIZED VIEW IF EXISTS wa_lid_phone_resolution;

CREATE MATERIALIZED VIEW wa_lid_phone_resolution AS
WITH team_phones AS (
  SELECT DISTINCT regexp_replace(team_member_phone::text, '\D', '', 'g') AS phone_digits
  FROM whatsapp_message_context
  WHERE team_member_phone IS NOT NULL
),
extracted_counterpart AS (
  SELECT counterpart_lid AS lid,
         (regexp_matches(raw_baileys_event::text, '([0-9]{8,16})@s\.whatsapp\.net', 'g'))[1] AS phone_digits
  FROM whatsapp_message_context
  WHERE counterpart_lid IS NOT NULL
    AND raw_baileys_event <> '{}'::jsonb
),
extracted_sender AS (
  SELECT sender_lid AS lid,
         regexp_replace(
           (raw_baileys_event #>> '{key,participantAlt}'), '@s\.whatsapp\.net$', ''
         ) AS phone_digits
  FROM whatsapp_message_context
  WHERE sender_lid IS NOT NULL
    AND (raw_baileys_event #>> '{key,participant}') = sender_lid || '@lid'
    AND (raw_baileys_event #>> '{key,participantAlt}') ~ '^[0-9]{8,16}@s\.whatsapp\.net$'
),
combined AS (
  SELECT lid, phone_digits FROM extracted_counterpart
  UNION ALL
  SELECT lid, phone_digits FROM extracted_sender
),
ranked AS (
  SELECT c.lid AS counterpart_lid,
         c.phone_digits,
         count(*) AS freq,
         row_number() OVER (PARTITION BY c.lid ORDER BY count(*) DESC) AS rk
  FROM combined c
  WHERE c.phone_digits IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM team_phones t WHERE t.phone_digits = c.phone_digits)
  GROUP BY c.lid, c.phone_digits
)
SELECT counterpart_lid,
       '+' || phone_digits AS resolved_phone,
       phone_digits AS phone_normalized,
       freq AS occurrences,
       now() AS computed_at
FROM ranked
WHERE rk = 1;

-- Indexes match the original definition (UNIQUE lid so REFRESH CONCURRENTLY works).
CREATE UNIQUE INDEX wa_lid_phone_resolution_lid_idx
  ON wa_lid_phone_resolution (counterpart_lid);
CREATE INDEX wa_lid_phone_resolution_phone_idx
  ON wa_lid_phone_resolution (phone_normalized);

-- === ROLLBACK ===
-- Restores the v1 definition (counterpart_lid only, no group-sender branch).
-- DROP MATERIALIZED VIEW IF EXISTS wa_lid_phone_resolution;
-- CREATE MATERIALIZED VIEW wa_lid_phone_resolution AS
-- WITH team_phones AS (
--   SELECT DISTINCT regexp_replace(team_member_phone::text, '\D', '', 'g') AS phone_digits
--   FROM whatsapp_message_context WHERE team_member_phone IS NOT NULL
-- ), extracted AS (
--   SELECT counterpart_lid,
--          (regexp_matches(raw_baileys_event::text, '([0-9]{8,16})@s\.whatsapp\.net', 'g'))[1] AS phone_digits
--   FROM whatsapp_message_context
--   WHERE counterpart_lid IS NOT NULL AND raw_baileys_event <> '{}'::jsonb
-- ), ranked AS (
--   SELECT e.counterpart_lid, e.phone_digits, count(*) AS freq,
--          row_number() OVER (PARTITION BY e.counterpart_lid ORDER BY count(*) DESC) AS rk
--   FROM extracted e
--   WHERE NOT EXISTS (SELECT 1 FROM team_phones t WHERE t.phone_digits = e.phone_digits)
--   GROUP BY e.counterpart_lid, e.phone_digits
-- )
-- SELECT counterpart_lid, '+' || phone_digits AS resolved_phone, phone_digits AS phone_normalized,
--        freq AS occurrences, now() AS computed_at
-- FROM ranked WHERE rk = 1;
-- CREATE UNIQUE INDEX wa_lid_phone_resolution_lid_idx ON wa_lid_phone_resolution (counterpart_lid);
-- CREATE INDEX wa_lid_phone_resolution_phone_idx ON wa_lid_phone_resolution (phone_normalized);
