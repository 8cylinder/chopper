from datetime import datetime
import os
import sys
import errno
import io
from textwrap import dedent
from pprint import pprint as pp  # noqa: F401
from html.parser import HTMLParser
from pathlib import Path
from enum import Enum
import difflib
from typing import Any, NamedTuple
import click
from dataclasses import dataclass
from typing_extensions import TextIO
import importlib.metadata
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

__version__ = importlib.metadata.version("chopper")
NOW = datetime.now().isoformat(timespec="seconds", sep=",")
DRYRUN = False
CHOPPER_NAME = ".chopper.html"


class Action(Enum):
    CHOP = "Chop"
    WRITE = "Write"
    NEW = "New"
    DIR = "Mkdir"
    UNCHANGED = "File unchanged"
    DOES_NOT_EXIST = "Does not exist"


class Comment(NamedTuple):
    open: str
    close: str


def print_action(
    action: Action,
    filename: str | Path,
    dry_run: bool = False,
    last: bool = False,
) -> None:
    """Output information about the action taken by chopper."""
    dry = " (DRY RUN)" if dry_run else ""
    choppa = click.style("CHOPPER:", fg="magenta", bold=True)
    task = click.style(action.value, fg="bright_green")
    filename = click.style(str(filename), fg="bright_blue")
    tree: str = ""
    date: str = ""
    if action == Action.CHOP:
        date = click.style(NOW, fg="bright_black")
    else:
        tree = "└─ " if last else "├─ "
    click.echo(f"{choppa} {tree}{task} {filename}  {date}")


def show_error(action: Action, filename: str, msg: str, dry_run: bool = False) -> None:
    dry = " (DRY RUN)" if dry_run else ""
    choppa = click.style("CHOPPER:", bg="red", bold=True)
    action_pretty = click.style(action.value, bg="red", bold=True)
    filename = click.style(filename, fg="bright_blue")
    click.echo(f"{choppa} ├─ {action_pretty} {msg} {filename}", err=True)


def show_warning(msg: str) -> None:
    choppa = click.style("CHOPPER:", fg="yellow", bold=True)
    msg_pretty = click.style(msg, fg="yellow")
    click.echo(f"{choppa} ┆ {msg_pretty}", err=True)


@dataclass
class ParsedData:
    path: str
    base_path: str
    source_file: str
    tag: str
    start: tuple[int, ...]
    end: tuple[int, int]
    content: str
    comment_open: str
    comment_close: str


class ChopperParser(HTMLParser):
    tags: list[str] = ["style", "script", "chop"]
    tree: list[Any] = []
    path: str = ""
    parsed_data: list[ParsedData] = []
    start: list[int] = [0, 0]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.tags:
            self.tree.append(tag)
            for attr in attrs:
                if attr[0] == "chopper:file":
                    self.path = attr[1] if attr[1] else ""
                    pos = list(self.getpos())
                    pos[0] -= 1
                    if start_tag := self.get_starttag_text():
                        extra = [len(i) for i in start_tag.split("\n")]
                        for line in extra:
                            pos = [pos[0] + 1, line]
                        self.start = pos

    def handle_endtag(self, tag: str) -> None:
        if tag in self.tags:
            self.tree.pop()
            if not self.tree:
                self.parsed_data.append(
                    ParsedData(
                        path=self.path,
                        base_path="",
                        source_file="",
                        tag=tag,
                        start=tuple(self.start),
                        end=self.getpos(),
                        content="",
                        comment_open="",
                        comment_close="",
                    )
                )
                self.path = ""


def find_chopper_files(source: Path) -> list[str]:
    """Find all the chopper files in the source directory."""
    if not os.path.exists(source):
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), source)

    if not os.path.isdir(source):
        raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), source)

    chopper_files = []

    for root, dirs, files in os.walk(source):
        for filename in files:
            # print(filename, os.path.islink(filename))
            try:
                os.stat(Path(root, filename))
                if not os.path.islink(filename) and filename.endswith(CHOPPER_NAME):
                    chopper_files.append(os.path.join(root, filename))
            except FileNotFoundError:
                # ignore broken symlinks which are used by Emacs to store backup files
                continue

    return chopper_files


