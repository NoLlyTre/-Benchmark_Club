from __future__ import annotations

from typing import Iterable

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from .achievements import evaluate_achievements
from .extensions import db
from .forms import (
    BenchmarkForm,
    BuildForm,
    CommentForm,
    HiddenIdForm,
    LoginForm,
    ProfileForm,
    RatingForm,
    RegistrationForm,
    parse_tags,
)
from .models import (
    BenchmarkResult,
    Build,
    BuildComment,
    BuildComponent,
    BuildRating,
    Role,
    Subscription,
    Tag,
    User,
    UserAchievement,
)
from .utils import delete_image, get_gamification_profile, save_image


main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
builds_bp = Blueprint("builds", __name__, url_prefix="/builds")
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")
media_bp = Blueprint("media", __name__)


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(builds_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(media_bp)


@media_bp.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    upload_root = current_app.config["UPLOAD_FOLDER"]
    return send_from_directory(upload_root, filename)


@main_bp.route("/")
def index():
    """Landing page highlighting featured builds."""
    featured_builds = (
        Build.query.filter_by(is_published=True)
        .order_by(Build.created_at.desc())
        .limit(6)
        .all()
    )
    leaderboard = (
        db.session.query(
            User.id,
            User.display_name,
            func.count(Build.id).label("published"),
        )
        .join(Build, Build.author_id == User.id)
        .filter(Build.is_published.is_(True))
        .group_by(User.id, User.display_name)
        .order_by(func.count(Build.id).desc())
        .limit(5)
        .all()
    )
    return render_template(
        "index.html",
        featured_builds=featured_builds,
        leaderboard=leaderboard,
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.overview"))

    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(phone_number=form.phone_number.data).first():
            flash("Пользователь с таким номером уже существует.", "warning")
            return redirect(url_for("auth.register"))

        user = User(
            phone_number=form.phone_number.data,
            display_name=form.display_name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data),
            role=Role.MEMBER,
        )
        db.session.add(user)
        db.session.commit()
        current_app.logger.info("New user registered: %s", user.phone_number)

        login_user(user)
        flash("Добро пожаловать в Бенчмарк Клуб!", "success")
        return redirect(url_for("dashboard.overview"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.overview"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(phone_number=form.phone_number.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash("С возвращением, энтузиаст!", "success")
            return redirect(request.args.get("next") or url_for("dashboard.overview"))
        flash("Неверный номер телефона или пароль.", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    current_app.logger.info("User %s logged out", current_user.phone_number)
    logout_user()
    flash("До встречи на следующих тестах!", "info")
    return redirect(url_for("main.index"))


@dashboard_bp.route("/")
@login_required
def overview():
    profile = get_gamification_profile(current_user)
    recent_achievements = (
        UserAchievement.query.filter_by(user_id=current_user.id)
        .order_by(UserAchievement.awarded_at.desc())
        .limit(5)
        .all()
    )
    recent_builds = (
        Build.query.filter_by(author_id=current_user.id)
        .order_by(Build.created_at.desc())
        .limit(5)
        .all()
    )
    latest_benchmarks = (
        BenchmarkResult.query.filter_by(user_id=current_user.id)
        .order_by(BenchmarkResult.recorded_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard/overview.html",
        profile=profile,
        achievements=recent_achievements,
        recent_builds=recent_builds,
        benchmarks=latest_benchmarks,
    )


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data
        current_user.email = form.email.data
        current_user.bio = form.bio.data
        db.session.commit()
        flash("Профиль обновлен.", "success")
        return redirect(url_for("dashboard.profile"))
    return render_template("dashboard/profile.html", form=form)


@dashboard_bp.route("/benchmarks", methods=["GET", "POST"])
@login_required
def benchmarks():
    user_builds = (
        Build.query.filter_by(author_id=current_user.id)
        .order_by(Build.created_at.desc())
        .all()
    )
    form = BenchmarkForm()
    build_choices = [(0, "— Выберите сборку —")] + [
        (build.id, build.title) for build in user_builds
    ]
    form.build_id.choices = build_choices
    if request.method == "GET" and not form.build_id.data:
        form.build_id.data = 0

    if form.validate_on_submit():
        selected_build = None
        if form.build_id.data:
            selected_build = Build.query.get(form.build_id.data)
            if not selected_build or selected_build.author_id != current_user.id:
                flash("Можно выбирать только свои сборки.", "danger")
                return redirect(url_for("dashboard.benchmarks"))
        build_name = (
            selected_build.title if selected_build else form.custom_build_name.data
        )
        result = BenchmarkResult(
            build_name=build_name,
            benchmark_name=form.benchmark_name.data,
            score=form.score.data,
            notes=form.notes.data,
            user=current_user,
            is_anonymous=form.is_anonymous.data,
        )
        if selected_build:
            result.build = selected_build
        if form.screenshot.data:
            try:
                path = save_image(
                    form.screenshot.data,
                    current_app.config["BENCHMARK_IMAGE_SUBDIR"],
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("dashboard.benchmarks"))
            result.screenshot_path = path

        db.session.add(result)
        db.session.commit()
        flash("Результат бенчмарка сохранен.", "success")
        return redirect(url_for("dashboard.benchmarks"))

    records = (
        BenchmarkResult.query.filter_by(user_id=current_user.id)
        .order_by(BenchmarkResult.recorded_at.desc())
        .all()
    )
    return render_template(
        "dashboard/benchmarks.html",
        form=form,
        records=records,
        available_builds=user_builds,
    )


@builds_bp.route("/")
def catalog():
    """Public catalog of published builds."""
    tag = request.args.get("tag")
    query = Build.query.filter_by(is_published=True)
    if tag:
        query = query.join(Build.tags).filter(Tag.name == tag)
    builds = query.order_by(Build.created_at.desc()).all()
    return render_template("builds/catalog.html", builds=builds, tag=tag)


@builds_bp.route("/mine")
@login_required
def mine():
    my_builds = (
        Build.query.filter_by(author_id=current_user.id)
        .order_by(Build.updated_at.desc())
        .all()
    )
    return render_template("builds/mine.html", builds=my_builds)


@builds_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = BuildForm()
    if form.validate_on_submit():
        build = Build(
            title=form.title.data,
            description=form.description.data,
            hardware_summary=form.hardware_summary.data,
            is_published=form.is_published.data,
            is_anonymous=form.publish_as_anonymous.data,
            author=current_user,
        )
        if form.cover_image.data:
            try:
                image_path = save_image(
                    form.cover_image.data,
                    current_app.config["BUILD_IMAGE_SUBDIR"],
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("builds/editor.html", form=form)
            build.cover_image = image_path
        _apply_tags(build, parse_tags(form.tags.data))
        _apply_components(build, form.components.entries)
        db.session.add(build)
        db.session.commit()
        evaluate_achievements(current_user)
        flash("Сборка сохранена.", "success")
        return redirect(url_for("builds.mine"))
    return render_template("builds/editor.html", form=form)


@builds_bp.route("/<int:build_id>/edit", methods=["GET", "POST"])
@login_required
def edit(build_id: int):
    build = Build.query.get_or_404(build_id)
    if build.author != current_user:
        abort(403)

    form = BuildForm(obj=build)
    if request.method == "GET":
        form.tags.data = ", ".join(tag.name for tag in build.tags)
        form.is_published.data = build.is_published
        form.publish_as_anonymous.data = build.is_anonymous
        existing_components = list(build.components)
        needed_entries = max(len(existing_components), form.components.min_entries)
        while len(form.components.entries) < needed_entries:
            form.components.append_entry()
        for entry, component in zip(form.components.entries, existing_components):
            entry.form.name.data = component.name
            entry.form.dns_price.data = component.dns_price
            entry.form.dns_url.data = component.dns_url
            entry.form.megamarket_price.data = component.megamarket_price
            entry.form.megamarket_url.data = component.megamarket_url
            entry.form.mvideo_price.data = component.mvideo_price
            entry.form.mvideo_url.data = component.mvideo_url

    if form.validate_on_submit():
        build.title = form.title.data
        build.description = form.description.data
        build.hardware_summary = form.hardware_summary.data
        build.is_published = form.is_published.data
        build.is_anonymous = form.publish_as_anonymous.data
        if form.cover_image.data:
            try:
                image_path = save_image(
                    form.cover_image.data,
                    current_app.config["BUILD_IMAGE_SUBDIR"],
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("builds/editor.html", form=form, build=build)
            delete_image(build.cover_image)
            build.cover_image = image_path
        _apply_tags(build, parse_tags(form.tags.data))
        build.components.clear()
        _apply_components(build, form.components.entries)
        db.session.commit()
        evaluate_achievements(current_user)
        flash("Сборка обновлена.", "success")
        return redirect(url_for("builds.mine"))
    return render_template("builds/editor.html", form=form, build=build)


@builds_bp.route("/<int:build_id>/delete", methods=["POST"])
@login_required
def delete(build_id: int):
    build = Build.query.get_or_404(build_id)
    if build.author != current_user:
        abort(403)
    delete_image(build.cover_image)
    for benchmark in build.benchmarks:
        delete_image(benchmark.screenshot_path)
    db.session.delete(build)
    db.session.commit()
    flash("Сборка удалена.", "info")
    return redirect(url_for("builds.mine"))


@builds_bp.route("/<int:build_id>", methods=["GET", "POST"])
def detail(build_id: int):
    build = Build.query.get_or_404(build_id)
    if not build.is_published and (not current_user.is_authenticated or build.author != current_user):
        abort(404)

    comment_form = CommentForm(prefix="comment")
    rating_form = RatingForm(prefix="rating")
    subscribe_form = HiddenIdForm(prefix="subscribe") if build.allow_profile_link() else None
    if request.method == "GET" and subscribe_form:
        subscribe_form.target_id.data = str(build.author_id)

    if request.method == "POST":
        if not current_user.is_authenticated:
            flash("Необходимо войти в аккаунт.", "warning")
            return redirect(url_for("auth.login"))

        if "comment-submit" in request.form and comment_form.validate_on_submit():
            comment = BuildComment(
                content=comment_form.content.data,
                build=build,
                author=current_user,
                is_anonymous=comment_form.is_anonymous.data,
            )
            db.session.add(comment)
            db.session.commit()
            evaluate_achievements(current_user)
            flash("Комментарий добавлен.", "success")
            return redirect(url_for("builds.detail", build_id=build.id))

        if "rating-submit" in request.form and rating_form.validate_on_submit():
            existing = BuildRating.query.filter_by(
                build_id=build.id, reviewer_id=current_user.id
            ).first()
            if existing:
                existing.score = int(rating_form.score.data)
                existing.feedback = rating_form.feedback.data
                existing.is_anonymous = rating_form.is_anonymous.data
            else:
                rating = BuildRating(
                    score=int(rating_form.score.data),
                    feedback=rating_form.feedback.data,
                    build=build,
                    reviewer=current_user,
                    is_anonymous=rating_form.is_anonymous.data,
                )
                db.session.add(rating)
            db.session.commit()
            evaluate_achievements(build.author)
            flash("Спасибо за оценку!", "success")
            return redirect(url_for("builds.detail", build_id=build.id))

        if (
            subscribe_form
            and "subscribe-submit" in request.form
            and subscribe_form.validate_on_submit()
        ):
            author_id = int(subscribe_form.target_id.data)
            if author_id == current_user.id:
                flash("Нельзя подписаться на себя.", "warning")
            else:
                existing = Subscription.query.filter_by(
                    follower_id=current_user.id,
                    followed_id=author_id,
                ).first()
                if existing:
                    db.session.delete(existing)
                    flash("Подписка отменена.", "info")
                else:
                    subscription = Subscription(
                        follower=current_user,
                        followed=build.author,
                    )
                    db.session.add(subscription)
                    flash("Теперь вы следите за этим сборщиком.", "success")
                db.session.commit()
                evaluate_achievements(current_user)
            return redirect(url_for("builds.detail", build_id=build.id))

    is_subscribed = False
    if current_user.is_authenticated and subscribe_form:
        is_subscribed = (
            Subscription.query.filter_by(
                follower_id=current_user.id,
                followed_id=build.author_id,
            ).count()
            > 0
        )
        subscribe_form.target_id.data = str(build.author_id)
    return render_template(
        "builds/detail.html",
        build=build,
        comment_form=comment_form,
        rating_form=rating_form,
        subscribe_form=subscribe_form,
        is_subscribed=is_subscribed,
    )


@main_bp.route("/experts/<int:user_id>")
def expert_profile(user_id: int):
    user = User.query.get_or_404(user_id)
    published_builds = (
        Build.query.filter_by(author_id=user.id, is_published=True)
        .order_by(Build.created_at.desc())
        .all()
    )
    profile = get_gamification_profile(user)
    return render_template(
        "dashboard/expert_profile.html",
        expert=user,
        builds=published_builds,
        profile=profile,
    )


def _apply_tags(build: Build, tag_names: Iterable[str]) -> None:
    build.tags.clear()
    for name in tag_names:
        tag = Tag.query.filter(func.lower(Tag.name) == name.lower()).first()
        if not tag:
            tag = Tag(name=name)
        build.tags.append(tag)
    current_app.logger.debug(
        "Tags updated for build %s: %s", build.id if build.id else "new", tag_names
    )


def _apply_components(build: Build, component_entries: Iterable) -> None:
    for entry in component_entries:
        data = entry.data
        name = (data.get("name") or "").strip()
        if not name:
            continue
        component = BuildComponent(
            name=name,
            dns_price=data.get("dns_price"),
            dns_url=data.get("dns_url"),
            megamarket_price=data.get("megamarket_price"),
            megamarket_url=data.get("megamarket_url"),
            mvideo_price=data.get("mvideo_price"),
            mvideo_url=data.get("mvideo_url"),
        )
        build.components.append(component)
    current_app.logger.debug(
        "Components updated for build %s. Total: %s",
        build.id if build.id else "new",
        len(build.components),
    )
