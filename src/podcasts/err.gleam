import gleam/list
import gleam/string
import glemplate/parser
import glemplate/renderer
import glrss_parser/rss
import podcasts/edownload
import simplifile
import sqlight

pub type Err {
  DownloadErr(edownload.DownloadError)
  FileErr(String, simplifile.FileError)
  TemplateParseErr(parser.ParseError)
  RssParseErr(rss.ParseError)
  RenderErr(renderer.RenderError)
  DbErr(sqlight.Error)
  NotFoundErr
  Errs(List(Err))
}

pub fn to_string(err: Err) -> String {
  case err {
    FileErr(path, err) -> path <> ": " <> simplifile.describe_error(err)
    Errs(errs) -> string.join(list.map(errs, to_string), ", ")
    _ -> string.inspect(err)
    // DownloadErr(err) -> string.inspect(err)
    // TemplateParseErr(err) -> string.inspect(err)
    // RssParseErr(err) -> string.inspect(err)
    // RenderErr(err) -> string.inspect(err)
  }
}
