# ADR-0005 — CVP profile layer contract

Date: 2026-06-13

## Status

Accepted for MVP sprint implementation.

## Context

Food2Mood needs to separate the digital taste profile (CVP) from the recommendation engine. Before this ADR, the serving cache already contained profile-like data (`hard_constraints`, `explicit`, `long_term`, `short_term`), but there was no explicit CVP contract and no deterministic human-readable description for admin/DW handoff.

The sprint goal is to let the recommendation engine consume CVP without owning profile semantics.

## Decision

- Introduce `app.domain.cvp` as the standalone CVP builder.
- Add `cvp_profile` to `user_profiles_cache.json`.
- Keep legacy cache fields in place for backward compatibility with existing scoring code.
- Define `cvp_profile` as:
  - `hard_constraints`
  - `soft_preferences.explicit`
  - `soft_preferences.long_term`
  - `soft_preferences.short_term`
  - full `feature_layers`
  - `history_aggregates`
  - deterministic `human_readable_description`
- Enrich `GET /profiles/{user_id}` on read if an old cache row does not yet contain `cvp_profile`.

## Consequences

- CVP is now a profile-layer contract, not a side effect of recommendation scoring.
- Existing recommendation code can keep reading `explicit`, `long_term`, and `short_term`.
- Admin/DW/Remarket can target `cvp_profile` without depending on score outputs.
- No runtime LLM is introduced.
- No taxonomy keys are invented or remapped by the CVP layer.

## Verification

```bat
python -m pytest tests\test_cvp_profile.py tests\test_profile_rebuild.py
```
