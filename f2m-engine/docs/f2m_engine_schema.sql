-- F2M Engine schema — runs idempotently (IF NOT EXISTS everywhere)
-- Apply: docker exec f2m_postgres psql -U f2m -d f2m_platform -f /tmp/f2m_engine_schema.sql

CREATE TABLE IF NOT EXISTS users (
    user_id   bigint PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dishes (
    dish_id   bigint PRIMARY KEY,
    dish_name text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS questionnaire_submissions (
    submission_id      bigserial PRIMARY KEY,
    user_id            bigint NOT NULL,
    questionnaire_type text NOT NULL DEFAULT 'manual',
    source_system      text NOT NULL DEFAULT 'local',
    raw_answers_json   jsonb NOT NULL DEFAULT '{}',
    extracted_json     jsonb NOT NULL DEFAULT '{}',
    extractor_version  text NOT NULL DEFAULT 'runtime_v1',
    submitted_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_constraints (
    user_id         bigint NOT NULL,
    constraint_key  text NOT NULL,
    constraint_kind text NOT NULL DEFAULT 'other',
    scope           text NOT NULL DEFAULT 'hard',
    source          text NOT NULL DEFAULT 'api',
    reason_text     text,
    evidence_json   jsonb,
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, constraint_key)
);

CREATE TABLE IF NOT EXISTS user_feature_values (
    user_id         bigint NOT NULL,
    profile_layer   text NOT NULL,
    axis            text NOT NULL,
    feature_key     text NOT NULL,
    weight          double precision NOT NULL,
    source          text NOT NULL DEFAULT 'api',
    confidence      double precision,
    feature_version text NOT NULL DEFAULT 'runtime_v1',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, profile_layer, axis, feature_key)
);

CREATE TABLE IF NOT EXISTS events (
    event_pk      bigserial PRIMARY KEY,
    source_system text NOT NULL,
    event_uuid    text NOT NULL,
    user_id       bigint NOT NULL,
    event_type    text NOT NULL,
    object_type   text NOT NULL DEFAULT 'dish',
    object_id     text,
    payload_json  jsonb NOT NULL DEFAULT '{}',
    occurred_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_system, event_uuid)
);

CREATE TABLE IF NOT EXISTS event_items (
    event_pk       bigint NOT NULL REFERENCES events(event_pk),
    line_no        int NOT NULL,
    dish_name      text NOT NULL DEFAULT '',
    qty            int NOT NULL DEFAULT 1,
    modifiers_json jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (event_pk, line_no)
);

CREATE TABLE IF NOT EXISTS dish_feature_values (
    dish_id     text NOT NULL,
    axis        text NOT NULL,
    feature_key text NOT NULL,
    value_num   double precision,
    source      text,
    meta        jsonb,
    PRIMARY KEY (dish_id, axis, feature_key)
);

CREATE TABLE IF NOT EXISTS dish_features_cache (
    dish_id         text PRIMARY KEY,
    cache_json      jsonb NOT NULL DEFAULT '{}',
    feature_version text NOT NULL DEFAULT 'runtime_v1'
);

CREATE TABLE IF NOT EXISTS user_profiles_cache (
    user_id         bigint PRIMARY KEY,
    cache_json      jsonb NOT NULL DEFAULT '{}',
    profile_version text NOT NULL DEFAULT 'runtime_v1'
);

CREATE TABLE IF NOT EXISTS recommendation_requests (
    recommendation_request_id text PRIMARY KEY,
    user_id                   bigint NOT NULL,
    occurred_at               timestamptz NOT NULL DEFAULT now(),
    context_snapshot          jsonb NOT NULL DEFAULT '{}',
    time_is_synthetic         boolean NOT NULL DEFAULT false,
    user_profile_snapshot_id  text,
    profile_version           text,
    shown_candidates_count    int NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recommendation_candidates (
    candidate_id              bigserial PRIMARY KEY,
    recommendation_request_id text NOT NULL,
    user_id                   bigint NOT NULL,
    occurred_at               timestamptz NOT NULL DEFAULT now(),
    context_snapshot          jsonb NOT NULL DEFAULT '{}',
    dish_id                   text NOT NULL,
    rank_position             int NOT NULL DEFAULT 0,
    deterministic_score       double precision,
    score_breakdown_snapshot  jsonb,
    hard_filter_excluded      boolean NOT NULL DEFAULT false,
    hard_filter_reasons       jsonb,
    compliance_unknown        boolean NOT NULL DEFAULT false,
    dish_feature_snapshot_id  text,
    dish_feature_version      text NOT NULL DEFAULT 'runtime_v1',
    was_shown                 boolean NOT NULL DEFAULT true,
    CONSTRAINT rec_candidates_req_dish_uniq UNIQUE (recommendation_request_id, dish_id)
);

CREATE TABLE IF NOT EXISTS recommendation_outcomes (
    outcome_id                bigserial PRIMARY KEY,
    recommendation_request_id text NOT NULL,
    dish_id                   text NOT NULL,
    outcome_type              text NOT NULL,
    occurred_at               timestamptz NOT NULL DEFAULT now(),
    time_to_action_ms         int,
    created_at                timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ranking_dataset_rows (
    row_id                    bigserial PRIMARY KEY,
    recommendation_request_id text NOT NULL,
    rank_position             int NOT NULL DEFAULT 0,
    dish_id                   text NOT NULL,
    winner_dish_id            text,
    label                     int NOT NULL DEFAULT 0,
    score                     double precision,
    features_json             jsonb,
    created_at                timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ranking_rows_req_dish_uniq UNIQUE (recommendation_request_id, dish_id)
);
