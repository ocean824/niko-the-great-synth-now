# Niko The Great - SYNTH NOW — Mobile Target Architecture

## Executive architecture decision

The cost-effective default is an **Expo mobile client** backed by a **Cloudflare Worker API**, **Neon PostgreSQL** for authoritative relational and vector data, and **Cloudflare R2** for private audio uploads and approved reference artifacts. The Worker uses a Cloudflare Hyperdrive binding to Neon in production, keeping the Neon connection secret out of the app and providing pooled database access at the edge. Cloudflare documents Hyperdrive as its recommended Neon connection pattern for Workers, while the Neon serverless driver remains a valid fallback for lower-complexity environments.[1]

The existing FastAPI/Kubernetes/AWS package remains a detailed analysis-service and resilience reference. It should not be the default mobile serving path. Heavy audio separation, fingerprint extraction, and model inference are delegated to a separately metered analysis worker/provider after a Worker creates an authorized job; a Cloudflare Worker is not used for long-running DSP.

## Cost and responsibility model

| Layer | Default technology | Responsibility | Cost-control mechanism |
| --- | --- | --- | --- |
| Mobile client | Expo + React Native | User interaction, secure token storage, authorized upload selection, result presentation. | Direct-to-R2 upload avoids API bandwidth/proxy work. |
| Public API | Cloudflare Workers + Hono-compatible route design | Authentication, authorization, typed API, signed upload/download grants, mutation validation, entitlement lookup, webhook receipt. | Short, stateless requests; cache safe public/read models at edge; no DSP in Worker. |
| Database | Neon PostgreSQL + pgvector | Claims/evidence, gear/preset graph, users, entitlements, job metadata, vector references, audit history. | Autosuspend/branching in non-production, pooled Hyperdrive connections, targeted indexes, cursor pagination, archived evidence only. |
| Object storage | Cloudflare R2 | Private authorized clips, source artifacts, generated analysis outputs, immutable evidence attachments. | Direct presigned upload, separate `uploads` and `approved-assets` buckets, expiration lifecycle for temporary clips, content-hash deduplication. |
| Audio analysis | Separate queue/worker/provider | Source separation, fingerprinting, feature extraction, similarity retrieval. | Async jobs, file-size/duration caps, budget quotas, reuse cached jobs by content hash, no synchronous model invocation. |
| Payments | Native store billing for mobile digital subscriptions; Stripe for supported web/outside-native checkout. | Purchase lifecycle, reconciliation, billing webhooks, web subscription checkout. | One entitlement ledger in Neon; no live secrets in app; native-flow selection avoids incorrect in-app payment path. |
| Email | Resend | Transactional account, analysis, moderation, and billing-status emails. | Verified purpose-specific sender subdomain; event-triggered templates; suppress duplicate notifications. |

## Request and event flow

```text
Expo app
  ├─ authenticated API request ────────────> Cloudflare Worker ──Hyperdrive──> Neon PostgreSQL
  ├─ upload grant request ─────────────────> Cloudflare Worker ──────────────> R2 signed PUT URL
  ├─ direct authorized clip upload ──────────────────────────────────────────> private R2 uploads bucket
  └─ job status polling / optional WebSocket ─> Cloudflare Worker ───────────> Neon job state

Cloudflare Worker ──authorized event──> analysis queue/provider ──results──> private R2 + Neon
Stripe / App Store / Google Play ──verified webhook/receipt──> Worker ──────> Neon entitlement ledger
Worker ──transactional request──> Resend ──verified sender domain──> recipient
```

## Data ownership and safety boundaries

Neon is the source of truth for product data. The prior evidence-model boundary remains unchanged: a model output or similarity response can create an `audio_inference` record but cannot independently create a published historical gear/VST/preset claim. Published claims require an evidence source and moderation transition.

R2 is object storage, not a public catalog. Raw incoming audio is stored under an opaque per-job key, never a user-entered filename. The client receives a short-lived, single-object signed upload grant only after creating an analysis request. The Worker validates expected MIME family, size, duration declaration, ownership, and retention class before issuing the grant. The worker later confirms object metadata and checksum before passing it to the analysis queue.

## Neon schema migration approach

The existing authoritative PostgreSQL schema is portable to Neon because Neon is PostgreSQL-compatible. Preserve the entity registry, gear/product/preset structure, recording/claim/evidence graph, audio-inference boundary, reference assets, Chromaprint artifacts, and versioned feature vector records. The mobile project’s initial MySQL Drizzle schema is replaced by a Postgres-oriented schema and SQL migrations; the old template users table is not treated as authoritative.

| Migration wave | Scope | Completion signal |
| --- | --- | --- |
| **1. Foundation** | Enable pgvector; create users, entities, aliases, sources, audit timestamps, and migration ledger. | Staging Neon migration applies and rollback path is documented. |
| **2. Knowledge graph** | Gear, manufacturers, software/VST products, presets, recordings, claims, evidence, scopes, and reviews. | Existing schema fixture loads without loss of claim/source separation. |
| **3. Audio and storage** | Reference assets, fingerprint artifacts, feature-model registry, embeddings, audio jobs, R2 object references, and retention data. | Query paths return only authorized object metadata; no direct R2 credentials are stored. |
| **4. Commerce and communications** | Entitlement ledger, provider event ids, webhook audit/replay protection, email delivery records, and preference states. | Replayed webhook does not create duplicate entitlement/email rows. |

## Stripe, native purchases, and entitlement rules

The mobile app does not contain Stripe secret/live keys. Native subscriptions use the required platform-native entitlement process and product IDs. Stripe can be used for a web checkout or any eligible non-native payment flow through a Worker-created checkout session. A single entitlement projection in Neon represents access, regardless of origin.

Stripe requires webhook signature verification using the raw request body, the `Stripe-Signature` header, and the endpoint’s signing secret.[2] The Worker stores an idempotency record keyed by provider event id before performing entitlement side effects. Acknowledgement is fast; noncritical email and analytics follow-up is asynchronous.

## Resend email policy

Resend calls originate only from the Worker. A verified sender domain is required, and a dedicated transactional subdomain such as `account.synthnow.example` should isolate essential account/billing mail from marketing reputation.[3] Store only message ID, template key, recipient hash/reference, trigger source, delivery status, and limited error classification in Neon—never an API key or raw sensitive payload in client logs.

## References

[1]: https://developers.cloudflare.com/workers/databases/third-party-integrations/neon/ "Cloudflare Workers: Neon"
[2]: https://docs.stripe.com/webhooks "Stripe: Receive events in your webhook endpoint"
[3]: https://resend.com/docs/dashboard/domains/introduction "Resend: Verified Domains"
