from app.pipelines.questionnaire_normalizer import normalize_questionnaire


def test_normalizer_is_deterministic_for_same_input() -> None:
    raw = {
        "likes": ["люблю белковую еду", "хочу суп и рыбу"],
        "dislikes": ["не люблю лук"],
        "hunger_level": "очень голоден, нужна плотная еда",
    }
    first = normalize_questionnaire(raw_questionnaire=raw, request_context={"time_of_day": "lunch"})
    second = normalize_questionnaire(raw_questionnaire=raw, request_context={"time_of_day": "lunch"})
    assert first == second


def test_hard_and_soft_are_not_mixed() -> None:
    raw = {
        "dislikes": [
            "у меня аллергия на арахис и глютен",
            "я вегетарианец и не ем свинину",
            "не люблю грибы",
        ],
    }
    normalized = normalize_questionnaire(raw_questionnaire=raw, request_context=None)
    hard = normalized["hard_constraints"]
    soft = normalized["soft_preferences"]
    assert "peanut" in hard["allergens"]
    assert "gluten" in hard["allergens"]
    assert "vegetarian" in hard["dietary_rules"]
    assert "no_pork" in hard["dietary_rules"]
    assert "mushroom" not in hard["ingredient_excludes"]
    assert "mushroom" in soft["soft_negative_ingredients"]


def test_unmapped_answers_are_surfaced_in_meta() -> None:
    raw = {
        "favorite_color": "ultraviolet",
        "age": 28,
        "likes": ["нравится азиатская кухня"],
    }
    normalized = normalize_questionnaire(raw_questionnaire=raw, request_context=None)
    unmapped = normalized["normalization_meta"]["unmapped_answers"]
    assert any(row["raw_field_name"] == "favorite_color" for row in unmapped)
    assert any(row["raw_field_name"] == "age" for row in unmapped)
