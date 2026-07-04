from app.pipelines.questionnaire_scoring import score_questionnaire_candidates


def test_scoring_uses_only_safe_candidates_input() -> None:
    normalized = _base_profile()
    safe = [
        _dish("1", "Fish soup", ingredient={"salmon": 1.0}, format_texture={"soup": 1.0}, nutrition={"satiety_class": "hearty"}),
        _dish("2", "Chicken rice", ingredient={"chicken": 1.0}, nutrition={"satiety_class": "hearty"}),
    ]
    ranked, _ = score_questionnaire_candidates(
        request_id="req1",
        user_id=1,
        normalized_profile=normalized,
        safe_candidates=safe,
        request_context={"venue": "gc"},
        top_k=10,
    )
    ids = [row["dish_id"] for row in ranked]
    assert ids == ["1", "2"]


def test_soft_nutrition_preferences_influence_order() -> None:
    normalized = _base_profile()
    normalized["soft_preferences"]["nutrition"] = {"high_protein": 1.0, "low_calorie": 1.0}
    safe = [
        _dish("1", "Protein bowl", ingredient={"chicken": 1.0}, nutrition={"high_protein": True, "low_calorie": True, "satiety_class": "hearty"}),
        _dish("2", "Carb meal", ingredient={"rice": 1.0}, nutrition={"high_protein": False, "low_calorie": False, "satiety_class": "hearty"}),
    ]
    ranked, _ = score_questionnaire_candidates("req2", 1, normalized, safe, {"venue": "gc"}, 10)
    assert ranked[0]["dish_id"] == "1"
    assert ranked[0]["nutrition_match"] > ranked[1]["nutrition_match"]


def test_familiarity_vs_adventurous_influences_rank() -> None:
    normalized = _base_profile()
    normalized["soft_preferences"]["desired_content"] = {}
    normalized["request_context"]["want_now"] = []
    normalized["soft_preferences"]["familiarity_novelty"] = {"adventurous_food": 1.0}
    safe = [
        _dish("1", "Author special", cuisine={"author_style": 1.0}, nutrition={"satiety_class": "hearty"}),
        _dish("2", "Home soup", cuisine={"home_style": 1.0}, format_texture={"soup": 1.0}, nutrition={"satiety_class": "hearty"}),
    ]
    ranked, _ = score_questionnaire_candidates("req3", 1, normalized, safe, {"venue": "gc"}, 10)
    assert ranked[0]["dish_id"] == "1"


def test_soft_negatives_penalize_without_hard_block() -> None:
    normalized = _base_profile()
    normalized["soft_preferences"]["soft_negative_ingredients"] = {"onion": 1.0}
    safe = [
        _dish("1", "Onion fish", ingredient={"salmon": 1.0, "onion": 1.0}, flags={"onion": True}, nutrition={"satiety_class": "hearty"}),
        _dish("2", "Clean fish", ingredient={"salmon": 1.0}, nutrition={"satiety_class": "hearty"}),
    ]
    ranked, _ = score_questionnaire_candidates("req4", 1, normalized, safe, {"venue": "gc"}, 10)
    ids = [row["dish_id"] for row in ranked]
    assert "1" in ids and "2" in ids
    penalty_by_id = {row["dish_id"]: row["soft_negative_penalty"] for row in ranked}
    assert penalty_by_id["1"] > penalty_by_id["2"]


def test_non_recommendable_entities_are_excluded() -> None:
    normalized = _base_profile()
    safe = [
        _dish("1", "Соус чесночный", category="sauce", nutrition={"satiety_class": "light"}),
        _dish("2", "Chicken soup", ingredient={"chicken": 1.0}, format_texture={"soup": 1.0}, nutrition={"satiety_class": "hearty"}),
        _dish("3", "Service charge", category="service", nutrition={"satiety_class": "light"}),
    ]
    ranked, _ = score_questionnaire_candidates("req5", 1, normalized, safe, {"venue": "gc"}, 10)
    ids = [row["dish_id"] for row in ranked]
    assert ids == ["2"]


def test_scoring_is_deterministic_across_runs() -> None:
    normalized = _base_profile()
    safe = [
        _dish("1", "Fish soup", ingredient={"salmon": 1.0}, format_texture={"soup": 1.0}, nutrition={"satiety_class": "hearty"}),
        _dish("2", "Chicken rice", ingredient={"chicken": 1.0}, nutrition={"satiety_class": "hearty"}),
    ]
    first, first_trace = score_questionnaire_candidates("req6", 1, normalized, safe, {"venue": "gc"}, 10)
    second, second_trace = score_questionnaire_candidates("req6", 1, normalized, safe, {"venue": "gc"}, 10)
    assert first == second
    assert first_trace == second_trace


def _base_profile() -> dict:
    return {
        "soft_preferences": {
            "desired_content": {"fish_seafood": 1.0, "soup": 1.0},
            "nutrition": {},
            "cuisine": {},
            "familiarity_novelty": {},
            "soft_negative_ingredients": {},
        },
        "request_context": {"want_now": ["fish_seafood"], "satiety": "full_meal"},
    }


def _dish(
    dish_id: str,
    name: str,
    *,
    ingredient: dict | None = None,
    cuisine: dict | None = None,
    nutrition: dict | None = None,
    format_texture: dict | None = None,
    flags: dict | None = None,
    category: str = "main",
) -> dict:
    return {
        "dish_id": dish_id,
        "dish_name": name,
        "venue": "gc",
        "category": category,
        "ingredient_features": ingredient or {},
        "cuisine_features": cuisine or {},
        "nutrition_features": nutrition or {},
        "format_texture_features": format_texture or {},
        "taste_features": {},
        "constraint_flags": flags or {},
    }
