from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


CANONICAL_ALLERGENS = ("gluten", "lactose", "nuts", "peanut", "egg", "soy", "fish_seafood")
CANONICAL_DIETARY_RULES = ("vegetarian", "vegan", "no_pork", "halal_like")
CANONICAL_SATIETY = ("snack", "light_meal", "full_meal")
CANONICAL_FAMILIARITY = ("familiar_food", "adventurous_food")
CANONICAL_WANT_NOW = ("vegetables", "meat", "fish_seafood", "soup", "spicy", "sweet", "hot", "cold")
CANONICAL_NUTRITION = ("low_calorie", "high_protein", "no_sugar")
CANONICAL_CUISINE = ("asian", "italian", "home_style", "author_style", "georgian_caucasian", "russian_home")


class QuestionnaireNormalizationError(ValueError):
    pass


class HardConstraints(TypedDict):
    allergens: list[str]
    intolerances: list[str]
    ingredient_excludes: list[str]
    dietary_rules: list[str]
    unknown_or_needs_review: list[dict[str, str]]


class SoftPreferences(TypedDict):
    desired_content: dict[str, float]
    nutrition: dict[str, float]
    cuisine: dict[str, float]
    familiarity_novelty: dict[str, float]
    soft_negative_ingredients: dict[str, float]


class RequestContext(TypedDict):
    want_now: list[str]
    satiety: str
    session_tags: list[str]
    questionnaire_version: str


class NormalizationMeta(TypedDict):
    source_fields_used: list[str]
    unmapped_answers: list[dict[str, str]]
    profile_version: str
    normalization_warnings: list[str]


class NormalizedQuestionnaireProfile(TypedDict):
    hard_constraints: HardConstraints
    soft_preferences: SoftPreferences
    request_context: RequestContext
    normalization_meta: NormalizationMeta


@dataclass(frozen=True)
class _AnswerRecord:
    raw_field_name: str
    raw_answer_value: str
    normalized_answer_value: str


DIETARY_FORBIDDEN_CONTENT: dict[str, tuple[str, ...]] = {
    "vegetarian": ("meat", "fish_seafood", "offal", "pork"),
    "vegan": ("meat", "fish_seafood", "offal", "pork"),
    "no_pork": ("pork",),
    "halal_like": ("pork", "offal"),
}


