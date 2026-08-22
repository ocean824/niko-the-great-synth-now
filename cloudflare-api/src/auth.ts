import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";
import type { Client } from "pg";

import type { AuthenticatedUser, Env } from "./types";

function emailFor(payload: JWTPayload): string {
  const email = typeof payload.email === "string" ? payload.email : null;
  if (email) return email.toLowerCase();
  return `${payload.sub}@token.invalid`.slice(0, 320);
}

function roleFor(payload: JWTPayload): string {
  const role = typeof payload.role === "string" ? payload.role : "member";
  return ["member", "contributor", "reviewer", "editor", "admin", "verified_creator"].includes(role) ? role : "member";
}

export async function authenticate(request: Request, env: Env, db: Client): Promise<AuthenticatedUser> {
  const header = request.headers.get("authorization");
  if (!header?.startsWith("Bearer ")) throw new Response(JSON.stringify({ detail: "Bearer access token is required" }), { status: 401 });
  if (!env.OIDC_JWKS_URL || !env.OIDC_ISSUER || !env.OIDC_AUDIENCE) throw new Response(JSON.stringify({ detail: "OIDC is not configured" }), { status: 503 });

  const token = header.slice("Bearer ".length);
  const keySet = createRemoteJWKSet(new URL(env.OIDC_JWKS_URL));
  const { payload } = await jwtVerify(token, keySet, { issuer: env.OIDC_ISSUER, audience: env.OIDC_AUDIENCE });
  if (!payload.sub) throw new Response(JSON.stringify({ detail: "Token subject is required" }), { status: 401 });

  const existing = await db.query<{ id: string; email: string; role: string }>(
    `SELECT u.id, u.email, u.role
       FROM user_identity_mappings map
       JOIN users u ON u.id = map.user_id
      WHERE map.provider_subject = $1 AND map.issuer = $2`,
    [payload.sub, env.OIDC_ISSUER],
  );
  if (existing.rowCount) return { id: existing.rows[0].id, subject: payload.sub, email: existing.rows[0].email, role: roleFor(payload) };

  const user = await db.query<{ id: string; email: string }>(
    `INSERT INTO users (email, display_name, role)
     VALUES ($1, $2, $3)
     ON CONFLICT (email) DO UPDATE SET updated_at = now()
     RETURNING id, email`,
    [emailFor(payload), (typeof payload.name === "string" ? payload.name : payload.sub).slice(0, 240), roleFor(payload)],
  );
  await db.query(
    `INSERT INTO user_identity_mappings (provider_subject, user_id, issuer)
     VALUES ($1, $2, $3)
     ON CONFLICT (provider_subject) DO UPDATE SET user_id = EXCLUDED.user_id, issuer = EXCLUDED.issuer, updated_at = now()`,
    [payload.sub, user.rows[0].id, env.OIDC_ISSUER],
  );
  return { id: user.rows[0].id, subject: payload.sub, email: user.rows[0].email, role: roleFor(payload) };
}
