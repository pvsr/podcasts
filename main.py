import html
import os
import time
import xml.dom.minidom
from operator import attrgetter
from pathlib import Path
from shutil import move
from subprocess import run
from tempfile import NamedTemporaryFile
from typing import Any, Callable, IO, Iterable, NamedTuple, Optional, Tuple, cast

import feedparser
import requests
import yaml


class ParsedFeed(NamedTuple):
    feed: Any
    entries: Any


FeedData = Tuple[str, ParsedFeed]


class IndexFeed(NamedTuple):
    last_ep: time.struct_time
    write_to_index: Callable[[IO[str]], None]


class Podcast(NamedTuple):
    slug: str
    url: str

    def title(self) -> str:
        return self.slug.replace("-", " ").title()


class Config(NamedTuple):
    base_url: str
    tags_to_strip: Iterable[str]


CONFIG: Config
FILENAME_TEMPLATE = "${itemid}${extension}"


def main() -> None:
    with open("podcasts.yml") as f:
        config = yaml.safe_load(f)
        podcasts = [Podcast(slug, url) for slug, url in config["podcasts"].items()]
        del config["podcasts"]
        global CONFIG
        CONFIG = Config(**config)
    os.chdir("/home/peter/annex/hosted-podcasts")
    index = NamedTemporaryFile(mode="w", dir=Path(), delete=False)
    print(
        """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="podcasts">""",
        file=index,
    )
    feeds = sorted(
        filter(None, map(process_feed, podcasts)),
        key=attrgetter("last_ep"),
        reverse=True,
    )
    for feed in feeds:
        feed.write_to_index(index)
    print(
        f"""
</div>
<h2>Updated: {time.strftime(f"{month_day()} %H:%M")}</h2>
</body>
</html>""",
        file=index,
    )
    move(index.name, Path("index.html"))


def process_feed(podcast: Podcast) -> Optional[IndexFeed]:
    old = Path(f"{podcast.slug}.rss")
    old_eps = len(feedparser.parse(old).entries)
    print(f"{podcast.slug}: downloading {podcast.url}")
    feed = download_feed(podcast)
    if not feed:
        print(f"{podcast.slug}: couldn't download {podcast.url}, continuing")
        return None

    new_eps = len(feed[1].entries)
    if len(feed[1].entries) <= old_eps:
        print(
            f"{podcast.slug}: we have {old_eps} while remote has {new_eps}, continuing"
        )
    else:
        update_feed(podcast.slug, feed)
        print(f"{podcast.slug}: annexing {podcast.url}")
        run(
            [
                "git-annex",
                "importfeed",
                podcast.url,
                "--template",
                f"{podcast.slug}/{FILENAME_TEMPLATE}",
                # "--fast",
                # "--force",
            ],
            capture_output=True,
            check=True,
        )
    return append_to_index(podcast, feed[1])


def download_feed(podcast: Podcast) -> Optional[FeedData]:
    r = requests.get(podcast.url)
    if r.status_code != 200:
        print(f"{podcast.slug}: failed to fetch {podcast.url}")
        return None

    parsed = cast(ParsedFeed, feedparser.parse(r.text))
    if len(parsed.entries) == 0:
        print(f"{podcast.slug}: no episodes")
        return None
    return (r.text, parsed)


def update_feed(slug: str, feed: FeedData) -> bool:
    updated = Path(f"{slug}.rss")
    relinked = relink(slug, feed)
    if not relinked:
        print(f"{slug}: failed to update links")
        return False

    print(f"{slug}: saving modified to {updated}")
    with open(updated, "w") as f:
        print(pretty_rss(relinked), file=f)
    return True


def relink(slug: str, feed: FeedData) -> Optional[str]:
    replacements = {}
    for entry in feed[1].entries:
        if not entry.guid:
            print("no guids in f{original}")
            return None
        for link in entry.links:
            if "audio" in link.type:
                replacements[link.href] = f"{CONFIG.base_url}/{slug}/{entry.guid}.mp3"
    raw = feed[0]
    for old, new in replacements.items():
        # print(f"replacing {old} with {new}")
        raw = raw.replace(html.escape(old), new)
    return raw


def pretty_rss(raw: str) -> xml.dom.minidom.Document:
    return strip_cruft(xml.dom.minidom.parseString(raw)).toprettyxml()


def strip_cruft(feed_xml: xml.dom.minidom.Document) -> xml.dom.minidom.Document:
    for tag in CONFIG.tags_to_strip:
        for node in feed_xml.getElementsByTagName(tag):
            node.parentNode.removeChild(node)
    return feed_xml


def append_to_index(podcast: Podcast, parsed: ParsedFeed) -> IndexFeed:
    feed = parsed.feed
    last = parsed.entries[0].published_parsed

    def append(index: IO[str]) -> None:
        print("<div>", file=index)
        if feed.image and feed.image.href:
            print(f"<img src='{feed.image.href}' alt='{feed.image.title}'>", file=index)

        print("<div>", file=index)
        print(f"<h1>{podcast.title() or feed.title}</h1>", file=index)
        print(f"<h2>latest episode: {month_day(last)}{year(last)}</h2>", file=index)
        print(f"<p><a href='{podcast.slug}.rss'>RSS feed</a></p>", file=index)
        print("</div>", file=index)
        print("</div>", file=index)

    return IndexFeed(last, append)


def month_day(t: time.struct_time = time.localtime()) -> str:
    day = f"{t.tm_mday}{month_day_suffix(t.tm_mday)}"
    return time.strftime(f"%b {day}", t)


def month_day_suffix(day: int) -> str:
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


def year(t: Optional[time.struct_time] = None) -> str:
    local = time.localtime()
    t = t or local
    return "" if t.tm_year == local.tm_year else f" {t.tm_year % 2000}"


if __name__ == "__main__":
    main()
