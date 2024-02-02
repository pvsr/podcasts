import string
from datetime import datetime
from pathlib import Path

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config.from_prefixed_env("PODCASTS")
app.config.update(
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{Path(app.config.get("DATA_DIR", ""))/"podcasts.sqlite"}',
)
db = SQLAlchemy(app)


class PodcastDb(db.Model):
    __tablename__ = "podcast"
    slug = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    image = db.Column(db.String, nullable=False)
    image_title = db.Column(db.String, nullable=False)
    last_ep = db.Column(db.DateTime, nullable=False)
    last_fetch = db.Column(db.DateTime, nullable=True)
    url = db.Column(db.String, nullable=True)

    episodes = db.relationship("EpisodeDb", back_populates="podcast")

    def last_ep_pretty(self) -> str:
        return month_day(self.last_ep)

    def last_fetch_pretty(self) -> str:
        return month_day_time(self.last_fetch)


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
    link = db.Column(db.String, nullable=True)
    enclosure = db.Column(db.String, nullable=False)

    podcast = db.relationship("PodcastDb", back_populates="episodes")

    def href(self, archived: bool) -> str:
        return (
            f"/{self.podcast_slug}/{git_annex_sanitize_filename(self.id)}.mp3"
            if archived
            else self.enclosure
        )


class UserDb(db.Model):
    __tablename__ = "user"
    name = db.Column(db.String, primary_key=True, nullable=False)
    password = db.Column(db.String, nullable=False)


def month_day(t: datetime) -> str:
    return f"{t:%b %-d}{month_day_suffix(t)}{year(t)}"


def month_day_time(t: datetime) -> str:
    return f"{t:%b %-d}{month_day_suffix(t)}{year(t)} {t:%R}"


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


def git_annex_sanitize_filename(filename: str) -> str:
    if not filename:
        return filename
    return "".join(sanitize_char(c) for c in filename)


def sanitize_char(char: str) -> str:
    # todo
    if char in [".", "-"]:
        return char
    if char in string.punctuation or char in string.whitespace:
        return "_"
    return char


# sanitizeFilePath :: String -> FilePath
# sanitizeFilePath = sanitizeLeadingFilePathCharacter . sanitizeFilePathComponent

# {- For when the filepath is being built up out of components that should be
#  - individually sanitized, this can be used for each component, followed by
#  - sanitizeLeadingFilePathCharacter for the whole thing.
#  -}
# sanitizeFilePathComponent :: String -> String
# sanitizeFilePathComponent = map sanitize
#   where
# 	sanitize c
# 		| c == '.' || c == '-' = c
# 		| isSpace c || isPunctuation c || isSymbol c || isControl c || c == '/' = '_'
# 		| otherwise = c

# sanitizeLeadingFilePathCharacter :: String -> FilePath
# sanitizeLeadingFilePathCharacter [] = "file"
# sanitizeLeadingFilePathCharacter ('.':s) = '_':s
# sanitizeLeadingFilePathCharacter ('-':s) = '_':s
# sanitizeLeadingFilePathCharacter ('/':s) = '_':s
# sanitizeLeadingFilePathCharacter s = s
