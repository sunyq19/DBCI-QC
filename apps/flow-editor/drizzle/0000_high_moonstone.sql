CREATE TABLE `flow_revisions` (
	`revision` integer PRIMARY KEY NOT NULL,
	`document` text NOT NULL,
	`hash` text NOT NULL,
	`author_id` text NOT NULL,
	`note` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `flow_versions` (
	`id` text PRIMARY KEY NOT NULL,
	`label` text NOT NULL,
	`revision` integer NOT NULL,
	`note` text NOT NULL,
	`author_id` text NOT NULL,
	`created_at` text NOT NULL,
	FOREIGN KEY (`revision`) REFERENCES `flow_revisions`(`revision`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `flow_versions_label_unique` ON `flow_versions` (`label`);