def normalize_questionnaire(
    raw_questionnaire: dict[str, Any],
    request_context: dict[str, Any] | None = None,
    questionnaire_version: str = "v1",
    profile_version: str = "questionnaire_profile_v1",
) -> NormalizedQuestionnaireProfile:
    if not isinstance(raw_questionnaire, dict):
        raise QuestionnaireNormalizationError("raw_questionnaire must be a dict")
    if not raw_questionnaire:
        raise QuestionnaireNormalizationError("raw_questionnaire must not be empty")

    mapped_fields: set[str] = set()
    unmapped_answers: list[dict[str, str]] = []
    unknown_hard: list[dict[str, str]] = []

    hard_allergens: set[str] = set()
    hard_intolerances: set[str] = set()
    hard_ingredient_excludes: set[str] = set()
    hard_dietary_rules: set[str] = set()

    soft_desired_content: dict[str, float] = {}
    soft_nutrition: dict[str, float] = {}
    soft_cuisine: dict[str, float] = {}
    soft_familiarity: dict[str, float] = {}
    soft_negative_ingredients: dict[str, float] = {}

    request_want_now: set[str] = set()
    request_satiety = ""
    request_session_tags: set[str] = set()

    records = _collect_answer_records(raw_questionnaire=raw_questionnaire)
    context_records = _collect_answer_records(raw_questionnaire=request_context or {}, field_prefix="request_context.")

    for record in [*records, *context_records]:
        outcome = _map_record(record)
        if not outcome:
            unmapped_answers.append(
                {
                    "raw_field_name": record.raw_field_name,
                    "raw_answer_value": record.raw_answer_value,
                    "reason": "no_mapping_rule",
                }
            )
            continue
        mapped_fields.add(record.raw_field_name)
        for key in outcome.get("allergens", ()):
            hard_allergens.add(key)
        for key in outcome.get("intolerances", ()):
            hard_intolerances.add(key)
        for key in outcome.get("ingredient_excludes", ()):
            hard_ingredient_excludes.add(key)
        for key in outcome.get("dietary_rules", ()):
            hard_dietary_rules.add(key)
        for key in outcome.get("unknown_hard", ()):
            unknown_hard.append(
                {
                    "raw_field_name": record.raw_field_name,
                    "raw_answer_value": record.raw_answer_value,
                    "note": key,
                }
            )
        for key, value in outcome.get("desired_content", {}).items():
            soft_desired_content[key] = max(soft_desired_content.get(key, 0.0), float(value))
        for key, value in outcome.get("nutrition", {}).items():
            soft_nutrition[key] = max(soft_nutrition.get(key, 0.0), float(value))
        for key, value in outcome.get("cuisine", {}).items():
            soft_cuisine[key] = max(soft_cuisine.get(key, 0.0), float(value))
        for key, value in outcome.get("familiarity_novelty", {}).items():
            soft_familiarity[key] = max(soft_familiarity.get(key, 0.0), float(value))
        for key, value in outcome.get("soft_negative_ingredients", {}).items():
            soft_negative_ingredients[key] = max(soft_negative_ingredients.get(key, 0.0), float(value))
        for key in outcome.get("want_now", ()):
            request_want_now.add(key)
        satiety_value = outcome.get("satiety", "")
        if satiety_value:
            request_satiety = satiety_value
        for tag in outcome.get("session_tags", ()):
            request_session_tags.add(tag)

    soft_desired_content, soft_negative_ingredients, precedence_audit, precedence_warnings = _apply_precedence_rules(
        hard_constraints={
            "allergens": hard_allergens,
            "intolerances": hard_intolerances,
            "ingredient_excludes": hard_ingredient_excludes,
            "dietary_rules": hard_dietary_rules,
        },
        desired_content=soft_desired_content,
        soft_negative=soft_negative_ingredients,
    )

    warnings: list[str] = []
    if not mapped_fields:
        warnings.append("no_preference_fields_mapped")
    if not request_satiety:
        warnings.append("satiety_not_provided")
    warnings.extend(precedence_warnings)

    return {
        "hard_constraints": {
            "allergens": sorted(hard_allergens),
            "intolerances": sorted(hard_intolerances),
            "ingredient_excludes": sorted(hard_ingredient_excludes),
            "dietary_rules": sorted(hard_dietary_rules),
            "unknown_or_needs_review": sorted(
                unknown_hard,
                key=lambda row: (row["raw_field_name"], row["raw_answer_value"], row["note"]),
            ),
        },
        "soft_preferences": {
            "desired_content": _sorted_dict(soft_desired_content),
            "nutrition": _sorted_dict(soft_nutrition),
            "cuisine": _sorted_dict(soft_cuisine),
            "familiarity_novelty": _sorted_dict(soft_familiarity),
            "soft_negative_ingredients": _sorted_dict(soft_negative_ingredients),
        },
        "request_context": {
            "want_now": sorted(request_want_now),
            "satiety": request_satiety,
            "session_tags": sorted(request_session_tags),
            "questionnaire_version": questionnaire_version,
        },
        "normalization_meta": {
            "source_fields_used": sorted(mapped_fields),
            "unmapped_answers": sorted(
                unmapped_answers,
                key=lambda row: (row["raw_field_name"], row["raw_answer_value"], row["reason"]),
            ),
            "profile_version": profile_version,
            "normalization_warnings": sorted(warnings),
            "conflict_audit": precedence_audit,
        },
    }