def chop(
    source: str,
    types: dict[str, str],
    insert_comments: bool,
    comments: dict[str, Comment],
    warn: bool = False,
) -> bool:
    """Chop up the source file into the blocks defined by the chopper tags."""
    print_action(Action.CHOP, source)
    try:
        with open(source, "r") as f:
            source_html = f.read()
    except UnicodeDecodeError:
        show_error(Action.CHOP, source, "File is not a valid UTF-8 file.")
        return False

    parser = ChopperParser()
    parser.parsed_data.clear()
    parser.feed(source_html)
    data = parser.parsed_data

    source_html_split = source_html.splitlines()
    block_count = len(data) - 1
    success: bool = True

    for i, block in enumerate(data):
        block.base_path = types[block.tag]
        # block.base_path = root
        if "{" in block.path:
            show_warning(f'Magic vars no longer work: "{block.path}".')
        block.content = extract_block(block.start, block.end, source_html_split)
        block.source_file = source

        comment = comments[block.tag]
        block.comment_open, block.comment_close = comment
        if insert_comments and block.path:
            dest = Path(os.path.join(block.base_path, block.path))
            comment_line = f"{comment.open}{source} -> {dest}{comment.close}"
            block.content = f"\n{comment_line}\n\n{block.content}"

        last = False if block_count != i else True
        if not new_or_overwrite_file(block, warn, last):
            success = False

    return success


def extract_block(
    start: tuple[int, ...], end: tuple[int, int], source_html: list[Any]
) -> str:
    """Extract the block of code from the source.

    Extract from the end of the start tag to the start of the end tag."""

    start_line: int = start[0] - 1
    start_char: int = start[1]
    end_line: int = end[0]
    end_char: int = end[1]

    extracted: list[Any] = source_html[start_line:end_line]
    if len(extracted) == 1:
        extracted[0] = extracted[0][start_char:end_char]
    else:
        extracted[0] = extracted[0][start_char:]
        extracted[-1] = extracted[-1][:end_char]
    extracted_rendered = "\n".join(extracted)
    extracted_rendered = dedent(extracted_rendered)
    extracted_rendered = extracted_rendered.strip()
    extracted_rendered = f"{extracted_rendered}\n"

    return extracted_rendered


def new_or_overwrite_file(
    block: ParsedData, warn: bool = False, last: bool = False
) -> bool:
    """Create or update the file specified in the chopper:file attribute."""
    content = block.content
    if not block.path:
        print_action(Action.UNCHANGED, "No destination defined", last=False)
        return True

    partial_file = Path(os.path.join(block.base_path, block.path))
    # print(f"Partial file: {partial_file}")

    if not partial_file.parent.exists():
        if not DRYRUN:
            partial_file.parent.mkdir(parents=True, exist_ok=True)
        print_action(Action.DIR, partial_file.parent)

    success: bool = False
    try:
        if warn and not partial_file.exists():
            print_action(Action.DOES_NOT_EXIST, partial_file, last=last)
            success = False

        elif partial_file.exists():
            with open(partial_file, "r+") as f:
                success = write_to_file(
                    block, content, f, last, partial_file, warn, False
                )
        else:
            with open(partial_file, "w") as f:
                success = write_to_file(
                    block, content, f, last, partial_file, False, True
                )
    except IsADirectoryError:
        show_error(Action.CHOP, block.source_file, "Destination is a dir.")
        sys.exit(1)
    except FileNotFoundError:
        # show_error(Action.CHOP, block.source_file, "Destination does not exist.")
        show_warning(f"Destination does not exist: {block.source_file}.")

    return success


def write_to_file(
    block: ParsedData,
    content: str,
    f: TextIO,
    last: bool,
    partial: Path,
    warn: bool,
    newfile: bool,
) -> bool:
    """Write the content to the file if it differs from the current contents.

    Show a diff if the file contents differ and the warn flag is set.
    """
    success: bool = True
    try:
        current_contents = f.read()
    except io.UnsupportedOperation:
        current_contents = ""

    if current_contents != content:
        if warn:
            show_error(Action.WRITE, str(partial), "File contents differ")
            a = partial.absolute()
            b = Path(block.source_file).absolute()
            a, b = remove_common_path(a, b, prefix="…")
            show_diff(content, current_contents, str(a), str(b))
            success = False
        else:
            if newfile:
                print_action(Action.NEW, partial, last=last)
            else:
                print_action(Action.WRITE, partial, last=last)
            if not DRYRUN:
                f.seek(0)
                f.write(content)
                f.truncate()
    else:
        print_action(Action.UNCHANGED, partial, last=last)

    return success


