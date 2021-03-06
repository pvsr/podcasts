import asyncio
import html
import os
import string
import time
import xml.dom.minidom
from dataclasses import dataclass
from datetime import datetime, timedelta
from operator import attrgetter
from pathlib import Path
from subprocess import run
from typing import Any, Optional, cast

import feedparser
import requests
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert

from podcasts import EpisodeDb, PodcastDb, app, db
from podcasts.config import Config, Podcast


# wrapper around the result of feedparser.parse()
@dataclass
class ParsedFeed:
    feed: Any
    entries: Any


@dataclass
class FeedData:
    slug: str
    raw: str
    url: Optional[str]
    parsed: ParsedFeed
    last_ep: datetime

    @classmethod
    def parse(cls, slug: str, raw: str, url: Optional[str]) -> Optional["FeedData"]:
        parsed = cast(ParsedFeed, feedparser.parse(raw))
        if len(parsed.entries) == 0:
            return None
        return FeedData(
            slug,
            raw,
            url,
            parsed,
            to_datetime(parsed.entries[0].published_parsed),
        )


FILENAME_TEMPLATE = "${itemid}${extension}"


async def fetch_feeds() -> None:
    annex_dir = Path(app.config.get("ANNEX_DIR", ""))
    config = Config.load()
    os.chdir(annex_dir)

    last = {
        row.slug: {
            "old_eps": row.eps,
            "last_fetch": datetime.fromisoformat(row.last_fetch),
        }
        for row in db.session.execute(
            text(
                """
                select p.slug, p.last_fetch, count(*) as eps
                from episode e inner join podcast p on e.podcast_slug = p.slug
                group by podcast_slug"""
            )
        )
    }
    fallback_status = {"old_eps": 0, "last_fetch": None}
    parsed_feeds = await asyncio.gather(
        *[
            asyncio.to_thread(
                process_feed,
                podcast,
                **last.get(podcast.slug, fallback_status),
            )
            for podcast in config.podcasts
        ]
    ) + await asyncio.gather(
        *[
            asyncio.to_thread(
                download_feed,
                podcast,
                last.get(podcast.slug, fallback_status)["last_fetch"],
                podcast.url,
            )
            for podcast in config.passthru
        ]
    )
    feeds = sorted(
        filter(None, parsed_feeds),
        key=attrgetter("last_ep"),
        reverse=True,
    )
    if len(feeds) == 0:
        return
    last_fetch = datetime.now()
    podcasts = [
        PodcastDb(
            slug=feed.slug,
            title=feed.parsed.feed.title,
            image=feed.parsed.feed.image.href,
            image_title=feed.parsed.feed.image.title,
            last_ep=feed.last_ep,
            last_fetch=last_fetch,
            url=feed.url,
            episodes=[
                EpisodeDb(
                    podcast_slug=feed.slug,
                    id=ep.guid,
                    title=ep.title,
                    description=ep.description,
                    published=to_datetime(ep.published_parsed),
                    link=ep.link,
                    enclosure=[link.href for link in ep.links if "audio" in link.type][
                        0
                    ],
                )
                for ep in feed.parsed.entries
            ],
        )
        for feed in feeds
    ]
    insert_stmt = insert(PodcastDb)
    db.session.execute(
        insert_stmt.on_conflict_do_update(
            set_={col: insert_stmt.excluded[col] for col in ["last_ep", "last_fetch"]}
        ),
        [vars(podcast) for podcast in podcasts],
    )
    insert_stmt = insert(EpisodeDb)
    db.session.execute(
        insert_stmt.on_conflict_do_update(
            set_={
                col: insert_stmt.excluded[col]
                for col in ["title", "description", "published", "link", "enclosure"]
            }
        ),
        [vars(episode) for podcast in podcasts for episode in podcast.episodes],
    )
    db.session.commit()


def process_feed(
    podcast: Podcast, old_eps: int, last_fetch: Optional[datetime]
) -> Optional[FeedData]:
    feed = download_feed(podcast, last_fetch)
    if not feed:
        return None

    new_eps = len(feed.parsed.entries)
    if len(feed.parsed.entries) <= old_eps:
        print(
            f"{podcast.slug}: we have {old_eps} while remote has {new_eps}, skipping import"
        )
    else:
        print(f"{podcast.slug}: annexing {podcast.url}")
        annex_cmd = run(
            [
                "git-annex",
                "importfeed",
                podcast.url,
                "--template",
                f"{podcast.slug}/{FILENAME_TEMPLATE}",
                # "--fast",
                # "--force",
            ],
            check=False,
        )
        if annex_cmd.returncode != 0:
            print(f"{podcast.slug}: failed to annex feed")
            return None
        update_feed(podcast.slug, feed)
    return feed


def download_feed(
    podcast: Podcast, last_fetch: Optional[datetime], url: Optional[str] = None
) -> Optional[FeedData]:
    if last_fetch and datetime.now() - last_fetch < timedelta(hours=1):
        print(f"{podcast.slug}: fetched in last hour, continuing")
        return None

    print(f"{podcast.slug}: downloading")
    r = requests.get(podcast.url)
    if r.status_code != 200:
        print(f"{podcast.slug}: failed")
        return None
    if getattr(r, "from_cache", False):
        print(f"{podcast.slug}: cache hit")
    feedtext = r.text
    return FeedData.parse(podcast.slug, feedtext, url)


def update_feed(slug: str, feed: FeedData) -> bool:
    updated = Path(f"{slug}.rss")
    relinked = relink(slug, feed)
    if not relinked:
        print(f"{slug}: failed to update links")
        return False

    print(f"{slug}: saving modified to {updated}")
    with open(updated, "w", encoding="utf-8") as f:
        print(pretty_rss(relinked), file=f)
    return True


def relink(slug: str, feed: FeedData) -> Optional[str]:
    replacements = {}
    for entry in feed.parsed.entries:
        if not entry.guid:
            print("no guids in f{original}")
            return None
        for link in entry.links:
            if "audio" in link.type:
                filename = git_annex_sanitize_filename(entry.guid)
                replacements[
                    link.href
                ] = f"{app.config.get('DOMAIN', '')}/{slug}/{filename}.mp3"
    raw = feed.raw
    for old, new in replacements.items():
        # print(f"replacing {old} with {new}")
        raw = raw.replace(html.escape(old), new)
    return raw


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


def pretty_rss(raw: str) -> xml.dom.minidom.Document:
    return strip_cruft(xml.dom.minidom.parseString(raw)).toprettyxml()


def strip_cruft(feed_xml: xml.dom.minidom.Document) -> xml.dom.minidom.Document:
    for tag in Config.load().tags_to_strip:
        for node in feed_xml.getElementsByTagName(tag):
            node.parentNode.removeChild(node)
    return feed_xml


def to_datetime(t: time.struct_time) -> datetime:
    return datetime.fromtimestamp(time.mktime(t))


def main():
    Config.load(Path(app.config.get("DATA_DIR"), ""))
    db.create_all()
    asyncio.run(fetch_feeds())
    db.session.commit()
    run(["git-annex", "status"], check=False)


if __name__ == "__main__":
    main()
