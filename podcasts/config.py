from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import dacite
import yaml


@dataclass
class Podcast:
    slug: str
    url: str

    def title(self) -> str:
        return self.slug.replace("-", " ").title()


@dataclass
class Config:
    tags_to_strip: list[str]
    podcasts: list[Podcast]
    passthru: list[Podcast]
    _instance: Optional["Config"] = None

    @classmethod
    def load(cls, data_dir: Optional[Path] = None) -> "Config":
        data_dir = data_dir or Path(".")
        if not cls._instance:
            cls._instance = open_config(data_dir)
        return cls._instance


def open_config(data_dir: Path) -> Config:
    with open(data_dir / "podcasts.yml", encoding="utf-8") as f:
        return dacite.from_dict(
            Config,
            yaml.safe_load(f),
            dacite.Config(type_hooks={list[Podcast]: to_podcasts}),
        )


def to_podcasts(slug_to_url: dict) -> list[Podcast]:
    return [Podcast(*podcast) for podcast in slug_to_url.items()]
