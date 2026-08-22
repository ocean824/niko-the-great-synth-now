import { AwsClient } from "aws4fetch";
import { Hono } from "hono";
import { z } from "zod";

import { authenticate } from "./auth";
import { withDatabase } from "./db";
import { sendTransactionalEmail } from "./resend";
import { createStripeCheckout, logStripeEvent, verifyStripeWebhook } from "./stripe";
import type { AuthenticatedUser, Env } from "./types";

type Variables = { user: AuthenticatedUser };
const app = new Hono<{ Bindings: Env; Variables: Variables }>();
const MAX_UPLOAD_BYTES = 25_000_000;
const uploadSchema = z.object({ filename: z.string().min(1).max(220), mimeType: z.string().regex(/^audio\//), sizeBytes: z.number().int().positive().max(MAX_UPLOAD_BYTES).optional(), inputType: z.enum(["mix", "stem"]) });

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unexpected request failure";
}

app.use("/v1/*", async (c, next) => {
  if (c.req.path === "/v1/health" || c.req.path === "/v1/webhooks/stripe") return next();
  try {
    await withDatabase(c.env, async (db) => c.set("user", await authenticate(c.req.raw, c.env, db)));
    await next();
  } catch (error) {
    if (error instanceof Response) return error;
    return c.json({ detail: errorMessage(error) }, 401);
  }
});

app.get("/v1/health", (c) => c.json({ service: "synth-now-worker", environment: c.env.APP_ENV, status: "ok" }));

app.get("/v1/presets", async (c) => {
  const query = (c.req.query("query") || "").trim();
  if (!query) return c.json({ items: [] });
  const items = await withDatabase(c.env, async (db) => {
    const result = await db.query<{ id: string; name: string; product: string | null }>(
      `SELECT p.entity_id::text AS id, registry.display_name AS name, bank.bank_version AS product
         FROM presets p
         JOIN entity_registry registry ON registry.id = p.entity_id
         JOIN preset_banks bank ON bank.entity_id = p.preset_bank_entity_id
        WHERE registry.display_name ILIKE $1 OR p.normalized_preset_name ILIKE $1
        ORDER BY registry.display_name ASC
        LIMIT 30`,
      [`%${query}%`],
    );
    return result.rows.map((row) => ({ ...row, evidenceLabel: "official" }));
  });
  return c.json({ items });
});

app.post("/v1/analysis/uploads", async (c) => {
  const parsed = uploadSchema.safeParse(await c.req.json());
  if (!parsed.success) return c.json({ detail: "Invalid upload request", issues: parsed.error.issues }, 422);
  const user = c.get("user");
  const jobId = crypto.randomUUID();
  const safeName = parsed.data.filename.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-120);
  const objectKey = `uploads/${user.id}/${jobId}/${safeName}`;
  const expiresAt = new Date(Date.now() + 10 * 60 * 1000);
  await withDatabase(c.env, async (db) => db.query(
    `INSERT INTO audio_upload_intents (id, owner_user_id, object_key, filename, declared_mime_type, declared_size_bytes, input_type, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
    [jobId, user.id, objectKey, parsed.data.filename, parsed.data.mimeType, parsed.data.sizeBytes || null, parsed.data.inputType, expiresAt],
  ));
  const signer = new AwsClient({ accessKeyId: c.env.R2_ACCESS_KEY_ID, secretAccessKey: c.env.R2_SECRET_ACCESS_KEY });
  const url = new URL(`https://${c.env.R2_PRESIGN_ACCOUNT_ID}.r2.cloudflarestorage.com/${c.env.R2_UPLOADS_BUCKET}/${objectKey}`);
  url.searchParams.set("X-Amz-Expires", "600");
  const signed = await signer.sign(new Request(url, { method: "PUT", headers: { "content-type": parsed.data.mimeType } }), { aws: { signQuery: true } });
  return c.json({ jobId, upload: { method: "PUT", url: signed.url, headers: { "content-type": parsed.data.mimeType }, expiresAt: expiresAt.toISOString() }, constraints: { maxBytes: MAX_UPLOAD_BYTES, acceptedMimePrefixes: ["audio/"], retentionClass: "temporary-analysis" } }, 201);
});

app.post("/v1/analysis/uploads/:jobId/complete", async (c) => {
  const user = c.get("user");
  const jobId = c.req.param("jobId");
  const upload = await withDatabase(c.env, async (db) => db.query<{ object_key: string; declared_mime_type: string; declared_size_bytes: number | null }>(
    `SELECT object_key, declared_mime_type, declared_size_bytes FROM audio_upload_intents WHERE id = $1 AND owner_user_id = $2 AND status = 'awaiting_upload' AND expires_at > now()`,
    [jobId, user.id],
  ));
  if (!upload.rowCount) return c.json({ detail: "Upload grant is invalid or expired" }, 404);
  const object = await c.env.R2_UPLOADS.head(upload.rows[0].object_key);
  if (!object || object.size > MAX_UPLOAD_BYTES) return c.json({ detail: "Uploaded object is missing or exceeds the authorized limit" }, 422);
  const assetId = crypto.randomUUID();
  const runId = crypto.randomUUID();
  await withDatabase(c.env, async (db) => {
    await db.query("BEGIN");
    try {
      await db.query(`UPDATE audio_upload_intents SET status = 'uploaded', completed_at = now() WHERE id = $1`, [jobId]);
      await db.query(
        `INSERT INTO audio_assets (id, owner_user_id, storage_uri, content_sha256, consent_version, source_type, retention_expires_at)
         VALUES ($1, $2, $3, repeat('0', 64), 'mobile-authorized-upload-v1', 'upload', now() + interval '7 days')`,
        [assetId, user.id, `r2://${c.env.R2_UPLOADS_BUCKET}/${upload.rows[0].object_key}`],
      );
      await db.query(
        `INSERT INTO audio_analysis_runs (id, audio_asset_id, model_bundle_version, configuration, status, retention_expires_at)
         VALUES ($1, $2, 'pending-analysis-worker', jsonb_build_object('input_type', $3), 'queued', now() + interval '30 days')`,
        [runId, assetId, "unknown"],
      );
      await db.query("COMMIT");
    } catch (error) {
      await db.query("ROLLBACK");
      throw error;
    }
  });
  await c.env.ANALYSIS_QUEUE.send({ runId, assetId, ownerUserId: user.id, objectKey: upload.rows[0].object_key });
  return c.json({ id: runId, state: "queued", message: "Private analysis is queued." }, 202);
});

app.get("/v1/analysis/:jobId", async (c) => {
  const user = c.get("user");
  const id = c.req.param("jobId");
  const result = await withDatabase(c.env, async (db) => db.query<{ id: string; status: string; failure_reason: string | null }>(
    `SELECT run.id::text AS id, run.status::text AS status, run.failure_reason
       FROM audio_analysis_runs run
       JOIN audio_assets asset ON asset.id = run.audio_asset_id
      WHERE run.id = $1 AND asset.owner_user_id = $2`,
    [id, user.id],
  ));
  if (!result.rowCount) return c.json({ detail: "Analysis job not found" }, 404);
  const run = result.rows[0];
  return c.json({ id: run.id, state: run.status, message: run.failure_reason || undefined, historicalClaimAllowed: false });
});

app.post("/v1/billing/web-checkout", async (c) => {
  if (c.req.header("x-client-surface") !== "web") return c.json({ detail: "Native purchases must use the approved platform subscription flow." }, 403);
  const body = z.object({ successUrl: z.string().url(), cancelUrl: z.string().url() }).safeParse(await c.req.json());
  if (!body.success) return c.json({ detail: "Invalid checkout redirect URLs" }, 422);
  return c.json(await createStripeCheckout(c.env, c.get("user").id, body.data.successUrl, body.data.cancelUrl));
});

app.post("/v1/webhooks/stripe", async (c) => {
  const rawBody = await c.req.raw.text();
  try {
    const event = await verifyStripeWebhook(rawBody, c.req.header("stripe-signature"), c.env.STRIPE_WEBHOOK_SECRET);
    const fresh = await withDatabase(c.env, (db) => logStripeEvent(db, event, rawBody));
    return c.json({ received: true, replay: !fresh });
  } catch (error) {
    if (error instanceof Response) return error;
    return c.json({ detail: errorMessage(error) }, 400);
  }
});

app.post("/v1/internal/email", async (c) => {
  if (c.req.header("x-internal-token") !== c.env.INTERNAL_EMAIL_TOKEN) return c.json({ detail: "Internal email route is restricted" }, 403);
  const body = z.object({ to: z.string().email(), subject: z.string().min(1).max(200), html: z.string().min(1), templateKey: z.string().min(1), userId: z.string().uuid().optional(), triggerReference: z.string().max(200).optional() }).safeParse(await c.req.json());
  if (!body.success) return c.json({ detail: "Invalid email request" }, 422);
  const result = await withDatabase(c.env, (db) => sendTransactionalEmail(c.env, db, body.data));
  return c.json(result, 202);
});

export default app;
