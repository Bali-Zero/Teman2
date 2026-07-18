CREATE TABLE `asset_status_events` (
	`asset_id` text NOT NULL,
	`status_seq` integer NOT NULL,
	`status` text NOT NULL,
	`rights_status` text NOT NULL,
	`reason_code` text NOT NULL,
	`replacement_asset_id` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY(`asset_id`, `status_seq`),
	FOREIGN KEY (`asset_id`) REFERENCES `assets`(`asset_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "asset_status_events_status_check" CHECK("asset_status_events"."status" in ('pending', 'verified', 'quarantined', 'revoked')),
	CONSTRAINT "asset_status_events_rights_status_check" CHECK("asset_status_events"."rights_status" in ('approved', 'denied', 'unknown'))
);
--> statement-breakpoint
CREATE TABLE `assets` (
	`asset_id` text PRIMARY KEY NOT NULL,
	`packet_id` text NOT NULL,
	`sha256` text NOT NULL,
	`r2_key` text NOT NULL,
	`mime_type` text NOT NULL,
	`byte_count` integer NOT NULL,
	`width` integer NOT NULL,
	`height` integer NOT NULL,
	`alt_text` text NOT NULL,
	`source` text NOT NULL,
	`rights_status` text NOT NULL,
	`status` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "assets_hash_check" CHECK(length("sha256") = 64 and "sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "assets_status_check" CHECK("assets"."status" in ('pending', 'verified', 'quarantined', 'revoked')),
	CONSTRAINT "assets_rights_status_check" CHECK("assets"."rights_status" in ('approved', 'denied', 'unknown')),
	CONSTRAINT "assets_dimensions_check" CHECK("assets"."width" > 0 and "assets"."height" > 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `assets_sha256_unique` ON `assets` (`sha256`);--> statement-breakpoint
CREATE UNIQUE INDEX `assets_r2_key_unique` ON `assets` (`r2_key`);--> statement-breakpoint
CREATE TABLE `audit_anchor_receipts` (
	`anchor_id` text PRIMARY KEY NOT NULL,
	`stream_id` text NOT NULL,
	`stream_seq` integer NOT NULL,
	`event_hash` text NOT NULL,
	`previous_anchor_hash` text NOT NULL,
	`observed_at` text NOT NULL,
	`key_id` text NOT NULL,
	`signature` text NOT NULL,
	`anchor_hash` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "audit_anchor_event_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_anchor_previous_hash_check" CHECK(length("previous_anchor_hash") = 64 and "previous_anchor_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_anchor_hash_check" CHECK(length("anchor_hash") = 64 and "anchor_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
CREATE UNIQUE INDEX `audit_anchor_receipts_anchor_hash_unique` ON `audit_anchor_receipts` (`anchor_hash`);--> statement-breakpoint
CREATE UNIQUE INDEX `audit_anchor_stream_seq_unique` ON `audit_anchor_receipts` (`stream_id`,`stream_seq`);--> statement-breakpoint
CREATE TABLE `audit_events` (
	`event_id` text PRIMARY KEY NOT NULL,
	`stream_id` text NOT NULL,
	`stream_seq` integer NOT NULL,
	`payload_json` text NOT NULL,
	`previous_event_hash` text NOT NULL,
	`event_hash` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "audit_events_seq_check" CHECK("audit_events"."stream_seq" > 0),
	CONSTRAINT "audit_events_previous_hash_check" CHECK(length("previous_event_hash") = 64 and "previous_event_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_events_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
CREATE UNIQUE INDEX `audit_events_stream_seq_unique` ON `audit_events` (`stream_id`,`stream_seq`);--> statement-breakpoint
CREATE TABLE `audit_stream_heads` (
	`stream_id` text PRIMARY KEY NOT NULL,
	`stream_seq` integer NOT NULL,
	`event_hash` text NOT NULL,
	CONSTRAINT "audit_stream_heads_seq_check" CHECK("audit_stream_heads"."stream_seq" > 0),
	CONSTRAINT "audit_stream_heads_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
CREATE TABLE `breaking_entries` (
	`breaking_revision` integer NOT NULL,
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`packet_id` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	PRIMARY KEY(`breaking_revision`, `story_id`),
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`story_id`,`version`) REFERENCES `story_versions`(`story_id`,`version`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "breaking_entries_state_check" CHECK("breaking_entries"."publication_state" in ('building', 'published', 'failed'))
);
--> statement-breakpoint
CREATE TABLE `breaking_pointer` (
	`singleton_id` integer PRIMARY KEY DEFAULT 1 NOT NULL,
	`active_revision` integer DEFAULT 0 NOT NULL,
	`updated_at` text,
	CONSTRAINT "breaking_pointer_singleton_check" CHECK("breaking_pointer"."singleton_id" = 1),
	CONSTRAINT "breaking_pointer_revision_check" CHECK("breaking_pointer"."active_revision" >= 0)
);
--> statement-breakpoint
CREATE TABLE `collector_runs` (
	`run_id` text PRIMARY KEY NOT NULL,
	`system_id` text NOT NULL,
	`collector_id` text NOT NULL,
	`started_at` text NOT NULL,
	`completed_at` text NOT NULL,
	`status` text NOT NULL,
	`freshness` text NOT NULL,
	`items_seen` integer NOT NULL,
	`items_eligible` integer NOT NULL,
	`source_count` integer NOT NULL,
	`unreachable_source_count` integer NOT NULL,
	`watermark` text NOT NULL,
	`verified_at` text NOT NULL,
	FOREIGN KEY (`system_id`) REFERENCES `source_systems`(`system_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "collector_runs_status_check" CHECK("collector_runs"."status" in ('healthy', 'delayed', 'degraded', 'unavailable', 'unknown')),
	CONSTRAINT "collector_runs_freshness_check" CHECK("collector_runs"."freshness" in ('fresh', 'delayed', 'archived')),
	CONSTRAINT "collector_runs_counts_check" CHECK("collector_runs"."items_seen" >= 0 and "collector_runs"."items_eligible" >= 0 and "collector_runs"."source_count" >= 0 and "collector_runs"."unreachable_source_count" >= 0)
);
--> statement-breakpoint
CREATE TABLE `edition_entries` (
	`edition_id` text NOT NULL,
	`packet_id` text NOT NULL,
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`section` text NOT NULL,
	`editorial_order` integer NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	PRIMARY KEY(`edition_id`, `packet_id`, `story_id`),
	FOREIGN KEY (`edition_id`) REFERENCES `editions`(`edition_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`edition_id`,`packet_id`) REFERENCES `editions`(`edition_id`,`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`,`story_id`,`version`) REFERENCES `story_versions`(`packet_id`,`story_id`,`version`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "edition_entries_state_check" CHECK("edition_entries"."publication_state" in ('building', 'published', 'failed'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `edition_entries_order_unique` ON `edition_entries` (`edition_id`,`section`,`editorial_order`);--> statement-breakpoint
CREATE TABLE `edition_pointer` (
	`singleton_id` integer PRIMARY KEY DEFAULT 1 NOT NULL,
	`current_edition_id` text,
	`current_revision` integer DEFAULT 0 NOT NULL,
	CONSTRAINT "edition_pointer_singleton_check" CHECK("edition_pointer"."singleton_id" = 1),
	CONSTRAINT "edition_pointer_revision_check" CHECK("edition_pointer"."current_revision" >= 0)
);
--> statement-breakpoint
CREATE TABLE `editions` (
	`edition_id` text PRIMARY KEY NOT NULL,
	`packet_id` text NOT NULL,
	`editor_version` text NOT NULL,
	`ruleset_version` text NOT NULL,
	`edition_date` text NOT NULL,
	`edition_revision` integer NOT NULL,
	`expected_current_revision` integer NOT NULL,
	`expected_breaking_revision` integer NOT NULL,
	`edition_kind` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	`coverage_state` text NOT NULL,
	`readiness_cutoff` text NOT NULL,
	`verified_at` text NOT NULL,
	`collector_run_ids_json` text NOT NULL,
	`placements_json` text NOT NULL,
	`breaking_story_ids_json` text NOT NULL,
	`asset_digests_json` text NOT NULL,
	`coverage_gaps_json` text NOT NULL,
	`reader_notices_json` text NOT NULL,
	`published_at` text,
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "editions_revision_check" CHECK("editions"."edition_revision" > 0),
	CONSTRAINT "editions_state_check" CHECK("editions"."publication_state" in ('building', 'published', 'superseded', 'failed')),
	CONSTRAINT "editions_kind_check" CHECK("editions"."edition_kind" in ('standard', 'quiet')),
	CONSTRAINT "editions_coverage_check" CHECK("editions"."coverage_state" in ('complete', 'partial'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `editions_packet_id_unique` ON `editions` (`packet_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `editions_date_revision_unique` ON `editions` (`edition_date`,`edition_revision`);--> statement-breakpoint
CREATE UNIQUE INDEX `editions_id_packet_unique` ON `editions` (`edition_id`,`packet_id`);--> statement-breakpoint
CREATE TABLE `evidence_refs` (
	`evidence_id` text PRIMARY KEY NOT NULL,
	`root_source_id` text NOT NULL,
	`canonical_url` text,
	`publisher` text NOT NULL,
	`document_citation` text,
	`published_at` text,
	`retrieved_at` text NOT NULL,
	`source_type` text NOT NULL,
	`primary_document_status` text NOT NULL,
	`root_resolution_status` text NOT NULL,
	`independence_verdict` text NOT NULL,
	`evidence_note` text,
	`upstream_root_source_ids_json` text NOT NULL,
	`syndication_group_fingerprint` text NOT NULL,
	`independence_ruleset_version` text NOT NULL,
	`independence_reason` text NOT NULL,
	`counts_toward_breaking` integer NOT NULL,
	CONSTRAINT "evidence_refs_source_type_check" CHECK("evidence_refs"."source_type" in ('official', 'journalism', 'research', 'dataset'))
);
--> statement-breakpoint
CREATE TABLE `ingest_nonces` (
	`key_id` text NOT NULL,
	`nonce` text NOT NULL,
	`body_hash` text NOT NULL,
	`expires_at` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY(`key_id`, `nonce`)
);
--> statement-breakpoint
CREATE TABLE `ops_intents` (
	`intent_id` text PRIMARY KEY NOT NULL,
	`idempotency_key` text NOT NULL,
	`intent_type` text NOT NULL,
	`payload_json` text NOT NULL,
	`payload_hash` text NOT NULL,
	`actor_key` text NOT NULL,
	`policy_version` text NOT NULL,
	`status` text NOT NULL,
	`attempt_limit` integer NOT NULL,
	`expires_at` text NOT NULL,
	`claim_token` text,
	`fencing_token` integer DEFAULT 0 NOT NULL,
	`heartbeat_at` text,
	`lease_deadline` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `ops_intents_idempotency_key_unique` ON `ops_intents` (`idempotency_key`);--> statement-breakpoint
CREATE TABLE `ops_receipts` (
	`receipt_id` text PRIMARY KEY NOT NULL,
	`intent_id` text NOT NULL,
	`status` text NOT NULL,
	`payload_json` text NOT NULL,
	`payload_hash` text NOT NULL,
	`fencing_token` integer NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`intent_id`) REFERENCES `ops_intents`(`intent_id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `publication_packets` (
	`packet_id` text PRIMARY KEY NOT NULL,
	`manifest_hash` text NOT NULL,
	`packet_kind` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	`expected_story_version_count` integer NOT NULL,
	`expected_claim_count` integer NOT NULL,
	`expected_evidence_link_count` integer NOT NULL,
	`expected_edition_entry_count` integer NOT NULL,
	`expected_breaking_entry_count` integer NOT NULL,
	`expected_asset_reference_count` integer NOT NULL,
	`referenced_claim_ids_json` text NOT NULL,
	`referenced_evidence_ids_json` text NOT NULL,
	`referenced_asset_digests_json` text NOT NULL,
	`breaking_entries_json` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`published_at` text,
	CONSTRAINT "publication_packets_hash_check" CHECK(length("manifest_hash") = 64 and "manifest_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "publication_packets_kind_check" CHECK("publication_packets"."packet_kind" in ('edition', 'breaking')),
	CONSTRAINT "publication_packets_state_check" CHECK("publication_packets"."publication_state" in ('building', 'published', 'failed')),
	CONSTRAINT "publication_packets_expected_counts_check" CHECK("publication_packets"."expected_story_version_count" >= 0 and "publication_packets"."expected_claim_count" >= 0 and "publication_packets"."expected_evidence_link_count" >= 0 and "publication_packets"."expected_edition_entry_count" >= 0 and "publication_packets"."expected_breaking_entry_count" >= 0 and "publication_packets"."expected_asset_reference_count" >= 0)
);
--> statement-breakpoint
CREATE TABLE `release_attestations` (
	`attestation_id` text PRIMARY KEY NOT NULL,
	`story_id` text NOT NULL,
	`story_version` integer NOT NULL,
	`evidence_bundle_hash` text NOT NULL,
	`asset_set_hash` text NOT NULL,
	`key_id` text NOT NULL,
	`signature` text NOT NULL,
	`expires_at` text NOT NULL,
	`consumed_at` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL
);
--> statement-breakpoint
CREATE TABLE `research_jobs` (
	`job_id` text PRIMARY KEY NOT NULL,
	`actor_key` text NOT NULL,
	`mode` text NOT NULL,
	`query_json` text NOT NULL,
	`status` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`expires_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `research_results` (
	`result_id` text PRIMARY KEY NOT NULL,
	`job_id` text NOT NULL,
	`result_json` text NOT NULL,
	`result_hash` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`job_id`) REFERENCES `research_jobs`(`job_id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `source_systems` (
	`system_id` text PRIMARY KEY NOT NULL,
	`display_name` text NOT NULL,
	`expected_cadence_seconds` integer NOT NULL,
	`readiness` text NOT NULL,
	`health` text NOT NULL,
	`updated_at` text NOT NULL,
	CONSTRAINT "source_systems_readiness_check" CHECK("source_systems"."readiness" in ('required', 'optional')),
	CONSTRAINT "source_systems_health_check" CHECK("source_systems"."health" in ('healthy', 'delayed', 'degraded', 'unavailable', 'unknown')),
	CONSTRAINT "source_systems_cadence_check" CHECK("source_systems"."expected_cadence_seconds" > 0)
);
--> statement-breakpoint
CREATE TABLE `stories` (
	`story_id` text PRIMARY KEY NOT NULL,
	`slug` text NOT NULL,
	`current_version` integer DEFAULT 0 NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "stories_current_version_check" CHECK("stories"."current_version" >= 0)
);
--> statement-breakpoint
CREATE UNIQUE INDEX `stories_slug_unique` ON `stories` (`slug`);--> statement-breakpoint
CREATE TABLE `story_asset_references` (
	`packet_id` text NOT NULL,
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`asset_sha256` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	PRIMARY KEY(`packet_id`, `story_id`, `version`, `asset_sha256`),
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`asset_sha256`) REFERENCES `assets`(`sha256`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`,`story_id`,`version`) REFERENCES `story_versions`(`packet_id`,`story_id`,`version`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "story_asset_references_hash_check" CHECK(length("asset_sha256") = 64 and "asset_sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "story_asset_references_state_check" CHECK("story_asset_references"."publication_state" in ('building', 'published', 'failed'))
);
--> statement-breakpoint
CREATE TABLE `story_claims` (
	`claim_id` text NOT NULL,
	`packet_id` text NOT NULL,
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`claim_kind` text NOT NULL,
	`normalized_text` text NOT NULL,
	`numeric_value` text,
	`numeric_unit` text,
	`as_of` text,
	`breaking_gate` text,
	`evidence_ids_json` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	PRIMARY KEY(`packet_id`, `story_id`, `version`, `claim_id`),
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`,`story_id`,`version`) REFERENCES `story_versions`(`packet_id`,`story_id`,`version`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "story_claims_kind_check" CHECK("story_claims"."claim_kind" in ('fact', 'numeric', 'analysis')),
	CONSTRAINT "story_claims_state_check" CHECK("story_claims"."publication_state" in ('building', 'published', 'failed'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `story_claims_story_version_claim_unique` ON `story_claims` (`story_id`,`version`,`claim_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `story_claims_packet_claim_unique` ON `story_claims` (`packet_id`,`claim_id`);--> statement-breakpoint
CREATE TABLE `story_evidence` (
	`packet_id` text NOT NULL,
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`claim_id` text NOT NULL,
	`evidence_id` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	PRIMARY KEY(`packet_id`, `story_id`, `version`, `claim_id`, `evidence_id`),
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`evidence_id`) REFERENCES `evidence_refs`(`evidence_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`,`story_id`,`version`,`claim_id`) REFERENCES `story_claims`(`packet_id`,`story_id`,`version`,`claim_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "story_evidence_state_check" CHECK("story_evidence"."publication_state" in ('building', 'published', 'failed'))
);
--> statement-breakpoint
CREATE TABLE `story_versions` (
	`story_id` text NOT NULL,
	`version` integer NOT NULL,
	`packet_id` text NOT NULL,
	`expected_current_version` integer NOT NULL,
	`language` text NOT NULL,
	`domain` text NOT NULL,
	`severity` text NOT NULL,
	`lifecycle_state` text NOT NULL,
	`first_seen_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`title` text NOT NULL,
	`deck` text NOT NULL,
	`summary` text NOT NULL,
	`why_it_matters` text NOT NULL,
	`curiosity_text` text,
	`score_components_json` text NOT NULL,
	`claim_ids_json` text NOT NULL,
	`contributing_system_ids_json` text NOT NULL,
	`coverage_state` text NOT NULL,
	`confidence` text NOT NULL,
	`asset_digests_json` text NOT NULL,
	`adapter_version` text NOT NULL,
	`ruleset_version` text NOT NULL,
	`publication_state` text DEFAULT 'building' NOT NULL,
	`published_at` text,
	PRIMARY KEY(`story_id`, `version`),
	FOREIGN KEY (`story_id`) REFERENCES `stories`(`story_id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`packet_id`) REFERENCES `publication_packets`(`packet_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "story_versions_version_check" CHECK("story_versions"."version" > 0),
	CONSTRAINT "story_versions_expected_version_check" CHECK("story_versions"."expected_current_version" >= 0 and "story_versions"."version" = "story_versions"."expected_current_version" + 1),
	CONSTRAINT "story_versions_state_check" CHECK("story_versions"."publication_state" in ('building', 'published', 'superseded', 'failed'))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `story_versions_story_version_unique` ON `story_versions` (`story_id`,`version`);--> statement-breakpoint
CREATE UNIQUE INDEX `story_versions_packet_story_version_unique` ON `story_versions` (`packet_id`,`story_id`,`version`);--> statement-breakpoint
CREATE TABLE `story_visibility_events` (
	`story_id` text NOT NULL,
	`visibility_seq` integer NOT NULL,
	`story_version` integer NOT NULL,
	`intent_id` text NOT NULL,
	`desired_quarantined` integer NOT NULL,
	`audit_event_id` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY(`story_id`, `visibility_seq`),
	FOREIGN KEY (`audit_event_id`) REFERENCES `audit_events`(`event_id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `story_visibility_events_intent_id_unique` ON `story_visibility_events` (`intent_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `story_visibility_story_seq_unique` ON `story_visibility_events` (`story_id`,`visibility_seq`);--> statement-breakpoint
INSERT INTO edition_pointer (singleton_id, current_edition_id, current_revision)
VALUES (1, NULL, 0);--> statement-breakpoint
INSERT INTO breaking_pointer (singleton_id, active_revision, updated_at)
VALUES (1, 0, NULL);
