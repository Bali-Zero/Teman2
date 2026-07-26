PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__asset_sources_backup` AS
SELECT `asset_id`, `packet_id`, `sha256` AS `canonical_sha256`,
       `source_sha256`, `source_byte_count`, `source_mime_type`,
       `source_width`, `source_height`, `alt_text`, `source`, `source_url`,
       `rights_basis`, `rights_status`, `usage_status`, `dlp_status`,
       `sanitization_status`, `perceptual_dedup_status`, `status`,
       `captured_at`, `created_at`
FROM `assets`;--> statement-breakpoint
CREATE TABLE `__new_assets` (
	`sha256` text PRIMARY KEY NOT NULL,
	`r2_key` text NOT NULL,
	`mime_type` text NOT NULL,
	`byte_count` integer NOT NULL,
	`width` integer NOT NULL,
	`height` integer NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	CONSTRAINT "assets_hash_check" CHECK(length("sha256") = 64 and "sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "assets_mime_check" CHECK("__new_assets"."mime_type" = 'image/png'),
	CONSTRAINT "assets_dimensions_check" CHECK("__new_assets"."byte_count" > 0 and "__new_assets"."width" > 0 and "__new_assets"."height" > 0)
);--> statement-breakpoint
INSERT INTO `__new_assets`("sha256", "r2_key", "mime_type", "byte_count", "width", "height", "created_at")
SELECT "sha256", "r2_key", "mime_type", "byte_count", "width", "height", "created_at" FROM `assets`;--> statement-breakpoint
DROP TABLE `assets`;--> statement-breakpoint
ALTER TABLE `__new_assets` RENAME TO `assets`;--> statement-breakpoint
CREATE UNIQUE INDEX `assets_r2_key_unique` ON `assets` (`r2_key`);--> statement-breakpoint
CREATE TABLE `asset_sources` (
	`asset_id` text PRIMARY KEY NOT NULL,
	`packet_id` text NOT NULL,
	`canonical_sha256` text NOT NULL,
	`source_sha256` text NOT NULL,
	`source_byte_count` integer NOT NULL,
	`source_mime_type` text NOT NULL,
	`source_width` integer NOT NULL,
	`source_height` integer NOT NULL,
	`alt_text` text NOT NULL,
	`source` text NOT NULL,
	`source_url` text,
	`rights_basis` text DEFAULT 'unknown' NOT NULL,
	`rights_status` text NOT NULL,
	`usage_status` text DEFAULT 'unknown' NOT NULL,
	`dlp_status` text DEFAULT 'pending' NOT NULL,
	`sanitization_status` text DEFAULT 'pending' NOT NULL,
	`perceptual_dedup_status` text DEFAULT 'unreviewed' NOT NULL,
	`status` text NOT NULL,
	`captured_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	FOREIGN KEY (`canonical_sha256`) REFERENCES `assets`(`sha256`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "asset_sources_source_hash_check" CHECK(length("source_sha256") = 64 and "source_sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "asset_sources_source_mime_check" CHECK("asset_sources"."source_mime_type" in ('image/jpeg', 'image/png', 'image/webp')),
	CONSTRAINT "asset_sources_status_check" CHECK("asset_sources"."status" in ('pending', 'verified', 'quarantined', 'revoked')),
	CONSTRAINT "asset_sources_rights_status_check" CHECK("asset_sources"."rights_status" in ('approved', 'denied', 'unknown')),
	CONSTRAINT "asset_sources_rights_basis_check" CHECK("asset_sources"."rights_basis" in ('internal-owned', 'licensed', 'public-domain', 'official-use', 'generated', 'unknown')),
	CONSTRAINT "asset_sources_usage_status_check" CHECK("asset_sources"."usage_status" in ('approved', 'denied', 'unknown')),
	CONSTRAINT "asset_sources_dlp_status_check" CHECK("asset_sources"."dlp_status" in ('pending', 'passed', 'failed')),
	CONSTRAINT "asset_sources_sanitization_status_check" CHECK("asset_sources"."sanitization_status" in ('pending', 'passed', 'failed')),
	CONSTRAINT "asset_sources_perceptual_dedup_status_check" CHECK("asset_sources"."perceptual_dedup_status" in ('unreviewed', 'unique', 'intentional-reuse')),
	CONSTRAINT "asset_sources_source_dimensions_check" CHECK("asset_sources"."source_byte_count" > 0 and "asset_sources"."source_width" > 0 and "asset_sources"."source_height" > 0)
);--> statement-breakpoint
INSERT INTO `asset_sources` SELECT * FROM `__asset_sources_backup`;--> statement-breakpoint
DROP TABLE `__asset_sources_backup`;--> statement-breakpoint
CREATE INDEX `asset_sources_canonical_sha256_idx` ON `asset_sources` (`canonical_sha256`);--> statement-breakpoint
CREATE UNIQUE INDEX `asset_sources_source_sha256_unique` ON `asset_sources` (`source_sha256`);--> statement-breakpoint
CREATE TABLE `__new_asset_status_events` (
	`asset_id` text NOT NULL,
	`status_seq` integer NOT NULL,
	`status` text NOT NULL,
	`rights_status` text NOT NULL,
	`reason_code` text NOT NULL,
	`replacement_asset_id` text,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY(`asset_id`, `status_seq`),
	FOREIGN KEY (`asset_id`) REFERENCES `asset_sources`(`asset_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "asset_status_events_status_check" CHECK("__new_asset_status_events"."status" in ('pending', 'verified', 'quarantined', 'revoked')),
	CONSTRAINT "asset_status_events_rights_status_check" CHECK("__new_asset_status_events"."rights_status" in ('approved', 'denied', 'unknown'))
);--> statement-breakpoint
INSERT INTO `__new_asset_status_events` SELECT * FROM `asset_status_events`;--> statement-breakpoint
DROP TABLE `asset_status_events`;--> statement-breakpoint
ALTER TABLE `__new_asset_status_events` RENAME TO `asset_status_events`;--> statement-breakpoint
PRAGMA foreign_keys=ON;
