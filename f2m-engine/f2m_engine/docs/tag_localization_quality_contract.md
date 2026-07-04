# Tag Localization And Quality Contract

Date: 2026-06-13

## Purpose

Internal feature keys may remain English, but tags shown outside the engine must have Russian labels. Menu tag quality is checked by audit files before frontend/admin use.

## Rules

- Internal storage keeps closed taxonomy keys.
- UI/display labels use `app.domain.tag_localization.localize_tag`.
- Unknown ingredient ids may fall back to the canonical ingredient key until the ingredient dictionary gets a curated RU display name.
- Closed taxonomy axes (`taste`, `cuisine`, `format_texture`, `context`, `restriction`, `nutrition`) must have RU labels.

## Audit Command

```bat
python -m app.cli audit-tags --derived data\derived
```

Writes:

- `audit/tag_localization_audit.csv`;
- `audit/tag_anomaly_audit.csv`.
- `audit/questionable_tags_by_dish.csv` — one row per dish with a compact list of tags for analyst review.
- `audit/questionable_tag_rows.csv` — one row per questionable tag with evidence.

## Current Anomaly Checks

- `format_texture.fried` on bar-like items (`батончик`, `bar`, `granola`, etc.).
- `nutrition.low_calorie` with high kcal per portion.

## Current Questionable Tag Checks

The broader analyst-review report also flags:

- `format_texture.fried` without fried-like evidence in name/category.
- `format_texture.soup`, `salad`, `dessert` without matching name/category evidence.
- `cuisine.asian` and `cuisine.fast_food` without visible cuisine/category evidence.
- unexpected `hard_flags.peanut` when name/category has no nut marker.
- main menu items marked as `nutrition.satiety_class=snack`.

Audit findings are review inputs. The audit does not auto-patch tags.

## Anti-Hallucination Rule

Display/comment tags are kept only when supported by dish data:

- spicy requires `constraint_flags.spicy` or `taste_features.spicy >= 0.35`;
- nutrition tags require matching `nutrition_features`;
- cuisine tags require positive `cuisine_features`;
- violation tags require matching `dietary_conflicts`.

No runtime LLM is used for tag explanations.
