from __future__ import annotations

from f2m_engine.domain.models import ConstraintScope, ProfileLayer, UserConstraint, UserFeatureValue


def ensure_hard_constraint_only_in_constraints(constraint: UserConstraint) -> None:
    """
    Guard helper for the spec lock rule:
    hard constraints must live in user_constraints.
    """
    if constraint.scope != ConstraintScope.HARD:
        return


def ensure_profile_layer_policy(feature: UserFeatureValue, source_is_event: bool) -> None:
    """
    Guard helper for profile layer policy:
    - explicit: questionnaire-derived non-hard preferences
    - long_term/short_term: event-derived state
    """
    if source_is_event and feature.profile_layer == ProfileLayer.EXPLICIT:
        raise ValueError("Event-derived updates cannot write into explicit profile layer")
    if not source_is_event and feature.profile_layer in {
        ProfileLayer.LONG_TERM,
        ProfileLayer.SHORT_TERM,
    }:
        raise ValueError(
            "Non-event updates cannot write into long_term/short_term profile layers"
        )
