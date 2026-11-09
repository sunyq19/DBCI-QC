import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
export const flowRevisions = sqliteTable("flow_revisions", {
  revision: integer("revision").primaryKey(), document: text("document").notNull(),
  hash: text("hash").notNull(), authorId: text("author_id").notNull(),
  note: text("note").notNull(), createdAt: text("created_at").notNull(),
});
export const flowVersions = sqliteTable("flow_versions", {
  id: text("id").primaryKey(), label: text("label").notNull().unique(),
  revision: integer("revision").notNull().references(() => flowRevisions.revision),
  note: text("note").notNull(), authorId: text("author_id").notNull(), createdAt: text("created_at").notNull(),
});

export const flowAccessLinks = sqliteTable("flow_access_links", {
  id:text("id").primaryKey(), tokenHash:text("token_hash").notNull().unique(),
  label:text("label").notNull(), role:text("role").notNull(),
  createdAt:text("created_at").notNull(), revokedAt:text("revoked_at"),
});
