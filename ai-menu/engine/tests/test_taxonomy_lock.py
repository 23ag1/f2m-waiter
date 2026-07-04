from pathlib import Path

import pytest

from app.config.taxonomy import TaxonomyError, load_runtime_taxonomy
from app.domain.models import ProfileLayer, UserFeatureValue
from app.domain.policy import ensure_profile_layer_policy


def test_alias_resolution_for_cuisine() -> None:
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    assert taxonomy.resolve_tag("cuisine", "georgian") == "georgian_caucasian"


def test_invalid_tag_raises() -> None:
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    with pytest.raises(TaxonomyError):
        taxonomy.resolve_tag("cuisine", "unknown_cuisine")


def test_nutrition_boolean_tag_is_allowed() -> None:
    taxonomy = load_runtime_taxonomy(Path("docs/runtime_taxonomy_resolved_v1.json"))
    assert taxonomy.is_allowed("nutrition", "high_protein")


def test_event_source_cannot_write_explicit_layer() -> None:
    feature = UserFeatureValue(
        user_id=1,
        profile_layer=ProfileLayer.EXPLICIT,
        axis="taste",
        feature_key="spicy",
        weight=0.2,
        source="event",
    )
    with pytest.raises(ValueError):
        ensure_profile_layer_policy(feature=feature, source_is_event=True)


def test_non_event_source_cannot_write_event_layers() -> None:
    feature = UserFeatureValue(
        user_id=1,
        profile_layer=ProfileLayer.LONG_TERM,
        axis="taste",
        feature_key="spicy",
        weight=0.2,
        source="questionnaire",
    )
    with pytest.raises(ValueError):
        ensure_profile_layer_policy(feature=feature, source_is_event=False)
