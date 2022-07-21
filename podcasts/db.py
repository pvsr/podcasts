from datetime import datetime
from os import environ
from pathlib import Path
from sys import exit
from typing import Optional

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f'sqlite:///{Path(environ.get("PODCASTS_DATA_DIR", "")).resolve()/"podcasts.sqlite"}'
db = SQLAlchemy(app)


class PodcastDb(db.Model):
    __tablename__ = "podcast"
    slug = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    image = db.Column(db.String, nullable=False)
    image_title = db.Column(db.String, nullable=False)
    last_ep = db.Column(db.DateTime, nullable=False)
    last_fetch = db.Column(db.DateTime, nullable=False)

    episodes = db.relationship("EpisodeDb", back_populates="podcast")

    def last_ep_pretty(self):
        return month_day(self.last_ep)


class EpisodeDb(db.Model):
    __tablename__ = "episode"
    podcast_slug = db.Column(
        db.String,
        db.ForeignKey("podcast.slug"),
        primary_key=True,
        nullable=False,
    )
    id = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False)
    published = db.Column(db.DateTime, nullable=False)
    link = db.Column(db.String, nullable=False)
    enclosure = db.Column(db.String, nullable=False)

    podcast = db.relationship("PodcastDb", back_populates="episodes")


class UserDb(db.Model):
    __tablename__ = "user"
    name = db.Column(db.String, primary_key=True, nullable=False)
    password = db.Column(db.String, nullable=False)


def month_day(t: datetime) -> str:
    return f"{t:%b %-d}{month_day_suffix(t)}{year(t)}"


def month_day_suffix(t: datetime) -> str:
    day = t.day
    if day in (11, 12, 13):
        return "th"

    lsd = day % 10
    if lsd == 1:
        return "st"
    if lsd == 2:
        return "nd"
    if lsd == 3:
        return "rd"
    return "th"


def year(t: datetime) -> str:
    now = datetime.now()
    return "" if t.year == now.year else f" {t.year}"
