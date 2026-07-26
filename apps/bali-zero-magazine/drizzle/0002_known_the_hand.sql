PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_assets` (
	`asset_id` text PRIMARY KEY NOT NULL,
	`packet_id` text NOT NULL,
	`sha256` text NOT NULL,
	`source_sha256` text NOT NULL,
	`source_byte_count` integer NOT NULL,
	`source_mime_type` text NOT NULL,
	`source_width` integer NOT NULL,
	`source_height` integer NOT NULL,
	`r2_key` text NOT NULL,
	`mime_type` text NOT NULL,
	`byte_count` integer NOT NULL,
	`width` integer NOT NULL,
	`height` integer NOT NULL,
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
	CONSTRAINT "assets_hash_check" CHECK(length("sha256") = 64 and "sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "assets_source_hash_check" CHECK(length("source_sha256") = 64 and "source_sha256" not glob '*[^0-9a-f]*'),
	CONSTRAINT "assets_source_mime_check" CHECK("__new_assets"."source_mime_type" in ('image/jpeg', 'image/png', 'image/webp')),
	CONSTRAINT "assets_status_check" CHECK("__new_assets"."status" in ('pending', 'verified', 'quarantined', 'revoked')),
	CONSTRAINT "assets_rights_status_check" CHECK("__new_assets"."rights_status" in ('approved', 'denied', 'unknown')),
	CONSTRAINT "assets_rights_basis_check" CHECK("__new_assets"."rights_basis" in ('internal-owned', 'licensed', 'public-domain', 'official-use', 'generated', 'unknown')),
	CONSTRAINT "assets_usage_status_check" CHECK("__new_assets"."usage_status" in ('approved', 'denied', 'unknown')),
	CONSTRAINT "assets_dlp_status_check" CHECK("__new_assets"."dlp_status" in ('pending', 'passed', 'failed')),
	CONSTRAINT "assets_sanitization_status_check" CHECK("__new_assets"."sanitization_status" in ('pending', 'passed', 'failed')),
	CONSTRAINT "assets_perceptual_dedup_status_check" CHECK("__new_assets"."perceptual_dedup_status" in ('unreviewed', 'unique', 'intentional-reuse')),
	CONSTRAINT "assets_dimensions_check" CHECK("__new_assets"."width" > 0 and "__new_assets"."height" > 0),
	CONSTRAINT "assets_source_dimensions_check" CHECK("__new_assets"."source_byte_count" > 0 and "__new_assets"."source_width" > 0 and "__new_assets"."source_height" > 0)
);
--> statement-breakpoint
INSERT INTO `__new_assets`("asset_id", "packet_id", "sha256", "source_sha256", "source_byte_count", "source_mime_type", "source_width", "source_height", "r2_key", "mime_type", "byte_count", "width", "height", "alt_text", "source", "source_url", "rights_basis", "rights_status", "usage_status", "dlp_status", "sanitization_status", "perceptual_dedup_status", "status", "captured_at", "created_at") SELECT "asset_id", "packet_id", "sha256", "sha256", "byte_count", "mime_type", "width", "height", "r2_key", "mime_type", "byte_count", "width", "height", "alt_text", "source", "source_url", "rights_basis", "rights_status", "usage_status", "dlp_status", "sanitization_status", "perceptual_dedup_status", "status", "captured_at", "created_at" FROM `assets`;--> statement-breakpoint
DROP TABLE `assets`;--> statement-breakpoint
ALTER TABLE `__new_assets` RENAME TO `assets`;--> statement-breakpoint
PRAGMA foreign_keys=ON;--> statement-breakpoint
CREATE UNIQUE INDEX `assets_sha256_unique` ON `assets` (`sha256`);--> statement-breakpoint
CREATE UNIQUE INDEX `assets_r2_key_unique` ON `assets` (`r2_key`);
