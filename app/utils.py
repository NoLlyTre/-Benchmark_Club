from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from .models import Build, Subscription, User


@dataclass
class GamificationProfile:
    title: str
    points: int
    total_builds: int
    published_builds: int
    followers: int
    following: int


def get_gamification_profile(user: User) -> GamificationProfile:
    points = sum(ua.achievement.points for ua in user.achievements)
    total_builds = Build.query.filter_by(author_id=user.id).count()
    published_builds = Build.query.filter_by(
        author_id=user.id, is_published=True
    ).count()
    followers = Subscription.query.filter_by(followed_id=user.id).count()
    following = Subscription.query.filter_by(follower_id=user.id).count()

    title = _determine_title(points, published_builds, followers)
    return GamificationProfile(
        title=title,
        points=points,
        total_builds=total_builds,
        published_builds=published_builds,
        followers=followers,
        following=following,
    )


def _determine_title(points: int, published: int, followers: int) -> str:
    if points >= 500 or (published >= 10 and followers >= 20):
        return "Легенда сборок"
    if points >= 250 or (published >= 5 and followers >= 10):
        return "Оверклокер"
    if points >= 100 or (published >= 2 and followers >= 5):
        return "Мастер сборки"
    if points >= 50 or published >= 1:
        return "Новичок"
    return "Наблюдатель"


def save_image(file_storage, subdir: str) -> Optional[str]:
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    if extension not in allowed:
        raise ValueError("Неподдерживаемый формат файла.")

    uploads_dir = Path(current_app.config["UPLOAD_FOLDER"]) / subdir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    unique_filename = f"{uuid4().hex}.{extension}"
    file_path = uploads_dir / unique_filename
    file_storage.save(file_path)
    return f"{subdir}/{unique_filename}"


def delete_image(relative_path: Optional[str]) -> None:
    if not relative_path:
        return
    upload_root = Path(current_app.config["UPLOAD_FOLDER"])
    full_path = upload_root / relative_path
    try:
        full_path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Не удалось удалить файл %s", full_path)
