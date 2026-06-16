import re
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Regexp
from app.extensions import db, limiter
from app.models.user import User
import random

auth_bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")


class RegisterForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(1, 50)])
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(3, 20),
            Regexp(r"^[a-zA-Z0-9_]+$", message="Letters, numbers and underscores only."),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 128)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password")])

    def validate_username(self, field):
        if User.query.filter_by(username=field.data.lower()).first():
            raise ValidationError("Username is already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("An account with that email already exists.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("chat.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data.lower(),
            email=form.email.data.lower(),
            display_name=form.display_name.data.strip(),
            avatar_seed=random.randint(0, 9),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for("chat.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("chat.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page if next_page and next_page.startswith("/") else url_for("chat.index"))
        flash("Invalid username or password.")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
