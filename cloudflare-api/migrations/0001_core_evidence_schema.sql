-- Synth Now core PostgreSQL schema
-- Scope: canonical music identity, gear/VST/presets, evidence claims,
-- official sources, usage projections, and private audio-inference records.
-- Treat this as a migration starter; split into numbered migrations in production.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE entity_type AS ENUM (
  'artist', 'person', 'manufacturer', 'gear_product', 'product_variant',
  'software_product', 'software_version', 'preset_bank', 'preset',
  'musical_work', 'recording', 'recording_version', 'release', 'technique',
  'sonic_tag', 'sample_library'
);

CREATE TYPE recording_version_type AS ENUM (
  'original', 'remaster', 'radio_edit', 'extended_mix', 'remix', 'live',
  'cover', 'rerecording', 'instrumental', 'acapella', 'sped_up', 'slowed', 'other'
);

CREATE TYPE product_state AS ENUM ('current', 'discontinued', 'legacy', 'reissue', 'unknown');
CREATE TYPE evidence_status AS ENUM (
  'verified', 'community_corroborated', 'audio_inference',
  'recreation_recipe', 'disputed', 'unverified_lead'
);
CREATE TYPE review_state AS ENUM ('draft', 'submitted', 'needs_changes', 'approved', 'published', 'rejected', 'archived');
CREATE TYPE claim_type AS ENUM (
  'instrument_use', 'gear_use', 'software_use', 'preset_use', 'sample_use',
  'personnel_credit', 'production_technique', 'mix_technique', 'studio_context',
  'product_history', 'official_connection', 'other'
);
CREATE TYPE scope_kind AS ENUM (
  'recording_version', 'song_section', 'session', 'album', 'tour',
  'studio_ownership', 'general_context'
);
CREATE TYPE connection_kind AS ENUM (
  'track_specific_use', 'recording_credit', 'album_session_context',
  'touring_rig', 'artist_ownership', 'manufacturer_feature',
  'audio_similarity', 'recreation_recommendation'
);
CREATE TYPE source_status AS ENUM (
  'official', 'official_archive', 'manufacturer_feature',
  'independent_source', 'community_source'
);
CREATE TYPE history_event_type AS ENUM (
  'announced', 'released', 'revision', 'firmware_update', 'software_release',
  'discontinued', 'reissued', 'renamed', 'technical_change', 'cultural_context', 'other'
);
CREATE TYPE analysis_status AS ENUM ('queued', 'running', 'completed', 'failed', 'expired');
CREATE TYPE confidence_band AS ENUM ('high', 'moderate', 'low', 'insufficient');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  display_name text NOT NULL,
  role text NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'contributor', 'reviewer', 'editor', 'admin', 'verified_creator')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Stable identity anchor across domains. Do not expose internal IDs as meaning.
CREATE TABLE entity_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type entity_type NOT NULL,
  canonical_slug citext NOT NULL,
  display_name text NOT NULL,
  normalized_name text NOT NULL,
  lifecycle_state text NOT NULL DEFAULT 'active' CHECK (lifecycle_state IN ('active', 'merged', 'archived', 'draft')),
  merged_into_entity_id uuid REFERENCES entity_registry(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (entity_type, canonical_slug)
);
CREATE INDEX entity_registry_name_trgm_idx ON entity_registry USING gin (normalized_name gin_trgm_ops);

CREATE TABLE manufacturers (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  official_domain citext,
  country_code char(2),
  founded_year smallint,
  official_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE entity_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id uuid NOT NULL REFERENCES entity_registry(id) ON DELETE CASCADE,
  alias text NOT NULL,
  normalized_alias text NOT NULL,
  locale text,
  alias_type text NOT NULL DEFAULT 'alternate' CHECK (alias_type IN ('alternate', 'abbreviation', 'misspelling', 'marketing', 'legacy', 'translation')),
  UNIQUE (entity_id, normalized_alias)
);
CREATE INDEX entity_aliases_trgm_idx ON entity_aliases USING gin (normalized_alias gin_trgm_ops);

