export interface Env {
  APP_ENV: "development" | "staging" | "production";
  HYPERDRIVE: Hyperdrive;
  R2_UPLOADS: R2Bucket;
  R2_APPROVED_ASSETS: R2Bucket;
  ANALYSIS_QUEUE: Queue;
  R2_UPLOADS_BUCKET: string;
  R2_PRESIGN_ACCOUNT_ID: string;
  R2_ACCESS_KEY_ID: string;
  R2_SECRET_ACCESS_KEY: string;
  OIDC_ISSUER: string;
  OIDC_AUDIENCE: string;
  OIDC_JWKS_URL: string;
  STRIPE_SECRET_KEY: string;
  STRIPE_WEBHOOK_SECRET: string;
  STRIPE_WEB_PRICE_ID: string;
  RESEND_API_KEY: string;
  RESEND_FROM_EMAIL: string;
  INTERNAL_EMAIL_TOKEN: string;
}

export type AuthenticatedUser = {
  id: string;
  subject: string;
  email: string;
  role: string;
};
