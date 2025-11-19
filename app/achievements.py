from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .extensions import db
from .models import Achievement, Build, Subscription, User, UserAchievement


@dataclass(frozen=True)
class AchievementRule:
    code: str
    name: str
    description: str
    points: int


ACHIEVEMENT_RULES: tuple[AchievementRule, ...] = (
    AchievementRule(
        code="first_build",
        name="Первая сборка",
        description="Опубликуйте свою первую сборку.",
        points=50,
    ),
    AchievementRule(
        code="commentator",
        name="Комментатор",
        description="Оставьте 5 полезных комментариев.",
        points=30,
    ),
    AchievementRule(
        code="mentor",
        name="Наставник",
        description="Получите 3 оценки '5' за ваши сборки.",
        points=80,
    ),
    AchievementRule(
        code="social",
        name="Человек-Коммьюнити",
        description="Подпишитесь на 3 экспертов.",
        points=20,
    ),
)


def sync_achievements_catalog() -> None:
    """Ensure that the achievement catalog is pre-populated."""
    for rule in ACHIEVEMENT_RULES:
        existing = Achievement.query.filter_by(code=rule.code).first()
        if not existing:
            db.session.add(
                Achievement(
                    code=rule.code,
                    name=rule.name,
                    description=rule.description,
                    points=rule.points,
                )
            )
    db.session.commit()


def evaluate_achievements(user: User) -> Iterable[UserAchievement]:
    """Check user progress and award new achievements."""
    unlocked: list[UserAchievement] = []
    achievement_map = {a.code: a for a in Achievement.query.all()}
    owned_codes = {ua.achievement.code for ua in user.achievements}

    # First build published
    if "first_build" not in owned_codes and "first_build" in achievement_map:
        published_builds = (
            Build.query.filter_by(author_id=user.id, is_published=True).count()
        )
        if published_builds >= 1:
            unlocked.append(_grant(user, achievement_map["first_build"]))

    # Commentator badge
    if "commentator" not in owned_codes and "commentator" in achievement_map:
        if len(user.comments) >= 5:
            unlocked.append(_grant(user, achievement_map["commentator"]))

    # Mentor badge (three five-star ratings)
    if "mentor" not in owned_codes and "mentor" in achievement_map:
        five_star_count = sum(
            1
            for build in user.builds
            for rating in build.ratings
            if rating.score == 5
        )
        if five_star_count >= 3:
            unlocked.append(_grant(user, achievement_map["mentor"]))

    # Social badge (follow three experts)
    if "social" not in owned_codes and "social" in achievement_map:
        if Subscription.query.filter_by(follower_id=user.id).count() >= 3:
            unlocked.append(_grant(user, achievement_map["social"]))

    if unlocked:
        db.session.commit()
    return unlocked


def _grant(user: User, achievement: Achievement) -> UserAchievement:
    granted = UserAchievement(user=user, achievement=achievement)
    db.session.add(granted)
    return granted