def _collect_answer_records(raw_questionnaire: dict[str, Any], field_prefix: str = "") -> list[_AnswerRecord]:
    records: list[_AnswerRecord] = []
    for key in sorted(raw_questionnaire.keys()):
        value = raw_questionnaire[key]
        field_name = f"{field_prefix}{key}" if field_prefix else str(key)
        for answer in _flatten_value(value):
            normalized = _norm(answer)
            if not normalized:
                continue
            records.append(
                _AnswerRecord(
                    raw_field_name=field_name,
                    raw_answer_value=answer,
                    normalized_answer_value=normalized,
                )
            )
    return records


def _flatten_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        rows: list[str] = []
        for item in value:
            rows.extend(_flatten_value(item))
        return rows
    if isinstance(value, dict):
        rows: list[str] = []
        for key in sorted(value.keys()):
            rows.extend(_flatten_value(value[key]))
        return rows
    return [str(value)]


def _map_record(record: _AnswerRecord) -> dict[str, Any]:
    field_name = _norm(record.raw_field_name)
    value = record.normalized_answer_value
    result: dict[str, Any] = {}

    positive_preference_context = _is_positive_food_preference_context(field_name=field_name, value=value)
    soft_negative_preference_context = _is_likely_soft_negative_context(field_name=field_name, value=value)
    canonical_allergens = _extract_allergen_keys(value)
    if canonical_allergens:
        if any(marker in value for marker in ("аллерг", "анафилак", "смерт")) or "allerg" in field_name:
            result["allergens"] = canonical_allergens
        elif any(marker in value for marker in ("неперенос", "intoler")) or "intoler" in field_name:
            result["intolerances"] = canonical_allergens
        elif not positive_preference_context and not soft_negative_preference_context:
            result["unknown_hard"] = ("allergen_like_signal_without_clear_hard_scope",)

    dietary = _extract_dietary_rules(value)
    if dietary:
        result["dietary_rules"] = dietary

    hard_excludes = _extract_hard_ingredient_excludes(field_name=field_name, value=value)
    if hard_excludes:
        result["ingredient_excludes"] = hard_excludes

    if _is_likely_want_now_field(field_name) or "хочу" in value:
        want_now = _extract_want_now(value)
        if want_now:
            result["want_now"] = want_now

    if _is_likely_satiety_field(field_name) or any(token in value for token in ("голод", "сыт", "перекус", "meal", "snack")):
        satiety = _extract_satiety(value)
        if satiety:
            result["satiety"] = satiety

    nutrition = _extract_soft_nutrition(value)
    if nutrition:
        result["nutrition"] = nutrition

    cuisine = _extract_soft_cuisine(value)
    if cuisine:
        result["cuisine"] = cuisine

    familiarity = _extract_familiarity_novelty(value)
    if familiarity:
        result["familiarity_novelty"] = familiarity

    desired_content = _extract_desired_content(field_name=field_name, value=value)
    if desired_content:
        result["desired_content"] = desired_content

    soft_negative = _extract_soft_negative_ingredients(field_name=field_name, value=value)
    if soft_negative:
        result["soft_negative_ingredients"] = soft_negative

    session_tags = _extract_session_tags(value)
    if session_tags:
        result["session_tags"] = session_tags

    return result


def _extract_allergen_keys(value: str) -> tuple[str, ...]:
    rules = {
        "gluten": ("глютен", "gluten"),
        "lactose": ("лактоз", "lactose", "молочк"),
        "nuts": ("орех", "nuts"),
        "peanut": ("арахис", "peanut"),
        "egg": ("яйц", "egg"),
        "soy": ("соя", "soy"),
        "fish_seafood": ("рыб", "морепродукт", "seafood", "fish"),
    }
    return tuple(key for key, markers in rules.items() if any(marker in value for marker in markers))


def _extract_dietary_rules(value: str) -> tuple[str, ...]:
    rules: list[str] = []
    if any(token in value for token in ("вегетари", "vegetarian")):
        rules.append("vegetarian")
    if any(token in value for token in ("веган", "vegan")):
        rules.append("vegan")
    if any(token in value for token in ("без свини", "не ем свини", "no pork", "свинину нельзя")):
        rules.append("no_pork")
    if any(token in value for token in ("халя", "halal")):
        rules.append("halal_like")
    return tuple(sorted(set(rule for rule in rules if rule in CANONICAL_DIETARY_RULES)))


