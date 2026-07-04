# ADR-0006 — Recommendation engine, tag quality, and output state contracts

Date: 2026-06-13

## Status

Accepted for MVP sprint implementation.

## Context

After separating CVP, the remaining sprint work requires the recommendation engine to consume CVP explicitly, expose honest empty/partial states, keep frontend ordering deterministic, localize tags for UI, and prevent explanations from making unsupported claims about dishes.

## Decision

- Introduce `f2m_engine.pipelines.recommendation_engine.rank_dishes_for_cvp` as the public order-history recommendation contract.
- Keep legacy deterministic scoring helpers during the split, but route `score_dishes_for_user` through CVP.
- Add `recommendation_state.json` with `ok | partial | empty`.
- Add `rank`, `rank_position`, and `frontend_order_contract = "backend_order"` to scored rows.
- Introduce `app.domain.tag_localization` for RU labels over closed taxonomy keys.
- Introduce `f2m_engine.pipelines.tag_audit.audit_menu_tags` and CLI command `audit-tags`.
- Introduce `app.domain.explanation_guard` to drop unsupported display facts.

## Consequences

- The recommendation engine no longer owns profile format; it consumes CVP.
- Frontend can rely on backend order and explicit empty/partial state.
- UI labels are centralized and auditable.
- Comments/display tags are grounded in dish data.
- Admin implementation remains blocked on product TZ, but its contours are documented.
- No runtime LLM is introduced.
- No taxonomy keys are invented.

## Verification

```bat
python -m pytest --basetemp D:\f2m\.pytest_tmp tests
```