CREATE TABLE gear_products (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  manufacturer_entity_id uuid REFERENCES manufacturers(entity_id),
  product_family text,
  category text NOT NULL,
  subcategory text,
  state product_state NOT NULL DEFAULT 'unknown',
  launch_date date,
  discontinued_date date,
  description text,
  specification_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX gear_products_category_idx ON gear_products(category, subcategory, state);

CREATE TABLE product_variants (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  gear_product_entity_id uuid NOT NULL REFERENCES gear_products(entity_id) ON DELETE CASCADE,
  launch_date date,
  discontinued_date date,
  serial_range text,
  technical_differences text,
  specification_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX product_variants_product_idx ON product_variants(gear_product_entity_id, launch_date);

CREATE TABLE software_products (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  developer_entity_id uuid REFERENCES manufacturers(entity_id),
  category text NOT NULL,
  plugin_formats text[] NOT NULL DEFAULT '{}',
  state product_state NOT NULL DEFAULT 'unknown',
  official_url text,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE software_versions (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  software_product_entity_id uuid NOT NULL REFERENCES software_products(entity_id) ON DELETE CASCADE,
  version_label text NOT NULL,
  release_date date,
  support_end_date date,
  compatibility_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (software_product_entity_id, version_label)
);

CREATE TABLE preset_banks (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  parent_entity_id uuid NOT NULL REFERENCES entity_registry(id),
  publisher_entity_id uuid REFERENCES manufacturers(entity_id),
  bank_version text,
  origin text NOT NULL CHECK (origin IN ('factory', 'third_party', 'artist', 'user', 'unknown')),
  license_url text,
  released_on date,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX preset_banks_parent_idx ON preset_banks(parent_entity_id, bank_version);

CREATE TABLE presets (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  preset_bank_entity_id uuid NOT NULL REFERENCES preset_banks(entity_id) ON DELETE CASCADE,
  preset_version text NOT NULL DEFAULT '1',
  normalized_preset_name text NOT NULL,
  author_entity_id uuid REFERENCES entity_registry(id),
  parameter_snapshot_hash text,
  parameter_json jsonb,
  licensing_state text NOT NULL DEFAULT 'unknown',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (preset_bank_entity_id, preset_version, normalized_preset_name)
);
CREATE INDEX presets_bank_name_idx ON presets(preset_bank_entity_id, normalized_preset_name);

-- Retain audio reference renders only for licensed/authorized preset material.
CREATE TABLE preset_reference_renders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  preset_entity_id uuid NOT NULL REFERENCES presets(entity_id) ON DELETE CASCADE,
  render_protocol_version text NOT NULL,
  midi_fixture_id text NOT NULL,
  sample_rate integer NOT NULL CHECK (sample_rate > 0),
  audio_uri text NOT NULL,
  audio_sha256 char(64) NOT NULL,
  embedding vector(1024),
  embedding_model_version text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (preset_entity_id, render_protocol_version, midi_fixture_id)
);
CREATE INDEX preset_reference_renders_embedding_idx
  ON preset_reference_renders USING hnsw (embedding vector_cosine_ops)
  WHERE embedding IS NOT NULL;

CREATE TABLE musical_works (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  iswc text UNIQUE,
  language_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE recordings (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  musical_work_entity_id uuid REFERENCES musical_works(entity_id),
  primary_artist_entity_id uuid REFERENCES entity_registry(id),
  canonical_musicbrainz_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE recording_versions (
  entity_id uuid PRIMARY KEY REFERENCES entity_registry(id) ON DELETE CASCADE,
  recording_entity_id uuid NOT NULL REFERENCES recordings(entity_id) ON DELETE CASCADE,
  parent_recording_version_entity_id uuid REFERENCES recording_versions(entity_id),
  version_type recording_version_type NOT NULL,
  version_label text,
  isrc text,
  duration_ms integer CHECK (duration_ms > 0),
  release_date date,
  fingerprint_provider text,
  fingerprint_provider_reference text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (recording_entity_id, version_type, version_label, isrc)
);
CREATE INDEX recording_versions_recording_idx ON recording_versions(recording_entity_id, release_date DESC);
CREATE INDEX recording_versions_isrc_idx ON recording_versions(isrc) WHERE isrc IS NOT NULL;

CREATE TABLE source_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_status source_status NOT NULL,
  title text NOT NULL,
  canonical_url text NOT NULL,
  publisher_or_owner text,
  author_name text,
  published_on date,
  captured_at timestamptz NOT NULL DEFAULT now(),
  verified_domain citext,
  rights_note text,
  content_hash char(64),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (canonical_url)
);

CREATE TABLE official_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_entity_id uuid NOT NULL REFERENCES entity_registry(id) ON DELETE CASCADE,
  source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
  source_role text NOT NULL CHECK (source_role IN ('product_page', 'manual', 'support', 'archive', 'artist_feature', 'firmware', 'developer_documentation')),
  support_summary text NOT NULL,
  link_health text NOT NULL DEFAULT 'unchecked' CHECK (link_health IN ('unchecked', 'healthy', 'redirected', 'broken', 'needs_review')),
  last_checked_at timestamptz,
  review_state review_state NOT NULL DEFAULT 'submitted',
  created_by_user_id uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (subject_entity_id, source_document_id, source_role)
);
CREATE INDEX official_sources_subject_idx ON official_sources(subject_entity_id, review_state);

CREATE TABLE gear_history_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  gear_product_entity_id uuid NOT NULL REFERENCES gear_products(entity_id) ON DELETE CASCADE,
  product_variant_entity_id uuid REFERENCES product_variants(entity_id),
  event_type history_event_type NOT NULL,
  event_start_date date,
  event_end_date date,
  date_precision text NOT NULL DEFAULT 'unknown' CHECK (date_precision IN ('day', 'month', 'year', 'approximate', 'unknown')),
  title text NOT NULL,
  description text NOT NULL,
  evidence_status evidence_status NOT NULL DEFAULT 'unverified_lead',
  review_state review_state NOT NULL DEFAULT 'submitted',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (event_end_date IS NULL OR event_start_date IS NULL OR event_end_date >= event_start_date)
);
CREATE INDEX gear_history_events_timeline_idx ON gear_history_events(gear_product_entity_id, event_start_date NULLS LAST);

CREATE TABLE production_claims (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  recording_version_entity_id uuid NOT NULL REFERENCES recording_versions(entity_id) ON DELETE CASCADE,
  claim_type claim_type NOT NULL,
  target_entity_id uuid REFERENCES entity_registry(id),
  target_text text,
  role_label text,
  evidence_status evidence_status NOT NULL DEFAULT 'unverified_lead',
  confidence numeric(4,3) CHECK (confidence >= 0 AND confidence <= 1),
  review_state review_state NOT NULL DEFAULT 'submitted',
  submitted_by_user_id uuid REFERENCES users(id),
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (target_entity_id IS NOT NULL OR target_text IS NOT NULL)
);
CREATE INDEX production_claims_version_idx ON production_claims(recording_version_entity_id, claim_type, evidence_status, review_state);
CREATE INDEX production_claims_target_idx ON production_claims(target_entity_id, evidence_status, review_state) WHERE target_entity_id IS NOT NULL;

CREATE TABLE claim_scopes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  production_claim_id uuid NOT NULL REFERENCES production_claims(id) ON DELETE CASCADE,
  scope_kind scope_kind NOT NULL,
  start_ms integer CHECK (start_ms IS NULL OR start_ms >= 0),
  end_ms integer CHECK (end_ms IS NULL OR end_ms >= 0),
  song_section text,
  scope_note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_ms IS NULL OR start_ms IS NULL OR end_ms >= start_ms)
);
CREATE INDEX claim_scopes_timeline_idx ON claim_scopes(production_claim_id, start_ms, end_ms);

