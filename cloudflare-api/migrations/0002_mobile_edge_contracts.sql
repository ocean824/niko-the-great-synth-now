-- Apply after the inherited Synth Now core PostgreSQL schema.
-- Neon target: PostgreSQL with pgvector, pgcrypto, citext, and pg_trgm enabled.

CREATE TABLE IF NOT EXISTS user_identity_mappings (
  provider_subject text PRIMARY KEY,
  user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  issuer text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audio_upload_intents (
  id uuid PRIMARY KEY,
  owner_user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  object_key text NOT NULL UNIQUE,
  filename text NOT NULL,
  declared_mime_type text NOT NULL,
  declared_size_bytes bigint,
  input_type text NOT NULL CHECK (input_type IN ('mix', 'stem')),
  status text NOT NULL CHECK (status IN ('awaiting_upload', 'uploaded', 'expired', 'cancelled')) DEFAULT 'awaiting_upload',
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS audio_upload_intents_owner_status_idx ON audio_upload_intents(owner_user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS audio_upload_intents_expiry_idx ON audio_upload_intents(expires_at) WHERE status = 'awaiting_upload';

CREATE TABLE IF NOT EXISTS entitlement_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider text NOT NULL CHECK (provider IN ('apple', 'google', 'stripe_web', 'manual')),
  external_customer_id text,
  external_subscription_id text,
  product_id text NOT NULL,
  status text NOT NULL CHECK (status IN ('trialing', 'active', 'past_due', 'cancelled', 'expired', 'revoked')),
  starts_at timestamptz,
  ends_at timestamptz,
  source_event_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_subscription_id)
);
CREATE INDEX IF NOT EXISTS entitlement_records_user_active_idx ON entitlement_records(user_id, status, ends_at DESC);

CREATE TABLE IF NOT EXISTS provider_event_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,
  external_event_id text NOT NULL,
  event_type text NOT NULL,
  payload_sha256 char(64) NOT NULL,
  processed_at timestamptz NOT NULL DEFAULT now(),
  outcome text NOT NULL,
  UNIQUE (provider, external_event_id)
);

CREATE TABLE IF NOT EXISTS email_delivery_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  resend_message_id text UNIQUE,
  template_key text NOT NULL,
  recipient_reference text NOT NULL,
  trigger_reference text,
  delivery_state text NOT NULL DEFAULT 'accepted',
  created_at timestamptz NOT NULL DEFAULT now()
);
