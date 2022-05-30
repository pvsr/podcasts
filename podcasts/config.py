from dataclasses import dataclass
from functools import cache
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
    base_url: str
    auth_url: str
    tags_to_strip: list[str]
    podcasts: list[Podcast]


@cache
def load_config(file: Path = Path("podcasts.yml")) -> Config:
    with open(file) as f:
        return dacite.from_dict(
            Config,
            yaml.safe_load(f),
            dacite.Config(type_hooks={list[Podcast]: to_podcasts}),
        )


def to_podcasts(slug_to_url: dict) -> list[Podcast]:
    return [Podcast(*podcast) for podcast in slug_to_url.items()]
