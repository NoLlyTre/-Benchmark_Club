from datetime import datetime
from enum import Enum

from flask_login import UserMixin

from .extensions import db, login_manager


class Role(Enum):
    MEMBER = "member"
    ADMIN = "admin"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), default=Role.MEMBER, nullable=False)
    bio = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    builds = db.relationship("Build", back_populates="author", cascade="all,delete")
    comments = db.relationship(
        "BuildComment", back_populates="author", cascade="all,delete"
    )
    ratings = db.relationship(
        "BuildRating", back_populates="reviewer", cascade="all,delete"
    )
    achievements = db.relationship(
        "UserAchievement", back_populates="user", cascade="all,delete"
    )
    subscriptions = db.relationship(
        "Subscription",
        foreign_keys="Subscription.follower_id",
        back_populates="follower",
        cascade="all,delete",
    )
    followers = db.relationship(
        "Subscription",
        foreign_keys="Subscription.followed_id",
        back_populates="followed",
        cascade="all,delete",
    )
    benchmarks = db.relationship(
        "BenchmarkResult", back_populates="user", cascade="all,delete"
    )

    def __repr__(self) -> str:
        return f"<User {self.phone_number}>"

    def get_role_display(self) -> str:
        return self.role.value


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


build_tags = db.Table(
    "build_tags",
    db.Column("build_id", db.Integer, db.ForeignKey("builds.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Build(db.Model):
    __tablename__ = "builds"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    hardware_summary = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    cover_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    author = db.relationship("User", back_populates="builds")
    tags = db.relationship("Tag", secondary=build_tags, back_populates="builds")
    comments = db.relationship(
        "BuildComment", back_populates="build", cascade="all,delete-orphan"
    )
    ratings = db.relationship(
        "BuildRating", back_populates="build", cascade="all,delete-orphan"
    )
    components = db.relationship(
        "BuildComponent", back_populates="build", cascade="all,delete-orphan"
    )
    benchmarks = db.relationship(
        "BenchmarkResult", back_populates="build", cascade="all,delete-orphan"
    )

    def average_rating(self) -> float | None:
        if not self.ratings:
            return None
        return sum(r.score for r in self.ratings) / len(self.ratings)

    def display_author_name(self) -> str:
        if self.is_anonymous:
            return "Анонимный конструктор"
        return self.author.display_name

    def allow_profile_link(self) -> bool:
        return not self.is_anonymous


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    builds = db.relationship("Build", secondary=build_tags, back_populates="tags")


class BuildComment(db.Model):
    __tablename__ = "build_comments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    build = db.relationship("Build", back_populates="comments")
    author = db.relationship("User", back_populates="comments")

    def display_author_name(self) -> str:
        if self.is_anonymous:
            return "Анонимный участник"
        return self.author.display_name


class BuildRating(db.Model):
    __tablename__ = "build_ratings"

    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    build = db.relationship("Build", back_populates="ratings")
    reviewer = db.relationship("User", back_populates="ratings")

    __table_args__ = (
        db.CheckConstraint("score BETWEEN 1 AND 5", name="check_rating_range"),
        db.UniqueConstraint(
            "build_id", "reviewer_id", name="uniq_build_reviewer_rating"
        ),
    )

    def display_reviewer_name(self) -> str:
        if self.is_anonymous:
            return "Анонимный оценщик"
        return self.reviewer.display_name


class BuildComponent(db.Model):
    __tablename__ = "build_components"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    dns_price = db.Column(db.Numeric(10, 2))
    dns_url = db.Column(db.String(255))
    megamarket_price = db.Column(db.Numeric(10, 2))
    megamarket_url = db.Column(db.String(255))
    mvideo_price = db.Column(db.Numeric(10, 2))
    mvideo_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"), nullable=False)

    build = db.relationship("Build", back_populates="components")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "dns_price": self.dns_price,
            "dns_url": self.dns_url,
            "megamarket_price": self.megamarket_price,
            "megamarket_url": self.megamarket_url,
            "mvideo_price": self.mvideo_price,
            "mvideo_url": self.mvideo_url,
        }


class Achievement(db.Model):
    __tablename__ = "achievements"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)

    user_achievements = db.relationship(
        "UserAchievement",
        back_populates="achievement",
        cascade="all,delete-orphan",
    )


class UserAchievement(db.Model):
    __tablename__ = "user_achievements"

    id = db.Column(db.Integer, primary_key=True)
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    achievement_id = db.Column(
        db.Integer, db.ForeignKey("achievements.id"), nullable=False
    )

    user = db.relationship("User", back_populates="achievements")
    achievement = db.relationship("Achievement", back_populates="user_achievements")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "achievement_id",
            name="uniq_user_achievement",
        ),
    )


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    followed_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    follower = db.relationship(
        "User", foreign_keys=[follower_id], back_populates="subscriptions"
    )
    followed = db.relationship(
        "User", foreign_keys=[followed_id], back_populates="followers"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "follower_id", "followed_id", name="uniq_follow_relationship"
        ),
        db.CheckConstraint("follower_id != followed_id", name="no_self_follow"),
    )


class BenchmarkResult(db.Model):
    __tablename__ = "benchmark_results"

    id = db.Column(db.Integer, primary_key=True)
    build_name = db.Column(db.String(120), nullable=False)
    benchmark_name = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    build_id = db.Column(db.Integer, db.ForeignKey("builds.id"))
    screenshot_path = db.Column(db.String(255))
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="benchmarks")
    build = db.relationship("Build", back_populates="benchmarks")

    def display_author_name(self) -> str:
        if self.is_anonymous:
            return "Анонимный участник"
        return self.user.display_name
