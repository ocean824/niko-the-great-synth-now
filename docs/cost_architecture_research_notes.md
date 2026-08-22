# Cost Architecture Research Notes

Cloudflare documents two supported patterns for connecting a Worker to Neon: Hyperdrive, which Cloudflare recommends for pooled, low-latency Worker-to-database access, or the Neon serverless driver. Hyperdrive uses a dedicated Neon role/connection string and a Worker binding; direct mobile clients must never receive this credential. Source: https://developers.cloudflare.com/workers/databases/third-party-integrations/neon/

Cloudflare R2 documents server-generated presigned URLs for direct browser/mobile upload without proxying large files through a Worker. The Worker holds the R2 credentials, signs a time-bounded PUT request, and returns only the temporary URL to the client. Source: https://developers.cloudflare.com/r2/objects/upload-objects/

Initial architecture consequence: the Expo client uploads authorized clips directly to a private R2 key using a short-lived presigned URL, then creates an analysis job through the Worker API. The Worker records metadata in Neon and dispatches only authorized job payloads to a separate analysis provider; it does not run heavyweight DSP itself.

Stripe requires webhook verification from the unmodified raw request body, the `Stripe-Signature` header, and a per-endpoint signing secret. The webhook should return a successful response quickly and defer longer non-critical processing. Source: https://docs.stripe.com/webhooks

Resend requires at least one verified domain before it sends email using that domain. Resend recommends purpose-specific subdomains to isolate sending reputation, and supports domain settings such as TLS and DMARC-related controls. Source: https://resend.com/docs/dashboard/domains/introduction

Initial payment/email consequence: native iOS and Android subscriptions must be implemented through the appropriate platform billing path; a Worker-owned entitlement service reconciles store and Stripe-web events after signature verification. Stripe live secrets, webhook secrets, Resend keys, and sender-domain configuration remain server-only. Resend is used for transactional lifecycle mail such as account, analysis, and billing-status messages after its sender domain is verified.
