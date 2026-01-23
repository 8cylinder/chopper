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


def print_debug_info(locals_dict: dict[str, str | bool | Path | CommentType]) -> None:
    """Print debug information about locals and environment variables."""
    print()
    click.secho("Locals:", bold=True)
    for key, value in locals_dict.items():
        print(f"{key:10} {value}")
    print()
    click.secho("Environment variables:", bold=True)
    for key, value in os.environ.items():
        if key.startswith("CHOPPER_"):
            print(f"{key:20}{value}")
    print()


def validate_command_flags(update: bool, warn: bool, watch: bool) -> None:
    """Validate flag combinations and exit if invalid.

    Raises:
        SystemExit: If flag combination is invalid
    """
    if update and not warn:
        click.echo("Error: --update requires --warn flag", err=True)
        sys.exit(1)

    if update and watch:
        click.echo("Error: --update cannot be used with --watch", err=True)
        sys.exit(1)


def get_chopper_files(source_path: Path) -> list[str]:
    """Get list of chopper files from source path.

    Args:
        source_path: Path to file or directory containing chopper files

    Returns:
        List of chopper file paths

    Raises:
        SystemExit: If source path doesn't exist
    """
    if source_path.exists():
        if source_path.is_dir():
            return find_chopper_files(source_path)
        else:
            return [str(source_path)]
    else:
        show_error(Action.CHOP, str(source_path), "No such file or directory:")
        sys.exit(1)


def process_files(
    chopper_files: list[str],
    types: dict[str, str],
    comments: CommentType,
    warn: bool,
    update: bool,
) -> bool:
    """Process all chopper files.

    Args:
        chopper_files: List of file paths to process
        types: Dictionary mapping type names to output directories
        comments: Comment style to use
        warn: Whether to warn instead of overwrite
        update: Whether to enable interactive update mode

    Returns:
        True if all files processed successfully, False otherwise
    """
    success = True
    for source_file in chopper_files:
        if not chop(source_file, types, comments, warn=warn, update=update):
            success = False
    return success


def start_watch_mode(
    source: str,
    types: dict[str, str],
    comments: CommentType,
) -> None:
    """Start watch mode to monitor directory for changes.

    Args:
        source: Source directory to watch
        types: Dictionary mapping type names to output directories
        comments: Comment style to use
    """
    event_handler = ChopEventHandler(types, comments, warn=False)
    observer = Observer()
    observer.schedule(event_handler, path=source, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nChopper watch ended.")
    finally:
        observer.stop()
        observer.join()


class ChopEventHandler(FileSystemEventHandler):
    source: str
    types: dict[str, str]
    comments: CommentType
    warn: bool
    # Debounce tracking: maps file path to last processed timestamp
    _last_processed: dict[str, float]
    # Minimum seconds between processing the same file
    DEBOUNCE_SECONDS: float = 1.0

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
        self._last_processed = {}

    def on_any_event(self, event: FileSystemEvent) -> None:
        path = Path(str(event.src_path))
        is_chopper_file = path.is_file() and path.name.endswith(CHOPPER_NAME)

        if is_chopper_file and event.event_type == "modified":
            # Debounce: skip if this file was processed recently
            now = time.time()
            path_str = str(path)
            last_time = self._last_processed.get(path_str, 0)
            if now - last_time < self.DEBOUNCE_SECONDS:
                return
            self._last_processed[path_str] = now
            self.chop_file(path_str)

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
    CHOPPER_FILE_PATTERN
    CHOPPER_WARN
    CHOPPER_WATCH
    CHOPPER_INDENT
    """
    if debug:
        print_debug_info(locals())

    validate_command_flags(update, warn, watch)

    source_path = Path(source)
    chopper_files = get_chopper_files(source_path)

    types = {
        "script": script_dir or "",
        "style": style_dir or "",
        "chop": html_dir or "",
    }

    success = process_files(chopper_files, types, comments, warn, update)

    if not success:
        click.secho("Some files are different", fg="red")
        sys.exit(1)

    if watch:
        start_watch_mode(source, types, comments)