def _extract_hard_ingredient_excludes(field_name: str, value: str) -> tuple[str, ...]:
    hard_scope_by_field = any(
        token in field_name
        for token in ("allerg", "intoler", "ban", "exclude", "strict", "restriction", "constraint", "огранич")
    )
    hard_scope_by_phrase = any(
        token in value for token in ("категор", "строго", "запрещ", "никогда", "исключ", "нельзя")
    )
    if not (hard_scope_by_field or hard_scope_by_phrase):
        return ()
    mapping = {
        "mushroom": ("гриб", "mushroom"),
        "onion": ("лук", "onion"),
        "offal": ("субпроду", "offal"),
        "fish_seafood": ("рыб", "морепроду"),
        "pork": ("свинин", "pork"),
        "spicy_ingredients": ("остр", "spicy"),
    }
    return tuple(sorted(key for key, markers in mapping.items() if any(marker in value for marker in markers)))


def _extract_want_now(value: str) -> tuple[str, ...]:
    mapping = {
        "vegetables": ("овощ", "vegetable", "vegetables"),
        "meat": ("мяс", "meat"),
        "fish_seafood": ("рыб", "морепроду", "fish", "seafood", "fish_seafood"),
        "soup": ("суп", "soup"),
        "spicy": ("остр", "spicy"),
        "sweet": ("слад", "sweet"),
        "hot": ("горяч", "тепл", "hot"),
        "cold": ("холод", "cold", "ice"),
    }
    return tuple(sorted(key for key, markers in mapping.items() if any(marker in value for marker in markers)))


def _extract_satiety(value: str) -> str:
    if any(token in value for token in ("перекус", "snack")):
        return "snack"
    if any(token in value for token in ("легк", "light")):
        return "light_meal"
    if any(token in value for token in ("сыт", "плотн", "full", "full meal", "полноцен", "прием пищ")):
        return "full_meal"
    if any(token in value for token in ("очень голод", "голоден", "hungry")):
        return "full_meal"
    return ""


def _extract_soft_nutrition(value: str) -> dict[str, float]:
    mapping = {
        "low_calorie": ("низкокалор", "low calorie", "легк", "кбжу", "калор", "пп", "зож", "диет"),
        "high_protein": ("белк", "протеин", "high protein"),
        "no_sugar": ("без сах", "no sugar", "избегаю слад"),
    }
    result = {key: 1.0 for key, markers in mapping.items() if any(marker in value for marker in markers)}
    return {key: value for key, value in result.items() if key in CANONICAL_NUTRITION}


def _extract_soft_cuisine(value: str) -> dict[str, float]:
    mapping = {
        "asian": ("ази", "суши", "ролл", "том ям"),
        "italian": ("итальян", "паста", "пицц"),
        "home_style": ("домаш", "традицион"),
        "author_style": ("авторск", "экспериментал"),
        "georgian_caucasian": ("грузин", "кавказ"),
        "russian_home": ("русск", "борщ"),
    }
    result = {key: 1.0 for key, markers in mapping.items() if any(marker in value for marker in markers)}
    return {key: value for key, value in result.items() if key in CANONICAL_CUISINE}


def _extract_familiarity_novelty(value: str) -> dict[str, float]:
    result: dict[str, float] = {}
    if any(token in value for token in ("эксперимент", "новое", "необыч", "разное", "adventurous")):
        result["adventurous_food"] = 1.0
    if any(token in value for token in ("привыч", "знаком", "классик", "familiar")):
        result["familiar_food"] = 1.0
    return {key: value for key, value in result.items() if key in CANONICAL_FAMILIARITY}