CREATE TABLE claim_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  production_claim_id uuid NOT NULL REFERENCES production_claims(id) ON DELETE CASCADE,
  source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE RESTRICT,
  support_summary text NOT NULL,
  source_start_ms integer CHECK (source_start_ms IS NULL OR source_start_ms >= 0),
  source_end_ms integer CHECK (source_end_ms IS NULL OR source_end_ms >= 0),
  source_location text,
  source_quality smallint NOT NULL DEFAULT 3 CHECK (source_quality BETWEEN 1 AND 5),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (source_end_ms IS NULL OR source_start_ms IS NULL OR source_end_ms >= source_start_ms),
  UNIQUE (production_claim_id, source_document_id, source_location)
);

CREATE TABLE claim_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  production_claim_id uuid NOT NULL REFERENCES production_claims(id) ON DELETE CASCADE,
  reviewer_user_id uuid NOT NULL REFERENCES users(id),
  decision review_state NOT NULL CHECK (decision IN ('needs_changes', 'approved', 'published', 'rejected', 'archived')),
  decision_note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX claim_reviews_claim_idx ON claim_reviews(production_claim_id, created_at DESC);

CREATE TABLE claim_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  production_claim_id uuid NOT NULL REFERENCES production_claims(id) ON DELETE CASCADE,
  changed_by_user_id uuid REFERENCES users(id),
  change_reason text NOT NULL,
  snapshot jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Query-optimized, evidence-backed graph projection. Populate transactionally only after claim review.
