from os import environ
from pathlib import Path
from typing import Optional

from flask import render_template, send_from_directory
from flask_httpauth import HTTPBasicAuth
from sqlalchemy import desc, select
from werkzeug.security import check_password_hash

from podcasts.db import PodcastDb, UserDb, app, db

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password) -> Optional[UserDb]:
    user = db.session.scalar(select(UserDb).filter_by(name=username))
    if user and check_password_hash(user.password, password):
        return user
    return None


@app.route("/")
@auth.login_required
def home():
    podcasts = db.session.scalars(
        select(PodcastDb).order_by(desc(PodcastDb.last_ep))
    ).all()
    return render_template(
        "podcasts.html", podcasts=podcasts, updated="todo", base_url=""
    )


@app.route("/<path:path>")
@auth.login_required
def data(path):
    return send_from_directory(
        Path(environ.get("PODCASTS_ANNEX_DIR", "")), path, as_attachment=False
    )
