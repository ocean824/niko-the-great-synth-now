# Superseded Direct-Platform Handoff — Niko The Great - SYNTH NOW

> This file is retained for project history only. Direct integration with Emergent has been removed from scope. Use `docs/github_handoff.md` and `docs/target_architecture.md` for the current repository-first handoff.

## Build objective

Build a mobile-first Expo/React Native application for musicians, producers, and beat makers. The app lets users discover evidence-backed production information about recorded songs, instruments, synthesizers, VSTs, presets, and historical gear usage; users may submit authorized audio for analysis, but similarity output is never displayed as verified historical fact.

## Required production stack

Use Expo/React Native for iOS and Android. Use Cloudflare Workers for the public API and background-event entry points, Cloudflare Hyperdrive to Neon PostgreSQL for production database access, Cloudflare R2 private buckets for audio and artifact objects, Stripe only in secure backend routes for eligible web/non-native payment paths, native store billing for mobile subscriptions, and Resend for transactional email from a verified sender subdomain.

## Non-negotiable data and trust rules

1. Keep all Neon, R2, Stripe secret/live, webhook, and Resend credentials server-side. No secret can be compiled into the Expo client or committed to Git.
2. A source-backed gear/VST/preset claim must be separate from model output. Audio inferences always have `historicalClaimAllowed: false` until a moderator verifies a source.
3. A separated stem with source bleed must show an artifact banner and cannot return an exact recording claim.
4. R2 raw audio is private. The client uploads with a short-lived, single-object, Worker-issued signed URL; it never receives R2 credentials.
5. All payment provider events are raw-body/signature verified and idempotent. Native subscription product IDs are implemented separately from Stripe web checkout.
6. The application must be usable in portrait orientation with one-handed controls, large touch targets, accessible status labels, and platform-native navigation.

## Implement in this order

1. Replace template MySQL access with Postgres/Neon schema and migrations that preserve the current Synth Now evidence graph.
2. Create Cloudflare Worker endpoints described in `docs/integration_contracts.md` and R2 bucket bindings/lifecycle controls.
3. Build the mobile screens described in `design.md`; use supplied API contracts and do not hard-code fake recognition results as verified facts.
4. Implement sign-in/token storage with platform-safe credential handling and the chosen production identity provider.
5. Implement native iOS/Android subscription product IDs and worker-side entitlement reconciliation. Add Stripe web checkout only behind a platform-appropriate route.
6. Add Resend template delivery for account, analysis, moderation, and subscription lifecycle messages after domain verification.
7. Add integration/unit tests, build validation, and no-secret CI checks.

## Current reference assets

`docs/target_architecture.md` defines system decisions. `docs/integration_contracts.md` defines the Worker/mobile boundary. `design.md` defines the mobile experience. The inherited `../Niko The Great - SYNTH NOW/` workspace contains the original FastAPI, PostgreSQL schema, AWS/Terraform, observability, security, and resilience package for reference; do not treat its AWS deployment as the default production target.
