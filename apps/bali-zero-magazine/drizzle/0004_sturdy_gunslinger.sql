CREATE TABLE `audit_anchor_heads` (
	`stream_id` text PRIMARY KEY NOT NULL,
	`stream_seq` integer NOT NULL,
	`event_hash` text NOT NULL,
	`anchor_hash` text NOT NULL,
	`updated_at` text NOT NULL,
	CONSTRAINT "audit_anchor_heads_seq_check" CHECK("audit_anchor_heads"."stream_seq" > 0),
	CONSTRAINT "audit_anchor_heads_event_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_anchor_heads_anchor_hash_check" CHECK(length("anchor_hash") = 64 and "anchor_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
CREATE TABLE `audit_promotion_block` (
	`singleton_id` integer PRIMARY KEY NOT NULL,
	`blocked` integer NOT NULL,
	`reason` text NOT NULL,
	`updated_at` text NOT NULL,
	CONSTRAINT "audit_promotion_block_singleton_check" CHECK("audit_promotion_block"."singleton_id" = 1),
	CONSTRAINT "audit_promotion_block_value_check" CHECK("audit_promotion_block"."blocked" in (0, 1))
);
--> statement-breakpoint
CREATE TABLE `audit_promotion_permits` (
	`operation` text NOT NULL,
	`packet_id` text NOT NULL,
	`stream_id` text NOT NULL,
	`stream_seq` integer NOT NULL,
	`event_hash` text NOT NULL,
	`anchor_hash` text NOT NULL,
	`status` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	`consumed_at` text,
	PRIMARY KEY(`operation`, `packet_id`),
	CONSTRAINT "audit_promotion_permit_operation_check" CHECK("audit_promotion_permits"."operation" in ('edition.publish', 'breaking.publish')),
	CONSTRAINT "audit_promotion_permit_seq_check" CHECK("audit_promotion_permits"."stream_seq" > 0),
	CONSTRAINT "audit_promotion_permit_event_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_promotion_permit_anchor_hash_check" CHECK(length("anchor_hash") = 64 and "anchor_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_promotion_permit_status_check" CHECK("audit_promotion_permits"."status" in ('permitted', 'consumed'))
);
--> statement-breakpoint
CREATE TABLE `publication_audit_bindings` (
	`operation` text NOT NULL,
	`packet_id` text NOT NULL,
	`event_id` text NOT NULL,
	`stream_id` text NOT NULL,
	`stream_seq` integer NOT NULL,
	`event_hash` text NOT NULL,
	`created_at` text DEFAULT CURRENT_TIMESTAMP NOT NULL,
	PRIMARY KEY(`operation`, `packet_id`),
	FOREIGN KEY (`event_id`) REFERENCES `audit_events`(`event_id`) ON UPDATE no action ON DELETE no action,
	CONSTRAINT "publication_audit_operation_check" CHECK("publication_audit_bindings"."operation" in ('edition.publish', 'breaking.publish')),
	CONSTRAINT "publication_audit_seq_check" CHECK("publication_audit_bindings"."stream_seq" > 0),
	CONSTRAINT "publication_audit_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
CREATE UNIQUE INDEX `publication_audit_bindings_event_id_unique` ON `publication_audit_bindings` (`event_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `publication_audit_stream_seq_unique` ON `publication_audit_bindings` (`stream_id`,`stream_seq`);--> statement-breakpoint
PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_audit_anchor_receipts` (
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
	CONSTRAINT "audit_anchor_seq_check" CHECK("__new_audit_anchor_receipts"."stream_seq" > 0),
	CONSTRAINT "audit_anchor_event_hash_check" CHECK(length("event_hash") = 64 and "event_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_anchor_previous_hash_check" CHECK(length("previous_anchor_hash") = 64 and "previous_anchor_hash" not glob '*[^0-9a-f]*'),
	CONSTRAINT "audit_anchor_hash_check" CHECK(length("anchor_hash") = 64 and "anchor_hash" not glob '*[^0-9a-f]*')
);
--> statement-breakpoint
INSERT INTO `__new_audit_anchor_receipts`("anchor_id", "stream_id", "stream_seq", "event_hash", "previous_anchor_hash", "observed_at", "key_id", "signature", "anchor_hash", "created_at") SELECT "anchor_id", "stream_id", "stream_seq", "event_hash", "previous_anchor_hash", "observed_at", "key_id", "signature", "anchor_hash", "created_at" FROM `audit_anchor_receipts`;--> statement-breakpoint
DROP TABLE `audit_anchor_receipts`;--> statement-breakpoint
ALTER TABLE `__new_audit_anchor_receipts` RENAME TO `audit_anchor_receipts`;--> statement-breakpoint
PRAGMA foreign_keys=ON;--> statement-breakpoint
CREATE UNIQUE INDEX `audit_anchor_receipts_anchor_hash_unique` ON `audit_anchor_receipts` (`anchor_hash`);--> statement-breakpoint
CREATE UNIQUE INDEX `audit_anchor_stream_seq_unique` ON `audit_anchor_receipts` (`stream_id`,`stream_seq`);--> statement-breakpoint
CREATE UNIQUE INDEX `audit_anchor_previous_hash_unique` ON `audit_anchor_receipts` (`stream_id`,`previous_anchor_hash`);