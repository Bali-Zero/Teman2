PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__legacy_research_results` AS
SELECT `result_id`, `job_id`, `result_json`, `result_hash`, `created_at`
FROM `research_results`;--> statement-breakpoint
DROP TABLE `research_results`;--> statement-breakpoint
CREATE TABLE `__new_research_jobs` (
	`job_id` text PRIMARY KEY NOT NULL,
	`actor_key` text NOT NULL,
	`mode` text NOT NULL,
	`query_json` text NOT NULL,
	`request_hash` text NOT NULL,
	`idempotency_key` text NOT NULL,
	`status` text NOT NULL,
	`attempt_limit` integer DEFAULT 3 NOT NULL,
	`attempt_count` integer DEFAULT 0 NOT NULL,
	`worker_id` text,
	`claim_token` text,
	`fencing_token` integer DEFAULT 0 NOT NULL,
	`heartbeat_at` text,
	`lease_deadline` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`expires_at` text NOT NULL,
	`completed_at` text,
	`cancelled_at` text,
	CONSTRAINT "research_jobs_actor_key_check" CHECK(length("actor_key") = 64 and "actor_key" not glob '*[^0-9a-f]*'),
	CONSTRAINT "research_jobs_request_hash_check" CHECK(length("request_hash") = 64 and "request_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "research_jobs_mode_check" CHECK("mode" in ('search', 'compare', 'timeline', 'notebook_insight')),
	CONSTRAINT "research_jobs_status_check" CHECK("status" in ('queued', 'claimed', 'completed', 'failed', 'cancelled')),
	CONSTRAINT "research_jobs_attempts_check" CHECK("attempt_limit" between 1 and 5 and "attempt_count" between 0 and "attempt_limit"),
	CONSTRAINT "research_jobs_fencing_check" CHECK("fencing_token" >= 0)
);--> statement-breakpoint
INSERT INTO `__new_research_jobs`(
	`job_id`, `actor_key`, `mode`, `query_json`, `request_hash`,
	`idempotency_key`, `status`, `attempt_limit`, `attempt_count`,
	`fencing_token`, `created_at`, `expires_at`, `cancelled_at`
)
SELECT old.`job_id`,
	CASE
		WHEN length(old.`actor_key`) = 64 AND old.`actor_key` NOT GLOB '*[^0-9a-f]*'
			THEN old.`actor_key`
		ELSE printf('%064d', 0)
	END,
	'search',
	'{"schema_version":"research-request.v1","mode":"search","topic_ids":["topic:legacy-archived"],"entity_ids":[],"index_tokens":[],"template":null,"facets":{"domains":[],"source_system_ids":["intel-lake"],"evidence_types":[],"confidence":[],"lifecycle_states":[],"languages":[]}}',
	printf('%064d', 0), 'legacy:' || old.`job_id`,
	'cancelled', 3, 0, 0, old.`created_at`, old.`expires_at`, old.`created_at`
FROM `research_jobs` old;--> statement-breakpoint
DROP TABLE `research_jobs`;--> statement-breakpoint
ALTER TABLE `__new_research_jobs` RENAME TO `research_jobs`;--> statement-breakpoint
CREATE UNIQUE INDEX `research_jobs_idempotency_key_unique` ON `research_jobs` (`idempotency_key`);--> statement-breakpoint
CREATE INDEX `research_jobs_claim_queue_idx` ON `research_jobs` (`status`,`expires_at`,`created_at`);--> statement-breakpoint
CREATE TABLE `research_results` (
	`result_id` text PRIMARY KEY NOT NULL,
	`job_id` text NOT NULL,
	`status` text NOT NULL,
	`result_json` text NOT NULL,
	`result_hash` text NOT NULL,
	`request_hash` text NOT NULL,
	`fencing_token` integer NOT NULL,
	`receipt_key_id` text NOT NULL,
	`receipt_body_hash` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`job_id`) REFERENCES `research_jobs`(`job_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "research_results_hash_check" CHECK(length("result_hash") = 64 and "result_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "research_results_request_hash_check" CHECK(length("request_hash") = 64 and "request_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "research_results_receipt_hash_check" CHECK(length("receipt_body_hash") = 64 and "receipt_body_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "research_results_status_check" CHECK("status" in ('completed', 'failed')),
	CONSTRAINT "research_results_fencing_check" CHECK("fencing_token" > 0)
);--> statement-breakpoint
DROP TABLE `__legacy_research_results`;--> statement-breakpoint
CREATE UNIQUE INDEX `research_results_job_id_unique` ON `research_results` (`job_id`);--> statement-breakpoint
CREATE TABLE `research_audit_events` (
	`event_id` text PRIMARY KEY NOT NULL,
	`job_id` text NOT NULL,
	`event_type` text NOT NULL,
	`actor_key` text,
	`worker_id` text,
	`status` text NOT NULL,
	`failure_code` text,
	`fencing_token` integer,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`job_id`) REFERENCES `research_jobs`(`job_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "research_audit_event_type_check" CHECK("event_type" in ('created', 'cancelled', 'claimed', 'completed', 'failed')),
	CONSTRAINT "research_audit_status_check" CHECK("status" in ('queued', 'claimed', 'completed', 'failed', 'cancelled')),
	CONSTRAINT "research_audit_failure_code_check" CHECK("failure_code" is null or "failure_code" in ('source_unavailable', 'dlp_rejected', 'evidence_missing', 'invalid_result', 'internal_error'))
);--> statement-breakpoint
CREATE INDEX `research_audit_job_idx` ON `research_audit_events` (`job_id`,`created_at`);--> statement-breakpoint
INSERT INTO `research_audit_events`(
	`event_id`, `job_id`, `event_type`, `actor_key`, `status`, `created_at`
)
SELECT `job_id` || ':created', `job_id`, 'created', `actor_key`, 'queued', `created_at`
FROM `research_jobs`;--> statement-breakpoint
INSERT INTO `research_audit_events`(
	`event_id`, `job_id`, `event_type`, `actor_key`, `status`, `created_at`
)
SELECT `job_id` || ':cancelled', `job_id`, 'cancelled', `actor_key`,
	'cancelled', COALESCE(`cancelled_at`, `created_at`)
FROM `research_jobs` WHERE `status` = 'cancelled';--> statement-breakpoint
PRAGMA foreign_keys=ON;
