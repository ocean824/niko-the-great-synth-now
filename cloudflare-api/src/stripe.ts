import type { Client } from "pg";
import type { Env } from "./types";

const encoder = new TextEncoder();

function constantTimeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let result = 0;
  for (let index = 0; index < left.length; index += 1) result |= left.charCodeAt(index) ^ right.charCodeAt(index);
  return result === 0;
}

function hex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((value) => value.toString(16).padStart(2, "0")).join("");
}

export async function verifyStripeWebhook(rawBody: string, signature: string | null | undefined, secret: string): Promise<Record<string, unknown>> {
  if (!signature || !secret) throw new Response(JSON.stringify({ detail: "Missing Stripe signature configuration" }), { status: 400 });
  const parts = Object.fromEntries(signature.split(",").map((item) => item.split("=", 2)));
  const timestamp = Number(parts.t);
  if (!Number.isFinite(timestamp) || Math.abs(Date.now() / 1000 - timestamp) > 300) throw new Response(JSON.stringify({ detail: "Expired Stripe signature" }), { status: 400 });
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const computed = hex(await crypto.subtle.sign("HMAC", key, encoder.encode(`${timestamp}.${rawBody}`)));
  if (!parts.v1 || !constantTimeEqual(computed, parts.v1)) throw new Response(JSON.stringify({ detail: "Invalid Stripe signature" }), { status: 400 });
  return JSON.parse(rawBody) as Record<string, unknown>;
}

export async function logStripeEvent(db: Client, event: Record<string, unknown>, rawBody: string): Promise<boolean> {
  const id = typeof event.id === "string" ? event.id : null;
  const type = typeof event.type === "string" ? event.type : "unknown";
  if (!id) throw new Response(JSON.stringify({ detail: "Stripe event id is missing" }), { status: 400 });
  const digest = hex(await crypto.subtle.digest("SHA-256", encoder.encode(rawBody)));
  const inserted = await db.query(
    `INSERT INTO provider_event_log (provider, external_event_id, event_type, payload_sha256, outcome)
     VALUES ('stripe_web', $1, $2, $3, 'received')
     ON CONFLICT (provider, external_event_id) DO NOTHING`,
    [id, type, digest],
  );
  return Boolean(inserted.rowCount);
}

export async function createStripeCheckout(env: Env, userId: string, successUrl: string, cancelUrl: string): Promise<{ url: string }> {
  if (!env.STRIPE_SECRET_KEY || !env.STRIPE_WEB_PRICE_ID) throw new Response(JSON.stringify({ detail: "Stripe web checkout is not configured" }), { status: 503 });
  const form = new URLSearchParams({ mode: "subscription", success_url: successUrl, cancel_url: cancelUrl, client_reference_id: userId });
  form.set("line_items[0][price]", env.STRIPE_WEB_PRICE_ID);
  form.set("line_items[0][quantity]", "1");
  const response = await fetch("https://api.stripe.com/v1/checkout/sessions", { method: "POST", headers: { Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`, "Content-Type": "application/x-www-form-urlencoded" }, body: form });
  if (!response.ok) throw new Response(JSON.stringify({ detail: "Stripe could not create checkout" }), { status: 502 });
  const session = await response.json<{ url?: string }>();
  if (!session.url) throw new Response(JSON.stringify({ detail: "Stripe did not provide checkout URL" }), { status: 502 });
  return { url: session.url };
}
