from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from f2m_engine.config.taxonomy import RuntimeTaxonomy
from f2m_engine.domain.models import ConstraintScope, ProfileLayer, UserConstraint, UserFeatureValue
from f2m_engine.repositories.base import Repository


@dataclass(frozen=True)
class ExtractionStats:
    users_processed: int
    constraints_written: int
    features_written: int


def run_seed_questionnaire_extraction(
    users_path: Path | str,
    repository: Repository,
    taxonomy: RuntimeTaxonomy,
) -> ExtractionStats:
    with Path(users_path).open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    users = payload.get("users", [])
    constraints_written = 0
    features_written = 0

    for user in users:
        user_id = int(user["user_id"])
        questionnaire = user.get("questionnaire", {})
        likes: list[str] = questionnaire.get("likes", [])
        dislikes: list[str] = questionnaire.get("dislikes", [])

        repository.write_questionnaire_submission(
            {
                "user_id": user_id,
                "questionnaire_type": "seed_json",
                "raw_answers_json": questionnaire,
                "extracted_json": {
                    "likes": likes,
                    "dislikes": dislikes,
                    "matched_constraints": [
                        constraint.constraint_key
                        for constraint in _extract_hard_constraints(user_id=user_id, likes=likes, dislikes=dislikes)
                    ],
                    "matched_features": [
                        f"{feature.axis}:{feature.feature_key}"
                        for feature in _extract_explicit_features(user_id=user_id, likes=likes, dislikes=dislikes)
                    ],
                },
            }
        )

        for constraint in _extract_hard_constraints(user_id=user_id, likes=likes, dislikes=dislikes):
            repository.upsert_user_constraint(constraint)
            constraints_written += 1

        for feature in _extract_explicit_features(user_id=user_id, likes=likes, dislikes=dislikes):
            if taxonomy.is_allowed(feature.axis, feature.feature_key):
                repository.upsert_user_feature(feature, source_is_event=False)
                features_written += 1

    return ExtractionStats(
        users_processed=len(users),
        constraints_written=constraints_written,
        features_written=features_written,
    )


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def _extract_hard_constraints(
    user_id: int,
    likes: list[str],
    dislikes: list[str],
) -> list[UserConstraint]:
    constraints: dict[str, UserConstraint] = {}
    normalized_likes = [_normalize(text) for text in likes]
    normalized_dislikes = [_normalize(text) for text in dislikes]
    all_phrases = [*normalized_likes, *normalized_dislikes]
    joined = " ".join(all_phrases)

    def add_constraint(key: str, reason: str, confidence: float = 0.9) -> None:
        constraints[key] = UserConstraint(
            user_id=user_id,
            constraint_key=key,
            scope=ConstraintScope.HARD,
            source="seed_json",
            reason_text=reason,
            confidence=confidence,
        )

    medical_markers = ("аллерг", "неперенос", "смертель", "анафилак", "медицин")

    def has_medical_phrase(patterns: tuple[str, ...]) -> bool:
        return any(
            any(marker in phrase for marker in medical_markers) and any(pattern in phrase for pattern in patterns)
            for phrase in all_phrases
        )

    if has_medical_phrase(("арахис",)):
        add_constraint("peanut", "explicit peanut allergy/intolerance")
    if has_medical_phrase(("лактоз", "молочк")):
        add_constraint("lactose", "explicit lactose intolerance")
    if has_medical_phrase(("рыб", "морепродукт", "кревет", "устриц", "мид", "кальмар")):
        add_constraint("fish_seafood", "explicit fish/seafood allergy/intolerance")
    if has_medical_phrase(("яйц", "яиц")):
        add_constraint("egg", "explicit egg allergy/intolerance")
    if has_medical_phrase(("соя", "соев")):
        add_constraint("soy", "explicit soy allergy/intolerance")
    if has_medical_phrase(("глютен",)):
        add_constraint("gluten", "explicit gluten allergy/intolerance")
    if has_medical_phrase(("орех",)):
        add_constraint("nuts", "explicit nuts allergy/intolerance")

    if any("халял" in phrase for phrase in all_phrases):
        add_constraint("halal", "explicit halal restriction", confidence=0.95)

    strict_ethical_vegan_markers = ("строгий веган", "этич", "категорически не ем", "не ем ничего животного")
    if any("веган" in phrase for phrase in all_phrases) and any(
        marker in joined for marker in strict_ethical_vegan_markers
    ):
        add_constraint("vegan", "strict ethical vegan declaration", confidence=0.95)

    mammalian_markers = (
        "красное мясо",
        "говядин",
        "свинин",
        "баранин",
        "теля",
        "мясной бульон",
        "бульон мясной",
        "mammal",
        "alpha-gal",
    )
    if any(marker in joined for marker in mammalian_markers):
        add_constraint(
            "mammalian_red_meat",
            "explicit mammalian/red meat restriction",
            confidence=0.9,
        )
    if "бульон" in joined and any(marker in joined for marker in ("мясн", "говяж", "барани", "свинин")):
        add_constraint(
            "mammalian_broth_stock",
            "explicit mammalian broth/stock restriction",
            confidence=0.9,
        )

    return list(constraints.values())


def _extract_explicit_features(
    user_id: int,
    likes: list[str],
    dislikes: list[str],
) -> list[UserFeatureValue]:
    features: dict[tuple[str, str], UserFeatureValue] = {}
    likes_joined = " ".join(_normalize(text) for text in likes)
    dislikes_joined = " ".join(_normalize(text) for text in dislikes)

    positives = [
        ("nutrition", "high_protein", ("белк", "протеин")),
        ("cuisine", "healthy", ("полезн", "правильно")),
        ("cuisine", "asian", ("ази", "суши", "ролл")),
        ("cuisine", "italian", ("итальян", "паста", "пицц")),
        ("cuisine", "georgian_caucasian", ("грузин", "кавказ")),
        ("format_texture", "bakery", ("выпечк",)),
        ("format_texture", "light", ("легк",)),
        ("context", "healthy_choice", ("полезн", "правильно")),
    ]
    negatives = [
        ("restriction", "spicy_avoid", ("не переношу острую", "острую еду")),
        ("restriction", "no_sugar", ("сахар", "сладк")),
        ("restriction", "offal", ("субпродукт", "печен", "язык")),
        ("format_texture", "fried", ("фритюр", "в масле")),
        ("ingredient", "onion", ("лук",)),
        ("ingredient", "mushroom", ("гриб",)),
    ]

    for axis, feature_key, patterns in positives:
        if any(pattern in likes_joined for pattern in patterns):
            features[(axis, feature_key)] = UserFeatureValue(
                user_id=user_id,
                profile_layer=ProfileLayer.EXPLICIT,
                axis=axis,
                feature_key=feature_key,
                weight=0.7,
                source="questionnaire",
                confidence=0.75,
            )

    for axis, feature_key, patterns in negatives:
        if any(pattern in dislikes_joined for pattern in patterns):
            features[(axis, feature_key)] = UserFeatureValue(
                user_id=user_id,
                profile_layer=ProfileLayer.EXPLICIT,
                axis=axis,
                feature_key=feature_key,
                weight=-0.7,
                source="questionnaire",
                confidence=0.75,
            )

    return list(features.values())