CREATE TABLE usage_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  production_claim_id uuid NOT NULL UNIQUE REFERENCES production_claims(id) ON DELETE CASCADE,
  target_entity_id uuid NOT NULL REFERENCES entity_registry(id),
  recording_version_entity_id uuid NOT NULL REFERENCES recording_versions(entity_id) ON DELETE CASCADE,
  person_entity_id uuid REFERENCES entity_registry(id),
  connection_kind connection_kind NOT NULL,
  role_label text,
  evidence_status evidence_status NOT NULL,
  published_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX usage_edges_documented_idx
  ON usage_edges(target_entity_id, recording_version_entity_id, published_at DESC)
  WHERE connection_kind IN ('track_specific_use', 'recording_credit');
CREATE INDEX usage_edges_context_idx ON usage_edges(target_entity_id, connection_kind, published_at DESC);

-- Private, permissioned analysis domain. It has no direct write path to production_claims.
CREATE TABLE audio_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id uuid NOT NULL REFERENCES users(id),
  storage_uri text NOT NULL,
  content_sha256 char(64) NOT NULL,
  duration_ms integer CHECK (duration_ms > 0),
  consent_version text NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('microphone', 'upload', 'rights_cleared_reference')),
  retention_expires_at timestamptz NOT NULL,
  public_access boolean NOT NULL DEFAULT false CHECK (public_access = false),
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audio_assets_retention_idx ON audio_assets(retention_expires_at) WHERE deleted_at IS NULL;

CREATE TABLE audio_analysis_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audio_asset_id uuid NOT NULL REFERENCES audio_assets(id) ON DELETE CASCADE,
  candidate_recording_version_entity_id uuid REFERENCES recording_versions(entity_id),
  model_bundle_version text NOT NULL,
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
  status analysis_status NOT NULL DEFAULT 'queued',
  started_at timestamptz,
  completed_at timestamptz,
  retention_expires_at timestamptz NOT NULL,
  failure_reason text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audio_analysis_runs_asset_idx ON audio_analysis_runs(audio_asset_id, created_at DESC);

CREATE TABLE audio_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audio_analysis_run_id uuid NOT NULL REFERENCES audio_analysis_runs(id) ON DELETE CASCADE,
  start_ms integer NOT NULL CHECK (start_ms >= 0),
  end_ms integer NOT NULL CHECK (end_ms >= start_ms),
  observation_type text NOT NULL CHECK (observation_type IN ('music_activity', 'section', 'instrument_family', 'sonic_attribute', 'source_separation', 'embedding', 'other')),
  target_label text NOT NULL,
  target_entity_id uuid REFERENCES entity_registry(id),
  probability numeric(5,4) NOT NULL CHECK (probability >= 0 AND probability <= 1),
  confidence_band confidence_band NOT NULL,
  alternative_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  explanation text,
  model_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audio_observations_timeline_idx ON audio_observations(audio_analysis_run_id, start_ms, end_ms);
CREATE INDEX audio_observations_target_idx ON audio_observations(observation_type, target_label, confidence_band);

CREATE TABLE preset_similarity_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audio_observation_id uuid NOT NULL REFERENCES audio_observations(id) ON DELETE CASCADE,
  preset_reference_render_id uuid NOT NULL REFERENCES preset_reference_renders(id) ON DELETE CASCADE,
  rank smallint NOT NULL CHECK (rank > 0),
  similarity numeric(5,4) NOT NULL CHECK (similarity >= -1 AND similarity <= 1),
  filter_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation text,
  disclaimer_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (audio_observation_id, preset_reference_render_id),
  UNIQUE (audio_observation_id, rank)
);

CREATE TABLE human_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audio_observation_id uuid REFERENCES audio_observations(id) ON DELETE CASCADE,
  preset_similarity_candidate_id uuid REFERENCES preset_similarity_candidates(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id),
  feedback_type text NOT NULL CHECK (feedback_type IN ('agree', 'disagree', 'correction', 'not_sure')),
  corrected_label text,
  notes text,
  consent_for_model_evaluation boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (audio_observation_id IS NOT NULL OR preset_similarity_candidate_id IS NOT NULL)
);

-- Guardrail recommendation: enforce in application service or a database trigger.
-- Reject an INSERT/UPDATE to production_claims with evidence_status='verified'
-- unless a reviewer/editor has published a claim_review and at least one claim_evidence row exists.
-- Reject materialization into usage_edges unless production_claims.review_state='published'.
