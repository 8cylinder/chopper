import difflib
import errno
import io
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from pathlib import Path
from pprint import pprint as pp  # noqa: F401
from textwrap import dedent
from typing import Any, NamedTuple, TextIO  # from typing_extensions import TextIO
import click
from dotenv import load_dotenv


def validate_output_path(file_path: str, base_path: str) -> tuple[bool, str]:
    """Validate that output path stays within base directory.

    Args:
        file_path: The requested output file path from chopper:file attribute
        base_path: The base directory that files should be written to

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path or not base_path:
        return False, "Empty file path or base path"

    try:
        # Normalize path separators to handle both Unix and Windows styles
        normalized_path = file_path.replace('\\', '/')

        # Resolve the paths to handle '..' and '.' components
        base_resolved = Path(base_path).resolve()
        requested_path = Path(base_path, normalized_path).resolve()

        # Check if the requested path is within the base directory
        try:
            requested_path.relative_to(base_resolved)
            return True, ""
        except ValueError:
            return (
                False,
                f"Path '{file_path}' attempts to write outside allowed directory",
            )

    except (ValueError, OSError) as e:
        return False, f"Invalid path '{file_path}': {e}"


def find_file_upwards(
    start_dir: Path, target_files: list[str], max_depth: int = 5
) -> Path | None:
    """Find config file by searching upwards from current directory.

    Args:
        start_dir: Directory to start search from
        target_files: List of filenames to search for
        max_depth: Maximum number of directories to search upward

    Returns:
        Path to found config file, or None if not found
    """
    current_dir = start_dir.resolve()
    depth = 0

    while current_dir != current_dir.parent and depth < max_depth:
        for target_file in target_files:
            target_path = current_dir / target_file
            # Only return regular files, not directories or special files
            if target_path.exists() and target_path.is_file():
                return target_path
        current_dir = current_dir.parent
        depth += 1
    return None


# Config loading moved to after function definitions


CHOPPER_NAME = ".chopper.html"


class Action(Enum):
    CHOP = "Chop"
    WRITE = "Write"
    NEW = "New"
    DIR = "Mkdir"
    MISSMATCH = "Files differ"
    UNCHANGED = "File unchanged"
    DOES_NOT_EXIST = "Does not exist"


class Chopped(NamedTuple):
    action: Action
    dest_file: Path
    msg: str | None = None
    diff: str | None = None


class ChopperLog(NamedTuple):
    source: Path
    chopped: list[Chopped] = []


# log = ChopperLog("chopper.html")
# l.chopped.append(Chopped(Action.CHOP, "style.css", "diff"))


class Comment(NamedTuple):
    open: str
    close: str


class CommentType(Enum):
    SERVER = "server"
    CLIENT = "client"
    NONE = "none"


comment_cs_styles = {
    "php": Comment("<!-- ", " -->"),
    "html": Comment("<!-- ", " -->"),
    "antlers": Comment("<!-- ", " -->"),
    "twig": Comment("<!-- ", " -->"),
    "js": Comment("// ", ""),
    "css": Comment("/* ", " */"),
    "none": Comment("", ""),
}
comment_ss_styles = {
    "php": Comment("/* ", " */"),
    "html": Comment("{# ", " #}"),
    "antlers": Comment("{{# ", " #}}"),
    "twig": Comment("{# ", " #}"),
    "js": Comment("// ", ""),
    "css": Comment("/* ", " */"),
    "none": Comment("", ""),
}


def print_action(
    action: Action,
    filename: str | Path,
    last: bool = False,
) -> None:
    """Output information about the action taken by chopper."""
    choppa = click.style("CHOPPER:", fg="magenta", bold=True)
    task = click.style(action.value, fg="bright_green")
    filename = click.style(str(filename), fg="bright_blue")
    tree: str = ""
    date: str = ""
    if action == Action.CHOP:
        now = datetime.now().isoformat(timespec="seconds", sep=",")
        date = click.style(now, fg="bright_black")
    else:
        tree = "└─ " if last else "├─ "
    click.echo(f"{choppa} {tree}{task}  {filename}  {date}")


def show_error(action: Action, filename: str, msg: str) -> None:
    choppa = click.style("CHOPPER:", bg="red", bold=True)
    action_pretty = click.style(action.value, bg="red", bold=True)
    filename = click.style(filename, fg="bright_blue")
    click.echo(f"{choppa} ├─ {action_pretty} {msg} {filename}", err=True)


def show_warning(msg: str) -> None:
    choppa = click.style("CHOPPER:", fg="yellow", bold=True)
    msg_pretty = click.style(msg, fg="yellow")
    click.echo(f"{choppa} ┆ {msg_pretty}", err=True)


# Load configuration files securely
chopper_confs = [
    ".chopper",
    "chopper.conf",
    ".env.chopper",
    ".env",
]
if dot_env := find_file_upwards(Path.cwd(), chopper_confs):
    try:
        if load_dotenv(dot_env):
            print(f"Using environment vars from: {dot_env}")
    except Exception as e:
        show_warning(f"Failed to load config file {dot_env}: {e}")
        # Continue execution without config file


@dataclass
class ParsedData:
    path: str
    file_type: str
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
            if not self.tree and self.path:
                self.parsed_data.append(
                    ParsedData(
                        path=self.path,
                        file_type=os.path.splitext(self.path)[1][1:],
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


def update_chopper_section(
    source_file: Path, block: ParsedData, new_content: str
) -> bool:
    """Update specific section in chopper file using parser position data.

    Args:
        source_file: Path to the .chopper.html file
        block: ParsedData object with position information
        new_content: New content to insert (from destination file)

    Returns:
        bool: True if update successful, False if error
    """
    try:
        original_content = source_file.read_text()
        lines = original_content.splitlines(keepends=True)

        # Use parser positions to identify content boundaries
        # ChopperParser returns 1-based line numbers, convert to 0-based
        start_line = block.start[0] - 1
        end_line = block.end[0] - 1

        # Replace content between tags, preserve tag structure
        # The start position is at the end of the opening tag
        # The end position is at the start of the closing tag
        before_section = lines[: start_line + 1]  # Include opening tag line
        after_section = lines[end_line:]  # Include closing tag line

        # Get indentation from environment variable, default to two spaces
        indent = os.environ.get("CHOPPER_INDENT", "  ")
        if not indent:  # Handle empty string case
            indent = "  "

        # Insert new content with proper formatting and indentation
        content_lines = new_content.rstrip().splitlines()
        new_content_lines = []

        for line in content_lines:
            if line.strip():  # Only indent non-empty lines
                new_content_lines.append(f"{indent}{line}\n")
            else:
                new_content_lines.append("\n")  # Preserve empty lines without indentation

        # Reconstruct file
        updated_lines = before_section + new_content_lines + after_section
        source_file.write_text("".join(updated_lines))

        return True

    except Exception as e:
        import click

        click.echo(f"Error updating {source_file}: {e}", err=True)
        return False


def chop(
    source: str,
    types: dict[str, str],
    comments: CommentType,
    warn: bool = False,
    update: bool = False,
) -> bool:
    """Chop up the source file into the blocks defined by the chopper tags."""
    print_action(Action.CHOP, source)
    log = ChopperLog(Path(source))
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
        # block.file_type = ""
        # block.base_path = root
        if "{" in block.path:
            show_warning(f'Magic vars no longer work: "{block.path}".')

        # SECURITY: Validate output path to prevent directory traversal
        if block.path:
            is_valid, error_msg = validate_output_path(block.path, block.base_path)
            if not is_valid:
                show_error(Action.CHOP, source, f"Security violation: {error_msg}")
                success = False
                continue  # Skip this block entirely

        block.content = extract_block(block.start, block.end, source_html_split)
        block.source_file = source

        if comments == CommentType.CLIENT and block.path:
            comment_style = comment_cs_styles[block.file_type]

            dest = Path(os.path.join(block.base_path, block.path))
            comment_line = (
                f"{comment_style.open}{source} -> {dest}{comment_style.close}"
            )
            block.content = f"\n{comment_line}\n\n{block.content}"

        # print(block.content)

        # comment = comments[block.tag]
        # block.comment_open, block.comment_close = comment
        # if insert_comments and block.path:
        #     dest = Path(os.path.join(block.base_path, block.path))
        #     comment_line = f"{comment.open}{source} -> {dest}{comment.close}"
        #     block.content = f"\n{comment_line}\n\n{block.content}"

        last = False if block_count != i else True
        if not new_or_overwrite_file(block, log, warn, update, last):
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
    block: ParsedData,
    log: ChopperLog,
    warn: bool = False,
    update: bool = False,
    last: bool = False,
) -> bool:
    """Create or update the file specified in the chopper:file attribute."""
    content = block.content
    if not block.path:
        print_action(Action.UNCHANGED, "No destination defined", last=False)
        log.chopped.append(Chopped(Action.UNCHANGED, "No destination defined"))
        return True

    # SECURITY: Validate output path to prevent directory traversal (defense in depth)
    is_valid, error_msg = validate_output_path(block.path, block.base_path)
    if not is_valid:
        show_error(Action.WRITE, block.source_file, f"Security violation: {error_msg}")
        log.chopped.append(Chopped(Action.MISSMATCH, Path(block.path), error_msg))
        return False

    partial_file = Path(os.path.join(block.base_path, block.path))

    if not partial_file.parent.exists():
        partial_file.parent.mkdir(parents=True, exist_ok=True)
        print_action(Action.DIR, partial_file.parent)
        log.chopped.append(Chopped(Action.DIR, partial_file.parent))

    success: bool = False
    try:
        if warn and not partial_file.exists():
            print_action(Action.DOES_NOT_EXIST, partial_file, last=last)
            success = False

        elif partial_file.exists():
            with open(partial_file, "r+") as f:
                success = write_to_file(
                    block, content, f, last, partial_file, warn, update, False
                )
        else:
            with open(partial_file, "w") as f:
                success = write_to_file(
                    block, content, f, last, partial_file, False, update, True
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
    update: bool,
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

            # Add update prompt if --update flag used
            if update:
                import click

                choice = click.prompt(
                    "Update chopper file?",
                    type=click.Choice(["y", "n", "c"], case_sensitive=False),
                )

                if choice == "y":
                    # Update the chopper file with destination content
                    if update_chopper_section(
                        Path(block.source_file), block, current_contents
                    ):
                        success = True  # Consider this a success
                    else:
                        success = False  # Update failed
                elif choice == "c":
                    # Cancel entire operation
                    click.echo("Operation cancelled")
                    sys.exit(0)
                # 'n' continues with warn behavior (success = False)

            if not update or (update and choice == "n"):
                success = False
        else:
            if newfile:
                print_action(Action.NEW, partial, last=last)
            else:
                print_action(Action.WRITE, partial, last=last)
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
    a_split = a.splitlines()
    b_split = b.splitlines()
    # a_split = [i.strip() for i in a.splitlines()]
    # b_split = [i.strip() for i in b.splitlines()]
    context = 3
    diff = difflib.unified_diff(
        a_split, b_split, tofile=fname_a, fromfile=fname_b, n=context
    )
    # prefix = "         ┆ "
    prefix = click.style("         │ ", fg="yellow")
    click.echo(prefix)
    for i, line in enumerate(diff):
        # header
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
        # diff
        elif line.startswith("+"):
            click.echo(
                prefix + click.style(line, fg="bright_green"),
                nl=True,
            )
        elif line.startswith("-"):
            click.echo(
                prefix + click.style(line, fg="bright_red"),
                nl=True,
            )
        else:
            click.echo(prefix + click.style(line, fg="bright_black"))
    click.echo(prefix)
