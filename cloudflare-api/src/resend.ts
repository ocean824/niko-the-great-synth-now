import type { Client } from "pg";
import type { Env } from "./types";

export async function sendTransactionalEmail(
  env: Env,
  db: Client,
  input: { userId?: string; to: string; templateKey: string; subject: string; html: string; triggerReference?: string },
): Promise<{ id: string }> {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: env.RESEND_FROM_EMAIL, to: [input.to], subject: input.subject, html: input.html }),
  });
  if (!response.ok) throw new Response(JSON.stringify({ detail: "Resend rejected the email" }), { status: 502 });
  const result = await response.json<{ id: string }>();
  await db.query(
    `INSERT INTO email_delivery_records (user_id, resend_message_id, template_key, recipient_reference, trigger_reference)
     VALUES ($1, $2, $3, $4, $5)`,
    [input.userId || null, result.id, input.templateKey, input.to, input.triggerReference || null],
  );
  return result;
}
