# GitHub Handoff — Niko The Great - SYNTH NOW

## Scope

This repository is the source-controlled mobile rebuild for Synth Now. It contains the Expo mobile client, Cloudflare Worker edge service, Neon SQL migrations, R2/Stripe/Resend placeholder contract, documentation, and a sanitized archival copy of the prior FastAPI/AWS resilience work.

Direct integration with Emergent is intentionally **out of scope** for this build. The repository is the handoff artifact. Any downstream platform can import or clone the codebase and follow `docs/target_architecture.md`, `docs/integration_contracts.md`, and `cloudflare-api/README.md`.

## Publication requirements

The remote repository must be private. Prior to push, scan for credentials, keep all values in environment examples as placeholders, exclude local database files/uploads/node modules, and keep Cloudflare `.dev.vars` untracked. Do not publish source audio, user uploads, Cloudflare secrets, Stripe secrets, Resend credentials, provider export files, or generated state artifacts.

The source package contains the CI workflow at `workflow-templates/mobile-edge-ci.yml`, rather than `.github/workflows/`, because the GitHub App used for the initial repository push has no permission to create workflow files. After granting the app **Workflows** permission, move that file to `.github/workflows/mobile-edge-ci.yml` and commit it through the authorized GitHub session. The template is complete and intentionally remains versioned with the repository.

## Repository layout

| Path | Purpose |
| --- | --- |
| `app`, `components`, `lib` | Expo mobile UI and client-side API/upload contract. |
| `cloudflare-api` | Cloudflare Worker, Neon/R2/Stripe/Resend server-only integrations, and migrations. |
| `docs` | Product design, target architecture, service contracts, deployment research, and GitHub handoff. |
| `workflow-templates` | GitHub Actions CI workflow ready to move into `.github/workflows/` after Workflows permission is enabled. |
| `reference-fastapi-platform` | Sanitized archive of the earlier FastAPI, security, testing, AWS/Terraform, resilience, and topology package. |
| `design.md`, `todo.md` | Mobile design decisions and durable project history. |

## tldr

1. Create a private GitHub repository named `niko-the-great-synth-now`.
2. Push this entire sanitized source tree after checks pass.
3. Grant Workflows permission, then move the tracked CI template into `.github/workflows/`.
4. Configure secrets only in Cloudflare/GitHub environment managers after the repository is private.
5. Use the documented Neon → R2 → Worker → Stripe/Resend deployment order.
