CREATE TABLE `flow_edit_sessions` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`label` text NOT NULL,
	`expires_at` integer NOT NULL,
	`password_version` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `flow_unlock_attempts` (
	`client_hash` text PRIMARY KEY NOT NULL,
	`window_id` integer NOT NULL,
	`attempts` integer NOT NULL
);
--> statement-breakpoint
ALTER TABLE `flow_revisions` ADD `based_on_revision` integer;