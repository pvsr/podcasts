from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, create_engine
from sqlalchemy.orm import declarative_base, relationship


def eng():
    return create_engine(
        "sqlite:///podcasts.sqlite",
        echo=True,
        future=True,
    )


Base = declarative_base()


class PodcastDb(Base):
    __tablename__ = "podcast"
    slug = Column(String, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    image = Column(String, nullable=False)
    image_title = Column(String, nullable=False)
    last_ep = Column(DateTime, nullable=False)
    last_fetch = Column(DateTime, nullable=False)

    episodes = relationship("EpisodeDb", back_populates="podcast")

    def last_ep_pretty(self):
        return month_day(self.last_ep)


class EpisodeDb(Base):
    __tablename__ = "episode"
    podcast_slug = Column(
        String,
        ForeignKey("podcast.slug"),
        primary_key=True,
        nullable=False,
    )
    id = Column(String, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    published = Column(DateTime, nullable=False)
    link = Column(String, nullable=False)
    enclosure = Column(String, nullable=False)

    podcast = relationship("PodcastDb", back_populates="episodes")


def create():
    engine = eng()
    Base.metadata.create_all(engine)
    return engine


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
