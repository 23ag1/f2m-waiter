"""
Рекомендательный слой: profile (Postgres) → engine_adapter (Rec2) → ranker.
Публичный API — функция rank_dishes из ranker.

Старые scorer.py и profile_features.py остаются для использования в
violations.py (UX-слой красных warning-тегов на карточке блюда).
"""
from app.services.recommendation.engine_adapter import recommend_via_engine
from app.services.recommendation.profile_features import UserFeatureBag, profile_to_features
from app.services.recommendation.ranker import rank_dishes

__all__ = [
    "UserFeatureBag",
    "profile_to_features",
    "rank_dishes",
    "recommend_via_engine",
]
