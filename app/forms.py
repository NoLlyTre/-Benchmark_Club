import re
from typing import Any

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DecimalField,
    FieldList,
    FloatField,
    FormField,
    HiddenField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)


PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")


class PhoneNumberField(StringField):
    def pre_validate(self, form: FlaskForm) -> None:
        if self.data and not PHONE_PATTERN.match(self.data):
            raise ValidationError("Введите корректный номер телефона.")


class RegistrationForm(FlaskForm):
    phone_number = PhoneNumberField(
        "Номер телефона",
        validators=[DataRequired(), Length(min=10, max=15)],
    )
    display_name = StringField(
        "Отображаемое имя", validators=[DataRequired(), Length(min=2, max=80)]
    )
    email = StringField("Email", validators=[Optional(), Email()])
    password = PasswordField(
        "Пароль", validators=[DataRequired(), Length(min=6, max=120)]
    )
    confirm_password = PasswordField(
        "Подтвердите пароль",
        validators=[DataRequired(), EqualTo("password", message="Пароли не совпадают.")],
    )
    submit = SubmitField("Зарегистрироваться")


class LoginForm(FlaskForm):
    phone_number = PhoneNumberField(
        "Номер телефона",
        validators=[DataRequired(), Length(min=10, max=15)],
    )
    password = PasswordField("Пароль", validators=[DataRequired()])
    remember_me = BooleanField("Запомнить меня")
    submit = SubmitField("Войти")


class ComponentEntryForm(FlaskForm):
    class Meta:
        csrf = False

    name = StringField("Наименование", validators=[Optional(), Length(max=120)])
    dns_price = DecimalField("Цена DNS", validators=[Optional()], places=2)
    dns_url = StringField("Ссылка DNS", validators=[Optional(), Length(max=255)])
    megamarket_price = DecimalField("Цена Мегамаркет", validators=[Optional()], places=2)
    megamarket_url = StringField(
        "Ссылка Мегамаркет", validators=[Optional(), Length(max=255)]
    )
    mvideo_price = DecimalField("Цена М.Видео", validators=[Optional()], places=2)
    mvideo_url = StringField(
        "Ссылка М.Видео", validators=[Optional(), Length(max=255)]
    )


class BuildForm(FlaskForm):
    title = StringField("Название сборки", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField(
        "Описание идеи", validators=[DataRequired(), Length(min=10)]
    )
    hardware_summary = TextAreaField(
        "Конфигурация железа", validators=[DataRequired(), Length(min=10)]
    )
    tags = StringField(
        "Теги",
        description="Введите теги через запятую (например: Игровой монстр)",
    )
    is_published = BooleanField("Опубликовать в клубе?")
    publish_as_anonymous = BooleanField("Показать сборку анонимно")
    cover_image = FileField(
        "Обложка сборки",
        validators=[
            Optional(),
            FileAllowed(["png", "jpg", "jpeg", "gif", "webp"], "Поддерживаемые форматы: png, jpg, gif, webp"),
        ],
    )
    components = FieldList(
        FormField(ComponentEntryForm),
        min_entries=3,
        max_entries=20,
        label="Комплектующие",
    )
    submit = SubmitField("Сохранить сборку")


class CommentForm(FlaskForm):
    content = TextAreaField(
        "Комментарий", validators=[DataRequired(), Length(min=3, max=800)]
    )
    is_anonymous = BooleanField("Оставить комментарий анонимно")
    submit = SubmitField("Отправить")


class RatingForm(FlaskForm):
    score = SelectField(
        "Оценка",
        choices=[
            ("1", "1 - Нужна доработка"),
            ("2", "2 - Есть вопросы"),
            ("3", "3 - Неплохо"),
            ("4", "4 - Отличная сборка"),
            ("5", "5 - Легенда!"),
        ],
        validators=[DataRequired()],
    )
    feedback = TextAreaField("Отзыв", validators=[Optional(), Length(max=500)])
    is_anonymous = BooleanField("Оставить оценку анонимно")
    submit = SubmitField("Оценить")


class BenchmarkForm(FlaskForm):
    build_id = SelectField("Выберите сборку", coerce=int, validators=[Optional()])
    custom_build_name = StringField(
        "Название сборки (если не из списка)", validators=[Optional(), Length(max=120)]
    )
    benchmark_name = StringField(
        "Название бенчмарка", validators=[DataRequired(), Length(max=120)]
    )
    score = FloatField("Результат", validators=[DataRequired()])
    notes = TextAreaField("Заметки", validators=[Optional(), Length(max=500)])
    screenshot = FileField(
        "Скриншот / фото",
        validators=[
            Optional(),
            FileAllowed(["png", "jpg", "jpeg", "gif", "webp"], "Поддерживаемые форматы: png, jpg, gif, webp"),
        ],
    )
    is_anonymous = BooleanField("Публиковать результат анонимно")
    submit = SubmitField("Сохранить результат")

    def validate(self, extra_validators: dict[str, list[Any]] | None = None) -> bool:
        if not super().validate(extra_validators=extra_validators):
            return False
        if not self.build_id.data and not self.custom_build_name.data:
            self.build_id.errors.append(
                "Выберите сборку или укажите её название вручную."
            )
            return False
        return True


class ProfileForm(FlaskForm):
    display_name = StringField(
        "Отображаемое имя", validators=[DataRequired(), Length(min=2, max=80)]
    )
    email = StringField("Email", validators=[Optional(), Email()])
    bio = TextAreaField("О себе", validators=[Optional(), Length(max=800)])
    submit = SubmitField("Обновить профиль")


class HiddenIdForm(FlaskForm):
    target_id = HiddenField(validators=[DataRequired()])
    submit = SubmitField("Подтвердить")


def parse_tags(raw_tags: str | None) -> list[str]:
    if not raw_tags:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for tag in (t.strip() for t in raw_tags.split(",") if t.strip()):
        normalized = tag.lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(tag)
    return result
