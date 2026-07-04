# CVP Profile Contract

Date: 2026-06-13

## Purpose

CVP (`cvp_profile`) is the standalone digital taste profile layer for a guest. It is owned by the profile pipeline and can be reused by recommendation, DW/Remarket, admin views, and future products without mixing in dish ranking logic.

The recommendation engine consumes CVP, but does not own its format.

## Contract: `cvp_profile`

```json
{
  "cvp_version": "cvp_v1",
  "user_id": 123,
  "hard_constraints": [
    {
      "constraint_key": "peanut",
      "scope": "hard",
      "source": "questionnaire",
      "reason_text": "allergy",
      "confidence": 0.9
    }
  ],
  "soft_preferences": {
    "explicit": {
      "positive": [{"axis": "taste", "feature_key": "spicy", "weight": 0.7}],
      "negative": [{"axis": "ingredient", "feature_key": "onion", "weight": -0.6}]
    },
    "long_term": {
      "positive": [{"axis": "cuisine", "feature_key": "asian", "weight": 0.4}],
      "negative": []
    },
    "short_term": {
      "positive": [{"axis": "context", "feature_key": "lunch", "weight": 0.5}],
      "negative": []
    }
  },
  "feature_layers": {
    "explicit": {"taste": {"spicy": 0.7}},
    "long_term": {"cuisine": {"asian": 0.4}},
    "short_term": {"context": {"lunch": 0.5}}
  },
  "history_aggregates": {
    "long_term": {"cuisine": {"asian": 0.4}},
    "short_term": {"context": {"lunch": 0.5}},
    "top_long_term": [{"axis": "cuisine", "feature_key": "asian", "weight": 0.4}],
    "top_short_term": [{"axis": "context", "feature_key": "lunch", "weight": 0.5}]
  },
  "human_readable_description": "ЦВП пользователя 123. ...",
  "meta": {
    "feature_version": "runtime_v1",
    "cvp_schema": "cvp_v1",
    "cvp_source": "user_profiles_cache"
  }
}
```

## Invariants

- No runtime LLM is used to create the human-readable description.
- `hard_constraints` are kept separate from `soft_preferences`; they are not scored as dislikes.
- Feature keys come from existing profile/cache rows built over the closed taxonomy.
- `cvp_profile` is added to `user_profiles_cache.json` while legacy fields remain for backward compatibility.
- `feature_layers` is the full machine-readable profile used by the recommendation engine.
- `soft_preferences.*.positive/negative` are compact top-lists for admin/DW previews.

## Current Integration Points

- `app.domain.cvp.build_cvp_profile` builds the standalone contract.
- `app.domain.cvp.scoring_profile_from_cvp` adapts CVP into the current deterministic scorer shape.
- `app.domain.cvp.build_cvp_dw_export_row` prepares a DW/Remarket export row.
- `f2m_engine.pipelines.profile_rebuild.rebuild_profiles` writes `cvp_profile` into the serving cache.
- `f2m_engine.pipelines.profile_rebuild.show_profile` prints `cvp_version` and `human_readable_description`.
- `GET /profiles/{user_id}` returns `cvp_profile`; old caches are enriched on read.

## Out Of Scope

- Recommendation ranking changes.
- DW/Remarket integration.
- Admin UI implementation.
- Localization of all tag labels; this belongs to the tag localization task.
