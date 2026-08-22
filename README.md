# Niko The Great - SYNTH NOW

**Niko The Great - SYNTH NOW** is a mobile-first music-production intelligence platform for musicians, beat makers, and producers. The product connects authorized audio analysis with an evidence-backed knowledge graph for instruments, synthesizers, VSTs, presets, gear history, and documented recording uses.

The core product promise is deliberately narrow: **audio similarity is useful discovery, not historical proof**. The app displays verified recording use, official source information, artist association, and audio similarity as distinct result types. A separated stem with source bleed receives an artifact warning and never creates a published gear/VST/preset claim.

## Repository architecture

| Area | Technology | Responsibility |
| --- | --- | --- |
| `app`, `components`, `lib` | Expo SDK 54, React Native, Expo Router | Portrait-first iOS/Android experience, secure API client, authorized audio selection, analysis-status UI, evidence-safe presentation. |
| `cloudflare-api` | Cloudflare Workers, Hono, Hyperdrive, Neon PostgreSQL, R2, Queues | Server-only access control, Neon persistence, R2 signed uploads, asynchronous job handoff, Stripe web webhook/checkouts, Resend transactional email. |
| `cloudflare-api/migrations` | PostgreSQL / pgvector | Preserved Synth Now evidence graph plus mobile identity, upload intent, entitlement, provider event, and email audit tables. |
| `reference-fastapi-platform` | Archived FastAPI, Python DSP, AWS/Terraform, resilience/security/test assets | Prior development reference only. It is not the default cost-effective mobile production serving path. |
| `docs` | Markdown | Product design, target architecture, API contracts, research notes, platform handoff, and release guidance. |

## Mobile experience

The app uses a studio-focused dark visual system with **Signal Cyan**, **Reference Green**, **Violet Tape**, and **Amber Monitor** states. The current product experience includes Today, Discover, Library, Account, private audio selection, private signed-upload preparation, queued analysis status, confidence dimensions, and source-bleed warnings.

Audio is selected through the platform file picker with explicit user authorization. The client asks the Worker for a short-lived upload grant, uploads directly to private R2, then polls the analysis-job state. It does not handle R2 credentials, Neon credentials, Stripe secrets, Resend keys, or raw worker secrets.

## Cost-efficient target stack

| Need | Default implementation | Cost and safety rationale |
| --- | --- | --- |
| Relational/evidence/vector data | Neon PostgreSQL + pgvector | PostgreSQL-compatible model preserves the existing evidence graph and supports branch-first migration/testing. |
| API hosting | Cloudflare Workers + Hyperdrive | Stateless edge requests and pooled server-side database access keep the mobile client simple and secrets out of builds. |
| Audio and approved artifacts | Private Cloudflare R2 buckets | Direct, short-lived signed upload avoids proxying large audio through the API; lifecycle rules control temporary storage. |
| Heavy audio analysis | Separate asynchronous worker/provider | No expensive DSP, stem separation, or inference blocks a Worker request. |
| Native subscriptions | Platform-native product IDs | The entitlement ledger reconciles verified provider events into one access record. |
| Web/eligible checkout | Stripe through Worker only | The app never contains a Stripe secret/live key; Stripe webhook verification is server-only. |
| Transactional email | Resend through Worker only | Uses a verified sender subdomain and retains a small delivery audit record. |

Detailed architecture and endpoint contracts are in [`docs/target_architecture.md`](docs/target_architecture.md) and [`docs/integration_contracts.md`](docs/integration_contracts.md).

## Prerequisites

Install Node.js 22+, pnpm 9+, a supported Expo development environment, and the Cloudflare Wrangler CLI through the `cloudflare-api` package. For production, configure a Neon project with the required PostgreSQL extensions, a Cloudflare account with Workers/Hyperdrive/R2/Queues, native store products, a Stripe account for eligible web checkout, and a Resend verified sender domain.

No live credential belongs in this repository. The code contains `REPLACE_WITH_*` values and a `.dev.vars.example` template only.

## Local mobile development

```bash
pnpm install
pnpm dev
```

Set only a non-secret public Worker base URL when you have a deployed staging API:

```bash
EXPO_PUBLIC_API_BASE_URL=https://api-staging.example.workers.dev
```

Keep credentials server-side. In particular, do not add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, `NEON_DATABASE_URL`, R2 keys, or a Cloudflare API token to an Expo `EXPO_PUBLIC_*` value.

## Cloudflare and Neon deployment

The Worker package has its own commands:

```bash
cd cloudflare-api
pnpm install
pnpm check
```

Apply `0001_core_evidence_schema.sql` followed by `0002_mobile_edge_contracts.sql` to a Neon **staging branch** before production. Then configure Worker resource bindings and use `wrangler secret put` for the six server-only secrets listed in [`cloudflare-api/README.md`](cloudflare-api/README.md). Do not deploy with placeholder IDs.

Cloudflare documents Hyperdrive as the recommended Neon path for Workers; R2 supports Worker-issued presigned URLs for direct mobile upload.[1] Stripe requires raw-body webhook signature verification.[2] Resend requires a verified sender domain before sending mail.[3]

## Payments and email

The native subscription path requires approved iOS and Android store product identifiers and verified server-side purchase events. Stripe is reserved for a secure Worker-created checkout session when the client surface is explicitly `web`; it is not an in-app shortcut around native digital-subscription requirements. The Worker records provider events idempotently before it mutates entitlement data.

Resend sends account, analysis, moderation, and entitlement lifecycle mail only from a verified transactional sender domain. Configure a purpose-specific subdomain, sender address, and email templates outside source control.

## Validation

Run the mobile checks:

```bash
pnpm check
pnpm test
```

Run the Worker type check:

```bash
cd cloudflare-api
./node_modules/.bin/tsc --noEmit
```

The Worker package must also be checked with Wrangler in an approved environment after resources and secrets are configured. Local package-manager build-script policies may require explicit approval in the deployment environment.

## GitHub handoff

This source tree is designed to publish as a **private** GitHub repository. Direct Emergent integration is out of scope; see [`docs/github_handoff.md`](docs/github_handoff.md) for the sanitized repository handoff boundary. The CI workflow is versioned at `workflow-templates/mobile-edge-ci.yml` until the GitHub App is granted Workflows permission, at which point it should be moved to `.github/workflows/`.

## tldr

1. Run the mobile test/type checks and the Worker TypeScript check.
2. Create a private GitHub repository and push this sanitized source tree.
3. Grant GitHub Workflows permission and move `workflow-templates/mobile-edge-ci.yml` into `.github/workflows/`.
4. Create Neon staging and apply both migrations to a branch.
5. Create private R2 buckets, a Cloudflare Hyperdrive binding, and the analysis queue.
6. Enter live Stripe, Resend, R2, and internal token values only as Cloudflare Worker secrets—not in the app or Git.
7. Deploy the Worker, set `EXPO_PUBLIC_API_BASE_URL`, verify a synthetic upload/job flow, then configure native product IDs and verified payment/email webhooks.

## References

[1]: https://developers.cloudflare.com/workers/databases/third-party-integrations/neon/ "Cloudflare Workers: Neon"
[2]: https://docs.stripe.com/webhooks "Stripe: Receive events in your webhook endpoint"
[3]: https://resend.com/docs/dashboard/domains/introduction "Resend: Verified Domains"
