import gleam/function
import gleam/io
import gleam/list
import gleam/pair
import gleam/result
import gleam/set
import gleam/string
import glrss_parser/rss
import podcasts/config
import podcasts/db
import podcasts/edownload
import podcasts/err.{type Err}
import podcasts/render
import simplifile

pub fn main() {
  let #(_base_url, podcasts) = config.load_podcasts()
  let oks =
    edownload.archive(podcasts)
    |> list.map(result.map_error(_, err.DownloadErr))
    |> list.zip(podcasts, _)
    |> eject_pair_errors
    |> list.filter(fn(podcast) { string.ends_with(podcast.1, ".rss") })
    |> list.map(fn(podcast) {
      use file <- pair.map_second(podcast)
      use text <- result.try(
        result.map_error(simplifile.read(file), err.FileErr(file, _)),
      )
      text
      |> rss.parse(skip_unknown_tags: True)
      |> result.map_error(err.RssParseErr)
      // |> result.map(db.main)
      // |> result.map_error(err.DbErr)
    })
    |> eject_pair_errors
    |> list.map(fn(feed) {
      result.map(db.main(feed), fn(dest) {
        io.println("wrote " <> dest)
        feed
      })
      |> result.map_error(err.DbErr)
    })
    |> eject_errors(function.identity)
    |> list.map(pair.first)
    |> list.map(fn(p) { p.slug })
    |> set.from_list
  db.load_podcasts()
  |> result.map(list.filter(_, fn(p) { set.contains(oks, p.slug) }))
  |> result.try(render.render)
  |> result.map(eject_errors(_, function.identity))
  |> result.map(print_all)
  |> result.map_error(err.to_string)
  |> result.map_error(io.println_error)
}

fn eject_pair_errors(results: List(#(a, Result(b, Err)))) -> List(#(a, b)) {
  use entry <- eject_errors(results)
  use ok <- result.map(entry.1)
  #(entry.0, ok)
}

fn eject_errors(results: List(a), to_result: fn(a) -> Result(b, Err)) -> List(b) {
  let #(oks, errs) = result.partition(list.map(results, to_result))
  list.each(errs, fn(err) {
    err
    |> err.to_string
    |> io.println_error
  })
  oks
}

fn print_all(downloads: List(String)) -> Nil {
  use download <- list.each(downloads)
  io.println("wrote " <> download)
}