def _extract_desired_content(field_name: str, value: str) -> dict[str, float]:
    if _is_likely_soft_negative_field(field_name):
        return {}
    if any(
        token in field_name
        for token in (
            "dislike",
            "soft_negative",
            "avoid",
            "negative",
            "undesired",
            "undesirable",
            "unwanted",
            "not_wanted",
            "allerg",
            "intoler",
            "ingredient_ban",
            "exclude",
            "ban",
        )
    ):
        return {}
    if any(
        token in value
        for token in (
            "не люблю",
            "не хочу",
            "избегаю",
            "терпеть не могу",
            "не нравится",
            "категор",
            "не остро",
            "без остр",
        )
    ):
        return {}
    mapping = {
        "vegetables": ("овощ", "vegetable", "vegetables"),
        "meat": ("мяс", "meat"),
        "fish_seafood": ("рыб", "морепроду", "fish", "seafood", "fish_seafood"),
        "soup": ("суп", "soup"),
        "spicy": ("остр", "spicy"),
        "sweet": ("слад", "sweet"),
    }
    return {key: 1.0 for key, markers in mapping.items() if any(marker in value for marker in markers)}


def _extract_soft_negative_ingredients(field_name: str, value: str) -> dict[str, float]:
    if any(token in value for token in ("категор", "строго", "запрещ", "никогда", "не ем")):
        return {}
    explicit_soft_negative_field = _is_likely_soft_negative_field(field_name)
    if not explicit_soft_negative_field and not _has_soft_negative_phrase(value):
        return {}
    mapping = {
        "mushroom": ("гриб", "mushroom"),
        "onion": ("лук", "onion"),
        "offal": ("субпроду", "offal"),
        "fish_seafood": ("рыб", "морепроду", "fish", "seafood", "fish_seafood"),
        "spicy_ingredients": ("остр", "spicy"),
        "sweet": ("слад", "сах", "sweet"),
        "vegetables": ("овощ", "vegetable", "vegetables"),
        "meat": ("мяс", "meat"),
        "soup": ("суп", "soup"),
    }
    _ = field_name
    return {key: 1.0 for key, markers in mapping.items() if any(marker in value for marker in markers)}


def _is_likely_soft_negative_context(field_name: str, value: str) -> bool:
    return _is_likely_soft_negative_field(field_name) or _has_soft_negative_phrase(value)


def _is_likely_soft_negative_field(field_name: str) -> bool:
    return any(
        token in field_name
        for token in (
            "dislike",
            "soft_negative",
            "negative",
            "undesired",
            "undesirable",
            "unwanted",
            "not_wanted",
            "нежел",
            "негатив",
            "avoid",
            "ingredient_dislike",
            "ingredient_avoid",
        )
    )


def _has_soft_negative_phrase(value: str) -> bool:
    return any(
        token in value
        for token in ("не люблю", "не хочу", "избегаю", "терпеть не могу", "не нравится", "не остро", "без остр")
    )


def _extract_session_tags(value: str) -> tuple[str, ...]:
    tags: list[str] = []
    mapping = {
        "breakfast": ("завтрак", "breakfast"),
        "lunch": ("обед", "ланч", "lunch"),
        "dinner": ("ужин", "dinner"),
        "quick": ("быстро", "quick"),
        "hot": ("горяч", "тепл", "hot"),
        "cold": ("холод", "cold", "ice"),
    }
    for tag, markers in mapping.items():
        if any(marker in value for marker in markers):
            tags.append(tag)
    return tuple(sorted(set(tags)))


def _is_likely_want_now_field(field_name: str) -> bool:
    if _is_likely_soft_negative_field(field_name):
        return False
    return any(
        token in field_name
        for token in (
            "want_now",
            "what_do_you_want_now",
            "food_desires",
            "food_desire",
            "desires",
            "desire",
            "хочу",
            "want",
        )
    )


def _is_positive_food_preference_context(field_name: str, value: str) -> bool:
    if _is_likely_want_now_field(field_name):
        return True
    if any(token in field_name for token in ("like", "likes", "preference", "preferred", "люблю", "предпоч")):
        return True
    return any(token in value for token in ("хочу", "люблю", "нрав", "обож", "предпоч"))


