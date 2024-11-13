import birl
import gleam/dynamic/decode
import gleam/int
import gleam/list
import gleam/option
import gleam/result
import gleam/string
import glrss_parser/rss
import glrss_parser/rss/date
import podcasts/config.{type PodcastConf}
import podcasts/err.{type Err}
import simplifile
import sqlight

pub fn main(input: #(PodcastConf, rss.Rss)) -> Result(String, sqlight.Error) {
  let #(podcast, feed) = input
  let dest = "podcasts/" <> podcast.slug <> ".db"
  sqlight.with_connection(dest, fn(conn) {
    use _ <- result.try(create_podcast_db(conn, podcast, feed))
    use _ <- result.map(
      result.all(
        list.map(feed.channel.item, fn(item) { write_episode(conn, item) }),
      ),
    )
    dest
  })
}

pub type PodcastDb {
  PodcastDb(
    slug: String,
    url: String,
    title: String,
    link: String,
    image: String,
    updated: birl.Time,
    episodes: List(Episode),
  )
}

pub fn load_podcasts() -> Result(List(PodcastDb), Err) {
  use files <- result.try(
    simplifile.read_directory("podcasts")
    |> result.map_error(err.FileErr("podcasts", _)),
  )
  let podcasts =
    list.map(files, fn(file) { "podcasts/" <> file })
    |> list.filter(is_db)
    |> list.map(sqlight.with_connection(_, load_podcast))
  case result.partition(podcasts) {
    #([], []) -> Error(err.NotFoundErr)
    #(oks, []) -> Ok(oks)
    #(_, errs) -> Error(err.Errs(errs))
  }
}

fn load_podcast(conn: sqlight.Connection) -> Result(PodcastDb, Err) {
  use episodes <- result.try(get_episodes(conn) |> result.map_error(err.DbErr))
  use podcasts <- result.try(
    sqlight.query(
      "select
        slug,
        url,
        title,
        link,
        image,
        unixepoch(max((select timestamp from updated)))
      from podcast",
      conn,
      [],
      podcast_decoder(episodes),
    )
    |> result.map_error(err.DbErr),
  )
  list.first(podcasts)
  |> result.replace_error(err.NotFoundErr)
}

pub fn create_podcast_db(
  conn,
  podcast: PodcastConf,
  feed: rss.Rss,
) -> Result(Nil, sqlight.Error) {
  use _ <- result.try(sqlight.exec(
    "create table if not exists updated (
      timestamp text default current_timestamp
    )",
    conn,
  ))
  use _ <- result.try(sqlight.exec(
    "create table if not exists podcast (
      slug text,
      url text,
      title text,
      link text,
      image text
    )",
    conn,
  ))
  use _ <- result.try(sqlight.exec(
    "create table if not exists episode (
      guid text,
      title text,
      link text,
      description text,
      enclosure text,
      length int,
      pub_date int,
      primary key (title)
    );",
    conn,
  ))
  use _ <- result.try(sqlight.exec("insert into updated default values", conn))
  use _ <- result.try(sqlight.exec("delete from podcast", conn))
  use _ <- result.try(sqlight.query(
    "insert into podcast (
      slug,
      url,
      title,
      link,
      image
    ) values (
      ?,
      ?,
      ?,
      ?,
      ?
    )",
    conn,
    [
      sqlight.text(podcast.slug),
      sqlight.text(podcast.rss_url),
      sqlight.text(feed.channel.title),
      sqlight.text(feed.channel.link),
      text_or_empty(feed.channel.image |> option.map(fn(i) { i.url })),
    ],
    decode.success(Nil),
  ))
  Ok(Nil)
}

fn is_db(file: String) {
  string.ends_with(file, ".db")
  && simplifile.is_file(file) |> result.unwrap(False)
}

pub type Episode {
  Episode(
    guid: String,
    title: String,
    link: option.Option(String),
    description: String,
    enclosure: String,
    length: Int,
    pub_date: birl.Time,
  )
}

const episode_columns = "guid,
                        title,
                        link,
                        description,
                        enclosure,
                        length,
                        pub_date"

fn get_episodes(conn) -> Result(List(Episode), sqlight.Error) {
  sqlight.query(
    "select " <> episode_columns <> " from episode",
    conn,
    [],
    episode_decoder(),
  )
}

fn write_episode(
  conn: sqlight.Connection,
  episode: rss.Item,
) -> Result(Nil, sqlight.Error) {
  // TODO when would we want to replace an existing epsiode? we don't?
  sqlight.query("insert into episode (" <> episode_columns <> ") values (
      ?,
      ?,
      ?,
      ?,
      ?,
      ?,
      ?
    ) on conflict do nothing", conn, [
    text_or_empty(episode.guid),
    text_or_empty(episode.title),
    text_or_null(episode.link),
    text_or_empty(episode.description),
    text_or_empty(episode.enclosure |> option.map(fn(e) { e.url })),
    sqlight.int(
      episode.enclosure |> option.map(fn(e) { e.length }) |> option.unwrap(0),
    ),
    sqlight.int(
      episode.pub_date
      |> option.map(date_to_time)
      |> option.map(birl.to_unix)
      |> option.unwrap(0),
    ),
  ], decode.success(Nil))
  |> result.replace(Nil)
}

fn podcast_decoder(episodes) -> decode.Decoder(PodcastDb) {
  use slug <- decode.field(0, decode.string)
  use url <- decode.field(1, decode.string)
  use title <- decode.field(2, decode.string)
  use link <- decode.field(3, decode.string)
  use image <- decode.field(4, decode.string)
  use updated <- decode.field(5, decode.map(decode.int, birl.from_unix))
  decode.success(PodcastDb(
    slug:,
    url:,
    title:,
    link:,
    image:,
    updated:,
    episodes:,
  ))
}

fn episode_decoder() -> decode.Decoder(Episode) {
  use guid <- decode.field(0, decode.string)
  use title <- decode.field(1, decode.string)
  use link <- decode.field(2, decode.optional(decode.string))
  use description <- decode.field(3, decode.string)
  use enclosure <- decode.field(4, decode.string)
  use length <- decode.field(5, decode.int)
  use pub_date <- decode.field(6, decode.map(decode.int, birl.from_unix))
  decode.success(Episode(
    guid:,
    title:,
    link:,
    description:,
    enclosure:,
    length:,
    pub_date:,
  ))
}

fn text_or_empty(value: option.Option(String)) -> sqlight.Value {
  sqlight.text(option.unwrap(value, ""))
}

fn text_or_null(value: option.Option(String)) -> sqlight.Value {
  sqlight.nullable(sqlight.text, value)
}

fn date_to_time(d: date.RssDate) -> birl.Time {
  let assert Ok(time) =
    birl.unix_epoch
    |> birl.set_day(birl.Day(d.year, d.month, d.day))
    |> birl.set_time_of_day(birl.TimeOfDay(d.hour, d.minute, d.second, 0))
    |> birl.set_offset(offset(d.offset_minutes))
  time
}

fn offset(minutes: Int) -> String {
  let hours = minutes / 60
  zeropad2(hours) <> zeropad2(int.absolute_value(minutes) % 60)
}

fn zeropad2(n) {
  let abs = int.absolute_value(n)
  let neg = case n < 0 {
    True -> "-"
    _ -> ""
  }
  neg <> string.pad_start(int.to_string(abs), 2, "0")
}
