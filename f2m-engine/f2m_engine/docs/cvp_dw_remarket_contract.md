# CVP DW / Remarket Export Contract

Date: 2026-06-13

## Purpose

DW/Remarket should consume CVP as a profile payload, not recommendation scores. This sprint prepares the contract only; integration is out of scope.

## Export Row

`app.domain.cvp.build_cvp_dw_export_row(cvp_profile)` returns:

```json
{
  "user_id": 123,
  "cvp_version": "cvp_v1",
  "hard_constraints": ["peanut"],
  "explicit_positive_top": [],
  "explicit_negative_top": [],
  "long_term_top": [],
  "short_term_top": [],
  "human_readable_description": "ЦВП пользователя 123. ...",
  "payload_json": {"cvp_version": "cvp_v1"}
}
```

## Consumer Guidance

- Use `payload_json` as the full lossless profile.
- Use top fields for dashboards, previews, and segment builders.
- Do not infer safety from soft preferences.
- Do not use recommendation candidates as the source of truth for guest profile.

## Out Of Scope

- DW connector implementation.
- Remarket UI.
- Consent and cross-venue transfer policy.
