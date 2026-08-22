# Synth Now — Cloudflare, Neon, R2, Stripe, and Resend Contracts

## Public Worker API surface

All routes are versioned under `/v1`. The mobile client is never given a Neon, R2, Stripe secret, Resend key, or service credential.

| Route | Caller | Purpose | Persistence / side effect |
| --- | --- | --- | --- |
| `GET /v1/presets` | Authenticated or public policy route | Cursor-paginated preset discovery with source/evidence fields. | Neon read; cache safe public result fragments. |
| `GET /v1/presets/:id` | Authenticated or public policy route | Canonical preset detail, safe provenance, compatible product/version, related gear. | Neon read; never returns a direct private artifact URL. |
| `POST /v1/analysis/uploads` | Authenticated user | Validates request and creates a private upload grant. | Neon `audio_analysis_job` in `awaiting_upload`; returns signed R2 PUT URL and opaque object key. |
| `POST /v1/analysis/uploads/:jobId/complete` | Authenticated user | Confirms uploaded object metadata/checksum and queues analysis. | Neon job transition + queue event. |
| `GET /v1/analysis/:jobId` | Job owner/moderator | Returns job state, result type, confidence dimensions, artifact flags, and allowed result payload. | Neon read. |
| `GET /v1/gear/:id` | Authenticated or public policy route | Gear history, official link, source-backed usage, related products. | Neon read. |
| `POST /v1/billing/web-checkout` | Authenticated eligible web session | Creates Stripe Checkout only on approved non-native surface. | Stripe API through Worker; Neon checkout attempt audit. |
| `POST /v1/webhooks/stripe` | Stripe only | Verifies raw-body Stripe signature and reconciles entitlement. | Neon idempotent provider event + entitlement mutation. |
| `POST /v1/webhooks/native/:platform` | Trusted server-to-server receiver | Verifies Apple/Google provider event/receipt through approved server process. | Neon idempotent provider event + entitlement mutation. |
| `POST /v1/internal/email` | Worker-only internal service binding | Validated transactional template send through Resend. | Resend request + Neon delivery audit. |

## Upload grant response

```json
{
  "jobId": "job_opaque_id",
  "upload": {
    "method": "PUT",
    "url": "https://...short-lived-signed-r2-url...",
    "headers": { "content-type": "audio/wav" },
    "expiresAt": "2026-08-22T19:10:00Z"
  },
  "constraints": {
    "maxBytes": 25000000,
    "acceptedMimePrefixes": ["audio/"],
    "retentionClass": "temporary-analysis"
  }
}
```

The signed URL is a transport grant, not a stable asset link. The app persists only the `jobId`; it removes local temporary files after an upload succeeds or is cancelled, subject to user-visible confirmation.

## Confidence/result contract

```json
{
  "resultKind": "similarity_candidate",
  "historicalClaimAllowed": false,
  "artifactFlags": ["source_bleed"],
  "confidence": {
    "inputQuality": "moderate",
    "separationIntegrity": "limited",
    "referenceCompatibility": "moderate",
    "candidateMargin": "low",
    "temporalConsensus": "moderate"
  }
}
```

The mobile UI must display the banner and result-kind label before a user can interpret a candidate as a documented production fact.

## Environment and secret contract

| Variable / binding | Runtime | Rule |
| --- | --- | --- |
| `HYPERDRIVE` | Cloudflare Worker binding | Production Neon access; never in mobile bundle. |
| `NEON_DATABASE_URL` | Local migration/test only | Protected secret; not a `EXPO_PUBLIC_*` variable. |
| `R2_UPLOADS`, `R2_APPROVED_ASSETS` | Cloudflare Worker bindings | Private buckets; only Worker signs/object-manages. |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Worker secret when S3 presigning is used | Never shipped to app, logged, or committed. |
| `STRIPE_SECRET_KEY` | Worker secret | Live/test environment-separated; server-only. |
| `STRIPE_WEBHOOK_SECRET` | Worker secret | Per webhook endpoint; raw body required for verification. |
| `RESEND_API_KEY` | Worker secret | Server-only. |
| `RESEND_FROM_EMAIL` | Worker environment variable | Must use a verified transactional sender domain. |
| `EXPO_PUBLIC_API_BASE_URL` | Expo build-time public config | Contains only the Worker API base URL. |
| `EXPO_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Expo build-time public config only if native SDK requires it | Publishable key only; never a secret/live secret key. |

## Event idempotency

Every provider event uses the tuple `(provider, external_event_id)` as a unique idempotency key. The Worker first stores an immutable event audit row, then performs a state transition in the same database transaction. Replays return a successful acknowledgement without duplicating an entitlement, email, or audit effect.
