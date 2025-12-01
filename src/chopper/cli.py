import os
import sys
import click
from pathlib import Path
import importlib.metadata
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from .chopper import (
    chop,
    find_chopper_files,
    show_error,
    CommentType,
    Action,
    CHOPPER_NAME,
)
import time  # noqa
from watchdog.observers import Observer

__version__ = importlib.metadata.version("chopper")


class ChopEventHandler(FileSystemEventHandler):
    source: str
    types: dict[str, str]
    comments: CommentType
    warn: bool

    def __init__(
        self,
        types: dict[str, str],
        comments: CommentType,
        warn: bool,
    ) -> None:
        super().__init__()
        self.types = types
        self.comments = comments
        self.warn = warn

    def on_any_event(self, event: FileSystemEvent) -> None:
        path = str(event.src_path)
        is_chopper_file = os.path.isfile(path) and path.endswith(CHOPPER_NAME)

        if is_chopper_file and event.event_type == "modified":
            self.chop_file(path)

    def chop_file(self, path: str) -> bool:
        result = chop(path, self.types, self.comments, warn=self.warn)
        return result


# fmt: off
CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "token_normalize_func": lambda x: x.lower(),
}
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("source", envvar="CHOPPER_SOURCE_DIR",
                type=click.Path(exists=True, path_type=Path, file_okay=True, dir_okay=True))

@click.option("--script-dir", "-s", envvar="CHOPPER_SCRIPT_DIR",
              type=click.Path(exists=True, path_type=Path, file_okay=False),
              help="Destination for the script files.")
@click.option("--style-dir", "-c", envvar="CHOPPER_STYLE_DIR",
              type=click.Path(exists=True, path_type=Path, file_okay=False),
              help="Destination for the style files.")
@click.option("--html-dir", "-m", envvar="CHOPPER_HTML_DIR",
              type=click.Path(exists=True, path_type=Path, file_okay=False),
              help="Destination for the html files.")
@click.option("--comments", envvar="CHOPPER_COMMENTS",
              default=CommentType.NONE,
              type=click.Choice(CommentType),
              help="What comments to use for the chopped files. Default is none.")
@click.option("--warn/--overwrite", "-w/-o", envvar="CHOPPER_WARN", default=True,
              help=("On initial run, warn when the file contents differs instead of overwriting it. "
                    "Note that while watching, overwrite is always true."))
@click.option("--watch/--no-watch", envvar="CHOPPER_WATCH", default=False,
              help="Watch the source directory for changes and re-chop the files.")
@click.option("--update", is_flag=True,
              help="Interactively update chopper files with destination changes. Requires --warn.")
@click.option("--debug", is_flag=True, help="Print debug information.")
@click.version_option(__version__)
# fmt: on
def main(
    source: str,
    script_dir: str,
    style_dir: str,
    html_dir: str,
    comments: CommentType,
    warn: bool,
    watch: bool,
    update: bool,
    debug: bool,
) -> None:
    """Chop files into their separate types, style, script and html.

    Get to the choppa! 🚁

    These environment variables can be used instead of command line
    options.  They can be added to a .env file.

    \b
    CHOPPER_SOURCE_DIR
    CHOPPER_SCRIPT_DIR
    CHOPPER_STYLE_DIR
    CHOPPER_HTML_DIR
    CHOPPER_COMMENTS
    CHOPPER_WARN
    CHOPPER_WATCH
    CHOPPER_INDENT
    """

    if debug:
        print()
        click.secho("Locals:", bold=True)
        for key, value in locals().items():
            print(f'{key:10} {value}')
        print()
        click.secho('Environment variables:', bold=True)
        for key, value in os.environ.items():
            if key.startswith("CHOPPER_"):
                print(f'{key:20}{value}')
        print()

    # Validate flag combinations
    if update and not warn:
        click.echo("Error: --update requires --warn flag", err=True)
        sys.exit(1)

    if update and watch:
        click.echo("Error: --update cannot be used with --watch", err=True)
        sys.exit(1)

    if os.path.exists(source):
        if os.path.isdir(source):
            chopper_files = find_chopper_files(Path(source))
        else:
            chopper_files = [source]
    else:
        show_error(Action.CHOP, source, "No such file or directory:")
        sys.exit(1)

    types = {
        "script": script_dir or "",
        "style": style_dir or "",
        "chop": html_dir or "",
    }

    # if not comments:
    #     comments = "none"

    # chop_comment_type = {
    #     'php': Comment("/* ", " */"),
    #     'html': Comment("<!-- ", " -->"),
    #     'antlers': Comment("{{# ", " #}}"),
    #     'twig': Comment("{# ", " #}"),
    #     'js': Comment("/* ", " */"),
    #     'css': Comment("/* ", " */"),
    #     'none': Comment("", ""),
    # }
    # comment_types = {
    #     "script": Comment("// ", ""),
    #     "style": Comment("/* ", " */"),
    #     # 'chop': Comment('<!-- ', ' -->'),
    #     "chop": chop_comment_type[comments],
    # }
    # use_comments = True
    # if comments == 'none':
    #     use_comments = False

    success: bool = True
    for source_file in chopper_files:
        if not chop(source_file, types, comments, warn=warn, update=update):
            success = False

    if not success:
        click.secho("Some files are different", fg="red")
        sys.exit(1)

    if watch:
        event_handler = ChopEventHandler(types, comments, warn=False)
        observer = Observer()
        observer.schedule(event_handler, path=source, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            click.echo('\nChopper watch ended.')
        finally:
            observer.stop()
            observer.join()
