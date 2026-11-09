CREATE TABLE `flow_attachments` (
	`id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`size` integer NOT NULL,
	`mime` text NOT NULL,
	`storage_key` text NOT NULL,
	`created_at` text NOT NULL,
	`author_id` text NOT NULL
);
