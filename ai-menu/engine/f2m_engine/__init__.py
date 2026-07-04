"""Food2Mood recommendation engine — standalone package."""

from f2m_engine.api import create_app
from f2m_engine.pipelines.recommend_router import route_recommendation
from f2m_engine.pipelines.profile_rebuild import rebuild_profiles

__all__ = [
    "create_app",
    "route_recommendation",
    "rebuild_profiles",
]
