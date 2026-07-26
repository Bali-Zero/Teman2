CREATE TABLE ops_transition_guards (
  guard_id text PRIMARY KEY NOT NULL,
  intent_id text NOT NULL REFERENCES ops_intents(intent_id),
  transition_kind text NOT NULL,
  fencing_token integer NOT NULL CHECK (fencing_token >= 0),
  transition_ok integer NOT NULL CHECK (transition_ok = 1),
  created_at text NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(intent_id, transition_kind, fencing_token)
);
--> statement-breakpoint
CREATE UNIQUE INDEX ops_audit_transition_unique
  ON ops_audit_events(intent_id, event_type, fencing_token);
