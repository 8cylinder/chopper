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


NOW = datetime.now().isoformat(timespec="seconds", sep=",")
DRYRUN = False
CHOPPER_NAME = ".chopper.html"


class C:
    MAGENTA = "\033[95m"

    RED = "\033[31m"
    BRED = "\033[91m"
    REDB = "\033[41m"

    BLUE = "\033[34m"
    BBLUE = "\033[94m"
    BLUEB = "\033[44m"

    BCYAN = "\033[96m"
    CYAN = "\033[36m"
    CYANB = "\033[46m"

    GREEN = "\033[32m"
    BGREEN = "\033[92m"
    GREENB = "\033[42m"

    BLACK = "\033[30m"
    BBLACK = "\033[90m"
    BLACKB = "\033[40m"

    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"


class Action(Enum):
    CHOP = "Chop"
    WRITE = "Write"
    NEW = "New"
    DIR = "Mkdir"
    UNCHANGED = "File unchanged"
    DOESNOTEXIST = "Does not exist"


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
    choppa: str = f"{C.MAGENTA}{C.BOLD}CHOPPER:{C.RESET}"
    task: str = f"{C.BGREEN}{action.value}{dry}{C.RESET}"
    filename = f"{C.BBLUE}{filename}{C.RESET}"
    tree: str = ""
    date: str = ""
    if action == Action.CHOP:
        date = f"{C.BBLACK}{NOW}{C.RESET}"
    else:
        tree = "└─ " if last else "├─ "
    print(f"{choppa} {tree}{task} {filename}  {date}")


def show_error(action: Action, filename: str, msg: str, dry_run: bool = False) -> None:
    dry = " (DRY RUN)" if dry_run else ""
    choppa: str = f"{C.REDB}{C.BOLD}CHOPPER:{C.RESET}"
    action_pretty: str = f"{C.REDB}{C.BOLD}{action.value}{dry}{C.RESET}"
    filename = f"{C.BBLUE}{filename}{C.RESET}"
    print(choppa, action_pretty, msg, filename, file=sys.stderr)


def show_warning(action: Action, msg: str) -> None:
    choppa = click.style("CHOPPER:", fg="yellow", bold=True)
    action_pretty = click.style(action.value, fg="yellow", bold=True)
    print(choppa, action_pretty, msg, file=sys.stderr)


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
            if filename.endswith(CHOPPER_NAME):
                chopper_files.append(os.path.join(root, filename))

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
    with open(source, "r") as f:
        source_html = f.read()

    parser = ChopperParser()
    parser.parsed_data.clear()
    parser.feed(source_html)
    data = parser.parsed_data

    source_html_split = source_html.splitlines()
    block_count = len(data) - 1
    success: bool = True

    for i, block in enumerate(data):
        block.base_path = types[block.tag]
        if "{" in block.path:
            show_warning(Action.CHOP, f'Magic vars no longer work: "{block.path}".')
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

    if not partial_file.parent.exists():
        partial_file.parent.mkdir(parents=True, exist_ok=True)
        print_action(Action.DIR, partial_file.parent)

    try:
        if warn and not partial_file.exists():
            print_action(Action.DOESNOTEXIST, partial_file, last=last)
            success: bool = False

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
            show_diff(content, current_contents, block.path, str(partial))
            success = False
            print()
            # if not DRYRUN:
            #     sys.exit(1)
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


def show_diff(a: str, b: str, fname_a: str, fname_b: str) -> None:
    diff = difflib.context_diff(
        a.splitlines(), b.splitlines(), tofile=fname_a, fromfile=fname_b, n=0
    )
    print()

    for i, line in enumerate(diff):
        if i <= 2:
            continue

        line = line.rstrip()

        if line.startswith("!"):
            print(line)
        elif line.startswith("--"):
            print(f"{C.BLACK}{C.REDB}{line}{C.RESET}")
        elif line.startswith("****"):
            hl = "=" * 80
            print()
            print(f"{C.BCYAN}{hl}{C.RESET}")
            print()
        elif line.startswith("*"):
            print(f"{C.BLACK}{C.GREENB}{line}{C.RESET}")
        else:
            print(line)


# fmt: off
CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "token_normalize_func": lambda x: x.lower(),
}
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("source_dir", type=click.Path(True, path_type=Path, file_okay=False))
@click.option("-s", "--script-dir", type=click.Path(exists=True, file_okay=False),
    help="Destination for the script files",
)
@click.option("-c", "--style-dir", type=click.Path(exists=True, file_okay=False),
    help="Destination for the style files",
)
@click.option("-m", "--html-dir", type=click.Path(exists=True, file_okay=False),
    help="Destination for the html files",
)
@click.option("--comments", is_flag=True,
    help="Add comments to generated files",
)
@click.option("--warn", is_flag=True,
    help="Warn when the file contents differs instead of overwriting it.",
)
@click.option("--dry-run",is_flag=True,
    help="Do not write any file to the filesystem",
)
# fmt: on
def main(
    source_dir: str,
    script_dir: str,
    style_dir: str,
    html_dir: str,
    comments: bool,
    warn: bool,
    dry_run: bool,
) -> None:
    """Chop files into their separate types, style, script and html.

    Get to the choppa!"""
    global DRYRUN
    DRYRUN = dry_run
    if os.path.exists(source_dir):
        if os.path.isdir(source_dir):
            chopper_files = find_chopper_files(Path(source_dir))
        else:
            chopper_files = [source_dir]
    else:
        show_error(Action.CHOP, source_dir, "No such file or directory:")
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
    for source in chopper_files:
        if not chop(source, types, comments, comment_types, warn=warn):
            success = False

    if not success:
        show_error(Action.CHOP, "", "Some files were different.")
        sys.exit(1)
