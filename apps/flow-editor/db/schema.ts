import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";
export const flowRevisions = sqliteTable("flow_revisions", {
  revision: integer("revision").primaryKey(), document: text("document").notNull(),
  hash: text("hash").notNull(), authorId: text("author_id").notNull(),
  note: text("note").notNull(), createdAt: text("created_at").notNull(),
  basedOnRevision: integer("based_on_revision"),
});
export const flowVersions = sqliteTable("flow_versions", {
  id: text("id").primaryKey(), label: text("label").notNull().unique(),
  revision: integer("revision").notNull().references(() => flowRevisions.revision),
  note: text("note").notNull(), authorId: text("author_id").notNull(), createdAt: text("created_at").notNull(),
});

export const flowVersionDeletions = sqliteTable("flow_version_deletions", {
  id:text("id").primaryKey(), label:text("label").notNull(),
  revision:integer("revision").notNull().references(() => flowRevisions.revision),
  deletedBy:text("deleted_by").notNull(), deletedAt:text("deleted_at").notNull(),
});

export const flowAccessLinks = sqliteTable("flow_access_links", {
  id:text("id").primaryKey(), tokenHash:text("token_hash").notNull().unique(),
  label:text("label").notNull(), role:text("role").notNull(),
  createdAt:text("created_at").notNull(), revokedAt:text("revoked_at"),
});

export const flowEditSessions=sqliteTable("flow_edit_sessions",{
 tokenHash:text("token_hash").primaryKey(),label:text("label").notNull(),
 expiresAt:integer("expires_at").notNull(),passwordVersion:text("password_version").notNull(),
});
export const flowUnlockAttempts=sqliteTable("flow_unlock_attempts",{
 clientHash:text("client_hash").primaryKey(),windowId:integer("window_id").notNull(),attempts:integer("attempts").notNull(),
});

export const flowAttachments=sqliteTable("flow_attachments",{
 id:text("id").primaryKey(),name:text("name").notNull(),size:integer("size").notNull(),mime:text("mime").notNull(),
 storageKey:text("storage_key").notNull(),createdAt:text("created_at").notNull(),authorId:text("author_id").notNull(),
});
