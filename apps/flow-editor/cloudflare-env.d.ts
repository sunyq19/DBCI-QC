declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    FLOW_EDITOR_EMAILS?: string;
    BUCKET?: R2Bucket;
  }
}
