# Dish Constraints Policy (Milestone 3)

## Extraction model

`dish_constraints` are extracted deterministically from existing menu-derived artifacts:

1. `ingredient` features from `dish_features_cache.json` (primary trusted source).
2. Existing deterministic `hard_flags` from stage-A menu processing (secondary source).
3. Dish name lexical markers (supporting fallback evidence only).

No LLM is used. No inferred ingredients are invented outside deterministic dictionaries/rules.

## Trusted source fields

- Primary: explicit composition-derived ingredient keys (`dish.ingredient`).
- Secondary: deterministic menu hard flags (`dish.hard_flags`).
- Supporting text: dish name markers for explicit conflict hints.

If ingredient evidence is missing for relevant safety keys, constraints are marked unresolved and `review_required=true`.

## Supported hard flags/conflicts

Allergen/intolerance flags:

- `gluten`
- `lactose`
- `nuts`
- `peanut`
- `egg`
- `soy`
- `fish_seafood`

Ingredient exclude flags:

- `mushroom`
- `onion`
- `pork`
- `offal`
- `spicy`

Dietary conflicts:

- `vegetarian_conflict`
- `vegan_conflict`
- `no_pork_conflict`
- `halal_like_conflict`

## Fail-closed policy

In questionnaire-only mode, hard filter runs before any scoring:

- explicit hard conflict -> dish is blocked
- unresolved relevant hard key or low parse confidence -> dish is blocked
- `review_required=true` for relevant hard constraint -> dish is blocked

No relevant unknown safety status silently passes.

## Unknown handling

- Unknown/insufficient evidence is represented via `unresolved_constraint_keys`.
- For relevant user hard constraints, unresolved keys produce `blocked_reason_type=unresolved`.
- `review_required` also blocks relevant dishes.

## Halal-like limitation

`halal_like_conflict` is intentionally limited to explicit ingredient-level conflicts:

- pork
- explicit forbidden offal
- explicit alcohol-in-sauce/name markers

The system does not infer halal certification from generic menu text.
