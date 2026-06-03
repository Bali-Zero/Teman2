-- 208_olympus_safety_envelope_rules.sql
-- Olympus DB Guardian — Safety Envelope (P0) + Consume (P1) rule seeds.
--
-- Adds the evolvable rules that govern the new bounded-operator behavior:
--   P0.1 per-action timeouts, P0.2 pulse budget, P0.4 granular kill-switch,
--   P0.5 self-retention windows.
--
-- Every rule is seeded ON CONFLICT DO NOTHING so re-running is idempotent and
-- never overwrites an operator-tuned value. RulesEngine.get_threshold() reads
-- config->>'value'. category must satisfy the olympus_rules CHECK
-- (threshold|schedule|policy|skill). source='safety_envelope' tags for audit.

INSERT INTO olympus_rules (rule_name, category, config, source)
VALUES
    ('action_statement_timeout_s', 'threshold', '{"value": 300}'::jsonb, 'safety_envelope'),
    ('action_lock_timeout_s',      'threshold', '{"value": 5}'::jsonb,   'safety_envelope'),
    ('max_actions_per_pulse',      'threshold', '{"value": 50}'::jsonb,  'safety_envelope'),
    ('max_pulse_runtime_s',        'threshold', '{"value": 600}'::jsonb, 'safety_envelope'),
    ('olympus_enabled',            'policy',    '{"value": true}'::jsonb, 'safety_envelope'),
    ('olympus_pulse_enabled',      'policy',    '{"value": true}'::jsonb, 'safety_envelope'),
    ('olympus_heartbeat_enabled',  'policy',    '{"value": true}'::jsonb, 'safety_envelope'),
    ('olympus_hb_retention_months',     'policy', '{"value": 6}'::jsonb,  'safety_envelope'),
    ('olympus_actions_retention_days',  'policy', '{"value": 90}'::jsonb, 'safety_envelope'),
    ('olympus_insights_retention_days', 'policy', '{"value": 90}'::jsonb, 'safety_envelope')
ON CONFLICT (rule_name) DO NOTHING;

-- === ROLLBACK ===
DELETE FROM olympus_rules
WHERE source = 'safety_envelope'
  AND rule_name IN (
    'action_statement_timeout_s','action_lock_timeout_s','max_actions_per_pulse',
    'max_pulse_runtime_s','olympus_enabled','olympus_pulse_enabled',
    'olympus_heartbeat_enabled','olympus_hb_retention_months',
    'olympus_actions_retention_days','olympus_insights_retention_days'
  );
