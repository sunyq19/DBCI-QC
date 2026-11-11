CREATE TABLE `flow_version_deletions` (
	`id` text PRIMARY KEY NOT NULL,
	`label` text NOT NULL,
	`revision` integer NOT NULL,
	`deleted_by` text NOT NULL,
	`deleted_at` text NOT NULL,
	FOREIGN KEY (`revision`) REFERENCES `flow_revisions`(`revision`) ON UPDATE no action ON DELETE no action
);