def _is_likely_satiety_field(field_name: str) -> bool:
    return any(token in field_name for token in ("satiety", "hunger", "голод", "сытость"))


def _norm(value: str) -> str:
    return str(value).lower().replace("ё", "е").strip()


def _sorted_dict(values: dict[str, float]) -> dict[str, float]:
    return {key: round(float(values[key]), 6) for key in sorted(values.keys())}


def _apply_precedence_rules(
    hard_constraints: dict[str, set[str]],
    desired_content: dict[str, float],
    soft_negative: dict[str, float],
) -> tuple[dict[str, float], dict[str, float], list[dict[str, str]], list[str]]:
    desired = dict(desired_content)
    negatives = dict(soft_negative)
    warnings: list[str] = []
    audit: list[dict[str, str]] = []

    def _emit(
        raw_signal: str,
        normalized_target: str,
        bucket_before: str,
        bucket_after: str,
        conflict_type: str,
        resolution_rule: str,
        warning: str,
    ) -> None:
        audit.append(
            {
                "raw_signal": raw_signal,
                "normalized_target": normalized_target,
                "bucket_before": bucket_before,
                "bucket_after": bucket_after,
                "conflict_type": conflict_type,
                "resolution_rule": resolution_rule,
                "warning": warning,
            }
        )
        if warning:
            warnings.append(warning)

    hard_keys = set(hard_constraints.get("allergens", set()))
    hard_keys.update(hard_constraints.get("intolerances", set()))
    hard_keys.update(hard_constraints.get("ingredient_excludes", set()))

    for key in sorted(hard_keys):
        if key in desired:
            desired.pop(key, None)
            _emit(
                raw_signal=key,
                normalized_target=key,
                bucket_before="soft_positive",
                bucket_after="removed",
                conflict_type="hard_vs_soft_positive",
                resolution_rule="hard_constraint_overrides_soft",
                warning=f"soft_positive_removed_due_to_hard:{key}",
            )
        if key in negatives:
            negatives.pop(key, None)
            _emit(
                raw_signal=key,
                normalized_target=key,
                bucket_before="soft_negative",
                bucket_after="removed",
                conflict_type="hard_vs_soft_negative",
                resolution_rule="hard_constraint_overrides_soft",
                warning=f"soft_negative_removed_due_to_hard:{key}",
            )

    overlap = sorted(set(desired.keys()) & set(negatives.keys()))
    for key in overlap:
        desired.pop(key, None)
        _emit(
            raw_signal=key,
            normalized_target=key,
            bucket_before="soft_positive",
            bucket_after="removed",
            conflict_type="soft_positive_vs_soft_negative",
            resolution_rule="soft_negative_overrides_soft_positive",
            warning=f"soft_positive_removed_due_to_soft_negative:{key}",
        )

    dietary_rules = set(hard_constraints.get("dietary_rules", set()))
    dietary_forbidden: set[str] = set()
    for rule in dietary_rules:
        dietary_forbidden.update(DIETARY_FORBIDDEN_CONTENT.get(rule, ()))

    for key in sorted(dietary_forbidden):
        if key in desired:
            desired.pop(key, None)
            _emit(
                raw_signal=key,
                normalized_target=key,
                bucket_before="soft_positive",
                bucket_after="removed",
                conflict_type="dietary_vs_soft_positive",
                resolution_rule="dietary_rule_overrides_soft_positive",
                warning=f"soft_positive_removed_due_to_dietary:{key}",
            )
        if key in negatives:
            _emit(
                raw_signal=key,
                normalized_target=key,
                bucket_before="soft_negative",
                bucket_after="redundant",
                conflict_type="dietary_vs_soft_negative",
                resolution_rule="mark_soft_negative_redundant_under_dietary",
                warning=f"soft_negative_redundant_due_to_dietary:{key}",
            )

    return _sorted_dict(desired), _sorted_dict(negatives), audit, sorted(set(warnings))
