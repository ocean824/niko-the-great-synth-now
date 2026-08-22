# Synth Now Cloudflare Edge API

This package is the cost-efficient production boundary for **Niko The Great - SYNTH NOW**. It exposes the mobile API through Cloudflare Workers, reaches Neon PostgreSQL through a Hyperdrive binding, stores authorized audio and approved artifacts in private R2 buckets, creates secure Stripe web checkout sessions only for eligible web clients, and sends transactional email through Resend.

The Worker does **not** run source separation, audio fingerprinting, or model inference. It validates an authorized upload, creates an opaque R2 object key, persists an analysis run, and sends an asynchronous job payload to the separate analysis queue. Model output stays in the private analysis domain and cannot publish a historical gear/VST/preset claim.

## Deployment order

| Step | Action | Guardrail |
| --- | --- | --- |
| **1. Neon** | Create a Neon project/database and a least-privilege Hyperdrive role. Apply `migrations/0001_core_evidence_schema.sql`, then `migrations/0002_mobile_edge_contracts.sql` in staging first. | Enable required PostgreSQL extensions before the core migration; take a Neon branch/backup before each migration. |
| **2. Cloudflare storage** | Create private `synth-now-private-uploads` and `synth-now-approved-assets` R2 buckets. Configure lifecycle expiration for temporary uploads and never attach a public bucket domain to raw uploads. | The Worker issues short-lived, per-object upload grants; R2 credentials never reach Expo. |
| **3. Worker** | Replace only non-secret `wrangler.jsonc` placeholders with resource identifiers; bind Hyperdrive, both R2 buckets, and the analysis queue. | Do not place secrets in `wrangler.jsonc`, Expo config, git, or CI logs. |
| **4. Worker secrets** | Run `wrangler secret put` for `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, and `INTERNAL_EMAIL_TOKEN`. | Use environment-specific test/live keys. There are intentionally no live values in this repository. |
| **5. Stripe and native subscriptions** | Set `STRIPE_WEB_PRICE_ID` to the eligible web subscription price ID. Configure native Apple/Google product IDs in the respective store systems and verify through a server-side provider integration. | The mobile app must not embed a Stripe secret; web checkout is rejected when `x-client-surface` is not `web`. |
| **6. Resend** | Verify a sender domain/subdomain, set `RESEND_FROM_EMAIL`, and configure transactional templates. | Verify the domain before sending; use an account/transactional subdomain, not a generic personal sender. |
| **7. Deploy** | Run `pnpm check`, then deploy from a protected environment. | Confirm the API health route and use only synthetic/staging audio before enabling real users. |

## R2 retention classes

| Class | Bucket | Intended expiration | Access |
| --- | --- | --- | --- |
| `temporary-analysis` | Private uploads | Seven days after job acceptance, or earlier on cancellation. | Owner and authorized analysis worker only. |
| `analysis-output` | Private uploads or result bucket | Thirty days by default; extend only with a documented user/library need. | Owner, approved reviewer, authorized analysis worker. |
| `approved-reference` | Approved assets | Retained per license/evidence policy. | Worker-issued download grant only unless license allows public distribution. |

## tldr

1. Create Neon, Cloudflare Hyperdrive, private R2 buckets, and an analysis queue.
2. Apply the two numbered SQL migrations to a Neon staging branch.
3. Copy `.dev.vars.example` to `.dev.vars` only for local development; never replace placeholders in tracked files.
4. Add production values as Cloudflare Worker secrets, configure Stripe/Resend/domain providers, and deploy from a protected CI environment.
5. Point the Expo build’s `EXPO_PUBLIC_API_BASE_URL` at the deployed Worker, then verify signed upload, analysis-job ownership, webhook idempotency, and email delivery with staging data.
