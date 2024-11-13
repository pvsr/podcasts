import gleam/bit_array
import gleam/hackney
import gleam/http/request
import gleam/io
import gleam/list
import gleam/option
import gleam/result
import gleam/uri
import podcasts/config.{type PodcastConf}
import shellout
import simplifile

pub type DownloadError {
  HttpStatusError(#(Int, String))
  FeedFetchError(hackney.Error)
  ArchiveError(#(Int, String))
  WriteError(simplifile.FileError)
}

pub fn archive(
  podcasts: List(PodcastConf),
) -> List(Result(String, DownloadError)) {
  let download_dir = "podcasts"
  let assert Ok(run) = shellout.which("podcast-archiver")
  let downloads = download_feeds(podcasts, download_dir)
  list.map(downloads, fn(download) {
    let #(podcast, path) = download
    use path <- result.try(path)
    shellout.command(run:, with: archive_args(podcast), in: download_dir, opt: [
      shellout.LetBeStdout,
      shellout.SetEnvironment([#("FORCE_COLOR", "1")]),
    ])
    |> result.replace(path)
    |> result.map_error(ArchiveError)
  })
}

pub fn download_feeds(
  podcasts: List(PodcastConf),
  download_dir: String,
) -> List(#(PodcastConf, Result(String, DownloadError))) {
  let assert Ok(_) = simplifile.create_directory_all(download_dir)
  use podcast <- list.map(podcasts)
  #(podcast, download_feed(podcast, download_dir))
}

fn download_feed(
  podcast: PodcastConf,
  download_dir: String,
) -> Result(String, DownloadError) {
  let assert Ok(req) = request.to(podcast.upstream)
  let assert Ok(uri) = uri.parse(podcast.upstream)
  let req = case auth_header(uri) {
    option.None -> req
    option.Some(auth) -> request.set_header(req, "authorization", auth)
  }
  let req =
    req
    |> request.set_header("user-agent", "pvsr/podcasts/0.0.1")
  // |> request.set_header("accept", "*/*")
  // |> request.set_header("content-type", "")
  // |> request.set_header("content-length", "1")
  // |> request.set_body("asdf")
  use resp <- result.try(
    hackney.send(req)
    |> result.map_error(fn(e) { FeedFetchError(e) }),
  )
  case resp.status {
    200 -> {
      let path = download_dir <> "/" <> podcast.slug <> ".rss"
      simplifile.write(path, resp.body)
      |> result.map_error(WriteError)
      |> result.replace(path)
    }
    _ -> {
      io.debug(req)
      Error(HttpStatusError(#(resp.status, resp.body)))
    }
  }
}

fn auth_header(url: uri.Uri) {
  use userinfo <- option.map(url.userinfo)
  "Basic "
  <> userinfo
  |> bit_array.from_string
  |> bit_array.base64_encode(True)
}

fn archive_args(podcast: PodcastConf) {
  [
    // "--config",
    // "./config.yaml",
    "--debug-partial",
    "--feed",
    "file:///home/peter/dev/podcasts/podcasts/" <> podcast.slug <> ".rss",
    "--filename-template",
    // podcast.slug <> "/{episode.original_filename}",
    podcast.slug <> "/{episode.published_time:%Y-%m-%d} - {episode.title}.{ext}",
  ]
}
