# ADR-0007: Questionnaire Config As Data

## Status

Accepted.

## Context

The global Food2Mood admin panel needs a scenario/questionnaire editor where internal users can edit questions, answer options, visit scenarios, publish changes without a deploy, keep versions, and roll back.

The existing X5/Perek questionnaire options were served from code-level constants or from the broader `recommendation_settings.json` contour. That is enough for a static MVP, but it does not give the admin panel a clean draft/published lifecycle.

## Decision

Introduce `questionnaire_config.json` as a separate configuration document in the derived data directory.

The config stores:

- `draft`: editable questionnaire payload;
- `versions`: immutable published payloads by version id;
- `published_version`: currently active version for runtime clients;
- `audit_log`: basic actor/reason trail for draft updates, publish, and rollback.

The first API slice is exposed under `/api/v1/global-admin/questionnaire/*`:

- read full config, draft, and published payload;
- update draft;
- preview draft or request payload by step id;
- publish draft as a new version;
- roll back to a previous published version.

`/api/v1/rec_x5/food_options` now reads the published questionnaire config first and falls back to legacy `recommendation_settings.json`, then to the hardcoded options.

## Consequences

- Frontend/admin can build the scenario editor against stable endpoints before a database migration exists.
- Runtime users only see published config; draft changes are isolated until `publish`.
- No runtime LLM calls are added.
- Tags referenced by the default config stay inside the existing questionnaire/taxonomy vocabulary.
- Postgres storage can replace the file repository later without changing the public API shape.