def remove_common_path(a: Path, b: Path, prefix: str = "") -> tuple[Path, Path]:
    """Remove the common path from the two paths."""
    common = Path(os.path.commonpath([a, b]))
    a_parts = a.parts[len(common.parts) :]
    b_parts = b.parts[len(common.parts) :]
    a = Path(prefix, *a_parts)
    b = Path(prefix, *b_parts)
    return a, b
    # return (prefix + str(a), prefix + str(b))


def show_diff(a: str, b: str, fname_a: str, fname_b: str) -> None:
    diff = difflib.unified_diff(
        a.splitlines(), b.splitlines(), tofile=fname_a, fromfile=fname_b, n=3
    )
    prefix = "         ┆ "
    click.echo(prefix)
    for i, line in enumerate(diff):
        if line.startswith("+++"):
            click.echo(prefix + click.style(line, fg="bright_green"), nl=False)
        elif line.startswith("---"):
            click.echo(prefix + click.style(line, fg="bright_red"), nl=False)
        elif line.startswith("@@"):
            click.echo(
                prefix
                + click.style(line, fg="bright_white", bold=True, underline=True),
                nl=False,
            )
        elif line.startswith("+"):
            click.echo(prefix + click.style(line, fg="bright_green"), nl=True)
        elif line.startswith("-"):
            click.echo(prefix + click.style(line, fg="bright_red"), nl=True)
        else:
            click.echo(prefix + click.style(line, fg="bright_black"))
    click.echo(prefix)


class ChopEventHandler(FileSystemEventHandler):
    source: str
    types: dict[str, str]
    comments: bool
    comment_types: dict[str, Comment]
    warn: bool

    def __init__(
        self,
        types: dict[str, str],
        comments: bool,
        comment_types: dict[str, Comment],
        warn: bool,
    ) -> None:
        super().__init__()
        self.types = types
        self.comments = comments
        self.comment_types = comment_types
        self.warn = warn

    def on_any_event(self, event: FileSystemEvent) -> None:
        path = str(event.src_path)
        is_chopper_file = os.path.isfile(path) and path.endswith(CHOPPER_NAME)

        if is_chopper_file and event.event_type == "modified":
            self.chop_file(path)

    def chop_file(self, path: str) -> bool:
        result = chop(
            path, self.types, self.comments, self.comment_types, warn=self.warn
        )
        return result


# fmt: off
CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "token_normalize_func": lambda x: x.lower(),
}
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("source", type=click.Path(True, path_type=Path, file_okay=True, dir_okay=True))

@click.option("--script-dir", "-s", type=click.Path(exists=True, file_okay=False),
    help="Destination for the script files.",
)
@click.option("--style-dir", "-c", type=click.Path(exists=True, file_okay=False),
    help="Destination for the style files.",
)
@click.option("--html-dir", "-m", type=click.Path(exists=True, file_okay=False),
    help="Destination for the html files.",
)
@click.option("--comments", is_flag=True,
    help="Add comments to generated files.",
)
@click.option("--warn/--overwrite", "-w/-o", default=True,
  help=("On initial run, warn when the file contents differs instead of overwriting it.  " 
        "Note that while watching, overwrite is always true."),
)
@click.option("--dry-run", is_flag=True,
    help="Do not write any file to the filesystem.",
)
@click.option("--watch", "-w", is_flag=True,
    help="Watch the source directory for changes and re-chop the files.")
@click.version_option(__version__)
# fmt: on
def main(
    source: str,
    script_dir: str,
    style_dir: str,
    html_dir: str,
    comments: bool,
    warn: bool,
    dry_run: bool,
    watch: bool,
) -> None:
    """Chop files into their separate types, style, script and html.

    Get to the choppa!"""
    global DRYRUN
    DRYRUN = dry_run
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

    comment_types = {
        "script": Comment("// ", ""),
        "style": Comment("/* ", " */"),
        # 'chop': Comment('<!-- ', ' -->'),
        "chop": Comment("{{# ", " #}}"),
    }

    success: bool = True
    for source_file in chopper_files:
        if not chop(source_file, types, comments, comment_types, warn=warn):
            success = False

    if not success:
        click.secho("Some files are different", fg="red")
        sys.exit(1)

    if watch:
        event_handler = ChopEventHandler(types, comments, comment_types, warn=False)
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
