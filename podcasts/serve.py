from os import environ
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from flask import render_template, send_from_directory
from flask_httpauth import HTTPBasicAuth
from sqlalchemy import desc, select
from werkzeug.security import check_password_hash

from podcasts import PodcastDb, UserDb, app, db
from podcasts.config import Config

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password) -> Optional[UserDb]:
    user = db.session.scalar(select(UserDb).filter_by(name=username))
    if user and check_password_hash(user.password, password):
        return (username, password)
    return None


@app.route("/")
@auth.login_required
def home():
    podcasts = db.session.scalars(
        select(PodcastDb).order_by(desc(PodcastDb.last_ep))
    ).all()
    username, password = auth.current_user()
    login = f"{username}:{password}"
    base_url = urlparse(
        Config.load(Path(environ.get("PODCASTS_DATA_DIR", ""))).base_url
    )
    last_fetch = max(podcasts, key=lambda p: p.last_fetch).last_fetch_pretty()
    return render_template(
        "podcasts.html",
        podcasts=podcasts,
        updated=last_fetch,
        auth_url=base_url._replace(netloc=f"{login}@{base_url.netloc}").geturl(),
    )


@app.route("/<path:path>")
@auth.login_required
def data(path):
    return send_from_directory(
        Path(environ.get("PODCASTS_ANNEX_DIR", "")), path, as_attachment=False
    )
