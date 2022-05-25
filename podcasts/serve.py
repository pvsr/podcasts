from flask import Flask, render_template, url_for
from sqlalchemy import select
from sqlalchemy.orm import Session

from podcasts import db
from podcasts.db import PodcastDb, EpisodeDb

app = Flask(__name__)


@app.route("/")
def home():
    engine = db.create()
    with Session(engine) as session:
        podcasts = session.execute(select(PodcastDb))
        return render_template(
            "podcasts.html", podcasts=podcasts, updated="todo", base_url="todo"
        )
