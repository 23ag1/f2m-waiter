# Admin ↔ Recommendation Engine Contours

Date: 2026-06-13

## Status

Contour documented. Full implementation is blocked until product finalizes admin TZ.

## Contour A: Menu Tag Management

Admin edits dish tags from the closed F2M reference only.

Implemented foundation:

- `recommendation_settings.json.manual_tag_overrides` stores admin add/remove patches;
- patches are applied over AI tags before constraints and scoring;
- effective tags are used by both CVP recommendation scoring and questionnaire constraints;
- invalid non-taxonomy tags are ignored by the runtime validator.

Remaining UI/API DoD:

- tags can be viewed by dish;
- only closed taxonomy keys can be selected;
- RU labels are shown in UI;
- changes write a reviewable patch/audit trail;
- no new runtime tags are invented.

## Contour C: Runtime Recommendation Controls

Implemented foundation:

- POS stop-list via `stop_list_dish_ids`: excluded from recommendations, still available for general menu rendering;
- bounded dish priority via `priority_dish_ids`;
- bounded ingredient priority via `priority_ingredients` and normalized aliases such as `курица` / `chicken`;
- system hard rules and CVP hard constraints run before business boosts;
- alcohol is excluded unless settings or request context explicitly allow/request it.

Remaining product/admin DoD:

- persistence/edit API for settings;
- publish/version/rollback workflow;
- UI preview of effective tags and ranking impact;
- audit trail with editor, timestamp, and reason.

## Contour B: Guest CVP Viewer

Admin can view guest CVP, not recommendation internals.

DoD for implementation:

- show `cvp_profile.hard_constraints`;
- show explicit, long-term, and short-term preferences;
- show `human_readable_description`;
- show profile version and source metadata;
- do not expose pilot raw data by default.

## Product-Blocked Rules

These are intentionally not implemented in this sprint:

- unlimited admin priority boosts;
- margin/marginality boosts without agreed POS data coverage;
- final "fill empty slots" behavior.
- set, upsell, and modifier optimization rules.

## Constraints For Future Implementation

- Admin priorities must affect recommendation engine ranking, not CVP.
- Ingredient priority must use the normalized ingredient dictionary.
- Priority/boost limits must be bounded and auditable.
- Backend order remains authoritative for frontend rendering.
