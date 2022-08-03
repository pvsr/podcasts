from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from flask import abort, make_response, render_template, send_from_directory
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

from podcasts import EpisodeDb, PodcastDb, UserDb, app, db

auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password) -> Optional[tuple[str, str]]:
    user = UserDb.query.filter_by(name=username).first()
    if user and check_password_hash(user.password, password):
        return (username, password)
    return None


@app.route("/")
@app.route("/show/")
@auth.login_required
def home():
    podcasts = PodcastDb.query.order_by(db.desc(PodcastDb.last_ep)).all()
    username, password = auth.current_user()
    login = f"{username}:{password}"
    base_url = urlparse(app.config.get("DOMAIN", ""))
    last_podcast = max(podcasts, key=lambda p: p.last_fetch)
    resp = make_response(
        render_template(
            "podcasts.html",
            podcasts=podcasts,
            updated=last_podcast.last_fetch_pretty(),
            auth_url=base_url._replace(netloc=f"{login}@{base_url.netloc}").geturl(),
        )
    )
    resp.last_modified = last_podcast.last_fetch
    return resp


@app.route("/show/<slug>")
def show(slug: str):
    podcast = PodcastDb.query.filter_by(slug=slug).first()
    if not podcast:
        abort(404)
    episodes = (
        EpisodeDb.query.filter_by(podcast_slug=slug)
        .order_by(EpisodeDb.published.asc())
        .all()
    )
    return render_template("podcast.html", podcast=podcast, episodes=episodes)


@app.route("/<path:path>")
@auth.login_required
def data(path):
    return send_from_directory(
        Path(app.config.get("ANNEX_DIR", "")), path, as_attachment=False
    )
