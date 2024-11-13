import birl
import gleam/dict
import gleam/int
import gleam/list
import gleam/result
import gleam/string_tree
import glemplate/assigns
import glemplate/ast.{type Template}
import glemplate/html
import glemplate/parser
import podcasts/db.{type PodcastDb}
import podcasts/err.{type Err}
import simplifile

pub fn render(
  podcasts: List(PodcastDb),
) -> Result(List(Result(String, Err)), Err) {
  let p = parser.new()
  let template = fn(path) { parse_template("templates/" <> path, path, p) }
  use show <- result.try(template("podcast.html"))
  use shows <- result.map(template("podcasts.html"))
  let results = list.map(podcasts, fn(feed) { render_show(show, feed) })
  [render_shows(shows, podcasts), ..results]
}

fn render_show(template, podcast: PodcastDb) -> Result(String, Err) {
  let dest_dir = "rendered/show/" <> podcast.slug
  use _ <- result.try(
    simplifile.create_directory_all(dest_dir)
    |> result.map_error(err.FileErr(dest_dir, _)),
  )
  let dest = dest_dir <> ".html"
  render_template(template, show_inputs(podcast), dest)
  |> result.replace(dest)
}

type Order {
  Added
}

fn render_shows(template, podcasts: List(PodcastDb)) -> Result(String, Err) {
  let order = Added
  let podcasts = case order {
    Added -> list.reverse(podcasts)
  }
  use podcasts <- result.try(case podcasts {
    [] -> Error(err.NotFoundErr)
    _ -> Ok(podcasts)
  })
  let dest = "rendered/index.html"
  render_template(
    template,
    list.map(podcasts, show_inputs)
      |> list.map(assigns.Dict)
      |> assigns.add_list(assigns.new(), "podcasts", _),
    dest,
  )
  |> result.replace(dest)
}

fn show_inputs(podcast: PodcastDb) -> dict.Dict(String, assigns.AssignData) {
  // let assert option.Some(image) = podcast.image
  assigns.new()
  |> assigns.add_string("title", podcast.title)
  |> assigns.add_string("slug", podcast.slug)
  |> assigns.add_string("url", podcast.link)
  |> assigns.add_string("rss_url", podcast.url)
  |> assigns.add_string("image", podcast.image)
  |> assigns.add_string("updated", date_to_string(podcast.updated))
  |> assigns.add_string(
    "last_ep",
    podcast.episodes
      |> list.first
      |> result.map(fn(e) { e.pub_date })
      |> result.map(date_to_string)
      |> result.unwrap("none"),
  )
  |> assigns.add_list(
    "episodes",
    list.map(podcast.episodes, fn(item) {
      assigns.new()
      |> assigns.add_string("title", item.title)
      |> assigns.add_string("url", item.enclosure)
      // |> assigns.add_string("url", case podcast.passthru {
      //   True | False ->
      //     item.enclosure
      //     |> option.map(fn(e) { e.url })
      //     |> option.unwrap("no url")
      // TODO
      // False -> podcast.rss_url <> { option.unwrap(item.guid, "") } <> ".mp3"
      // })
      |> assigns.Dict
    }),
  )
}

fn render_template(template: Template, inputs, dest: String) -> Result(Nil, Err) {
  use rendered <- result.try(
    html.render(template, inputs, dict.new())
    |> result.map_error(err.RenderErr),
  )
  string_tree.to_string(rendered)
  |> simplifile.write(to: dest)
  |> result.map_error(err.FileErr(dest, _))
}

fn parse_template(file: String, name: String, parser) -> Result(Template, Err) {
  use text <- result.try(
    simplifile.read(file)
    |> result.map_error(err.FileErr(file, _)),
  )
  parser.parse_to_template(text, name, parser)
  |> result.map_error(err.TemplateParseErr)
}

fn date_to_string(d: birl.Time) -> String {
  let day = birl.get_day(d)
  let date = day.date
  birl.short_string_month(d)
  <> " "
  <> int.to_string(date)
  <> case date {
    11 | 12 | 13 -> "th"
    _ ->
      case date % 10 {
        1 -> "st"
        2 -> "nd"
        3 -> "rd"
        _ -> "th"
      }
  }
  // <> case d.day, d.day % 10 {
  //   11, _ | 12, _ | 13, _ -> "th"
  //   _, 1 -> "st"
  //   _, 2 -> "nd"
  //   _, 3 -> "rd"
  //   _, _ -> "th"
  // }
  <> case day.year {
    // TODO
    2025 -> ""
    year -> " " <> int.to_string(year)
  }
}
