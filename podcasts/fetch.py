import asyncio
import html
import os
import time
import xml.dom.minidom
from collections import defaultdict
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

from podcasts import EpisodeDb, PodcastDb, app, db, git_annex_sanitize_filename
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
    url: str | None
    parsed: ParsedFeed
    last_ep: datetime

    @classmethod
    def parse(cls, slug: str, raw: str, url: str | None) -> Optional["FeedData"]:
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

    rows = db.session.execute(
        text(
            """
            select e.id, p.slug, p.last_fetch
            from episode e inner join podcast p on e.podcast_slug = p.slug
            where p.url is null"""
        )
    )

    present = {f"{e.parent.name}/{e.stem}" for e in Path(annex_dir).glob("*/*")}

    last_fetch: dict[str, datetime] = {}
    old_eps: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        last_fetch.setdefault(row.slug, datetime.fromisoformat(row.last_fetch))
        if f"{row.slug}/{git_annex_sanitize_filename(row.id)}" in present:
            old_eps[row.slug].add(row.id)

    parsed_feeds = await asyncio.gather(
        *[
            asyncio.to_thread(
                process_feed,
                podcast,
                old_eps[podcast.slug],
                last_fetch.get(podcast.slug, None),
            )
            for podcast in config.podcasts
        ],
        *[
            asyncio.to_thread(
                download_feed,
                podcast,
                max(last_fetch.values()),
                podcast.url,
            )
            for podcast in config.passthru
        ],
    )
    feeds = sorted(
        filter(None, parsed_feeds),
        key=attrgetter("last_ep"),
        reverse=True,
    )
    if len(feeds) == 0:
        return
    now = datetime.now()
    podcasts = [
        PodcastDb(
            slug=feed.slug,
            title=feed.parsed.feed.title,
            image=feed.parsed.feed.image.href,
            image_title=feed.parsed.feed.image.title,
            last_ep=feed.last_ep,
            last_fetch=now,
            url=feed.url,
            episodes=[
                EpisodeDb(
                    podcast_slug=feed.slug,
                    id=ep.guid,
                    title=ep.title,
                    description=ep.description,
                    published=to_datetime(ep.published_parsed),
                    link=ep.get("link"),
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
    podcast: Podcast, old_eps: set[str], last_fetch: datetime | None
) -> FeedData | None:
    feed = download_feed(podcast, last_fetch)
    if not feed:
        return None

    feed_eps = {ep.id for ep in feed.parsed.entries}
    new_eps = feed_eps - old_eps
    if len(new_eps) == 0:
        print(f"{podcast.slug}: no new episodes, skipping import")
    elif len(old_eps - feed_eps) > 0:
        print(f"{podcast.slug}: existing episodes are missing, skipping import")
    else:
        print(f"{podcast.slug}: new episodes: {new_eps}")
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
    podcast: Podcast, last_fetch: datetime | None, url: str | None = None
) -> FeedData | None:
    if last_fetch and datetime.now() - last_fetch < timedelta(hours=1):
        print(f"{podcast.slug}: fetched in last hour, continuing")
        return None

    print(f"{podcast.slug}: downloading")
    r = requests.get(podcast.url, timeout=20)
    if r.status_code != 200:
        print(f"{podcast.slug}: failed with status code {r.status_code}")
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
    run(["git", "add", updated], check=False)
    return True


def relink(slug: str, feed: FeedData) -> str | None:
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


def pretty_rss(raw: str) -> str:
    return strip_cruft(xml.dom.minidom.parseString(raw)).toprettyxml()


def strip_cruft(feed_xml: xml.dom.minidom.Document) -> xml.dom.minidom.Document:
    for tag in Config.load().tags_to_strip:
        for node in feed_xml.getElementsByTagName(tag):
            node.parentNode.removeChild(node)
    return feed_xml


def to_datetime(t: time.struct_time) -> datetime:
    return datetime.fromtimestamp(time.mktime(t))


def main() -> None:
    Config.load(Path(app.config.get("DATA_DIR", "")))
    with app.app_context():
        db.create_all()
        asyncio.run(fetch_feeds())
        db.session.commit()
    run(["git-annex", "status"], check=False)


if __name__ == "__main__":
    main()
