import gleam/list
import gleam/pair
import gleam/result
import simplifile
import tom

pub type PodcastConf {
  PodcastConf(slug: String, upstream: String, rss_url: String, passthru: Bool)
}

pub fn load_podcasts() -> #(String, List(PodcastConf)) {
  let assert Ok(text) = simplifile.read("podcasts.toml")
  let assert Ok(parsed) = tom.parse(text)
  let assert Ok(base_url) = tom.get_string(parsed, ["base_url"])
  let assert Ok(podcasts) = tom.get_array(parsed, ["podcasts"])

  list.map(podcasts, fn(item) {
    let assert tom.Table(podcast) = item
    let assert Ok(slug) = tom.get_string(podcast, ["slug"])
    let assert Ok(upstream) = tom.get_string(podcast, ["url"])
    let passthru =
      tom.get_bool(parsed, ["passthru"])
      |> result.unwrap(False)
    let url = case passthru {
      True -> upstream
      _ -> base_url <> "/" <> slug <> ".rss"
    }
    PodcastConf(slug, upstream, url, passthru)
  })
  |> pair.new(base_url, _)
}
