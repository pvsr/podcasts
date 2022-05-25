from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    ForeignKey,
    create_engine,
)
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
    last_ep = Column(DateTime, nullable=False)
    last_fetch = Column(DateTime, nullable=False)

    episodes = relationship("EpisodeDb", back_populates="podcast")


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
