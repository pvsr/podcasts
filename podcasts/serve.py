from flask import Flask, render_template
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from podcasts import db
from podcasts.db import PodcastDb

app = Flask(__name__)


@app.route("/")
def home():
    engine = db.create()
    with Session(engine) as session:
        podcasts = session.scalars(
            select(PodcastDb).order_by(desc(PodcastDb.last_ep))
        ).all()
        return render_template(
            "podcasts.html", podcasts=podcasts, updated="todo", base_url="todo"
        )
