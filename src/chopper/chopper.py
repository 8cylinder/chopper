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
from textwrap import dedent
from typing import Any, NamedTuple, \
    TextIO  # from typing_extensions import TextIO
import click
from dotenv import load_dotenv

from .constants import (
    CHOPPER_FILE_EXTENSION,
    MAX_CONFIG_SEARCH_DEPTH,
    CONFIG_FILE_NAMES,
    COMMENT_CLIENT_STYLES,
    COMMENT_SERVER_STYLES,
)


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
        normalized_path = file_path.replace("\\", "/")

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
                f"Path '{file_path}' attempts to write outside allowed "
                f"directory",
            )

    except (ValueError, OSError) as e:
        return False, f"Invalid path '{file_path}': {e}"


def find_file_upwards(
        start_dir: Path,
        target_files: list[str] | None = None,
        max_depth: int = MAX_CONFIG_SEARCH_DEPTH,
) -> Path | None:
    """Find config file by searching upwards from current directory.

    Args:
        start_dir: Directory to start search from
        target_files: List of filenames to search for (defaults to
        CONFIG_FILE_NAMES)
        max_depth: Maximum number of directories to search upward

    Returns:
        Path to found config file, or None if not found
    """
    if target_files is None:
        target_files = CONFIG_FILE_NAMES

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
# Constants now imported from constants.py


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


class CommentType(Enum):
    SERVER = "server"
    CLIENT = "client"
    NONE = "none"


# Aliases for backward compatibility
comment_cs_styles = COMMENT_CLIENT_STYLES
comment_ss_styles = COMMENT_SERVER_STYLES


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


def get_chopper_file_pattern() -> str:
    """Get the chopper file pattern from environment variable or default.

    Returns:
        File pattern string, defaults to CHOPPER_FILE_EXTENSION if not set
        or if environment variable is empty.
    """
    pattern = os.environ.get("CHOPPER_FILE_PATTERN", CHOPPER_FILE_EXTENSION)
    if not pattern:  # Handle empty string case
        pattern = CHOPPER_FILE_EXTENSION
    return pattern


# Dynamic alias that respects environment configuration
CHOPPER_NAME = get_chopper_file_pattern()


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
    """HTML parser that extracts script, style, and chop sections."""

    def __init__(self) -> None:
        """Initialize parser with instance variables to avoid shared state."""
        super().__init__()
        self.tags: list[str] = ["style", "script", "chop"]
        self.tree: list[Any] = []
        self.path: str = ""
        self.parsed_data: list[ParsedData] = []
        self.start: list[int] = [0, 0]

    def handle_starttag(self, tag: str,
                        attrs: list[tuple[str, str | None]]) -> None:
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
            # Handle malformed HTML with unbalanced tags gracefully
            if not self.tree:
                return
            self.tree.pop()
            if not self.tree and self.path:
                self.parsed_data.append(
                    ParsedData(
                        path=self.path,
                        file_type=Path(self.path).suffix[
                            1:] if self.path else "",
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
    if not source.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT),
                                str(source))

    if not source.is_dir():
        raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR),
                                 str(source))

    chopper_files = []

    for root, dirs, files in os.walk(source):
        for filename in files:
            if filename.endswith(CHOPPER_NAME):
                full_path = Path(root, filename)
                try:
                    # Skip symlinks - they may be used by editors for backup
                    # files
                    if not full_path.is_symlink():
                        chopper_files.append(str(full_path))
                except FileNotFoundError:
                    # ignore broken symlinks which are used by Emacs to store
                    # backup files
                    continue

    return chopper_files


def update_chopper_section(
        source_file: Path, block: ParsedData, new_content: str,
) -> bool:
    """Update specific section in chopper file using parser position data.

    Args:
        source_file: Path to the .chopper.html file
        block: ParsedData object with position information
        new_content: New content to insert (from destination file)

    Returns:
        bool: True if update successful, False if error
    """
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
            new_content_lines.append(
                "\n")  # Preserve empty lines without indentation

    # Reconstruct file
    updated_lines = before_section + new_content_lines + after_section
    source_file.write_text("".join(updated_lines))

    return True


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
    parser.feed(source_html)
    data = parser.parsed_data

    source_html_split = source_html.splitlines()
    block_count = len(data) - 1
    success: bool = True

    i = 0
    while i < len(data):
        block = data[i]

        block.base_path = types[block.tag]
        if "{" in block.path:
            show_warning(f'Magic vars no longer work: "{block.path}".')

        block.content = extract_block(block.start, block.end, source_html_split)
        block.source_file = source

        if comments in (CommentType.CLIENT, CommentType.SERVER) and block.path:
            if comments == CommentType.CLIENT:
                comment_style = comment_cs_styles[block.file_type]
            else:  # CommentType.SERVER
                comment_style = comment_ss_styles[block.file_type]

            dest = Path(block.base_path) / block.path
            comment_line = (
                f"{comment_style.open}{source} -> {dest}{comment_style.close}"
            )
            block.content = f"\n{comment_line}\n\n{block.content}"

        last = False if block_count != i else True
        result, source_updated = write_chopped_block(block, log, warn, update,
                                                     last)
        if not result:
            success = False

        # If source was updated, re-parse to get fresh positions for
        # remaining blocks
        if source_updated:
            try:
                with open(source, "r") as f:
                    source_html = f.read()
            except UnicodeDecodeError:
                show_error(
                    Action.CHOP, source,
                    "File is not a valid UTF-8 file after update."
                )
                return False

            parser = ChopperParser()
            parser.feed(source_html)
            data = parser.parsed_data
            source_html_split = source_html.splitlines()
            block_count = len(data) - 1
            # Move to next block - current one was just updated
            i += 1
            continue

        i += 1

    return success


def extract_block(
        start: tuple[int, ...], end: tuple[int, int], source_html: list[Any],
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


def ensure_parent_directory_exists(file_path: Path) -> bool:
    """Create parent directory for file if it doesn't exist.

    Args:
        file_path: Path to the file whose parent should be created

    Returns:
        True if directory exists or was created successfully, False on error
    """
    if not file_path.parent.exists():
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            print_action(Action.DIR, file_path.parent)
            return True
        except (OSError, PermissionError) as e:
            show_error(
                Action.DIR, str(file_path.parent),
                f"Cannot create directory: {e}"
            )
            return False
    return True


def validate_and_resolve_output_path(
        block: ParsedData,
) -> tuple[bool, Path | None, str]:
    """Validate block has valid output path and resolve it.

    Args:
        block: ParsedData containing path and base_path

    Returns:
        Tuple of (is_valid, resolved_path, error_message)
    """
    if not block.path:
        return True, None, ""

    # Validate output path for security
    is_valid, error_msg = validate_output_path(block.path, block.base_path)
    if not is_valid:
        return False, None, error_msg

    return True, Path(block.base_path) / block.path, ""


def open_file_for_write(
        partial_file: Path, warn: bool,
) -> tuple[TextIO | None, bool, str]:
    """Open file for writing, handling new vs existing files.

    Args:
        partial_file: Path to file to open
        warn: Whether warn mode is enabled

    Returns:
        Tuple of (file_handle, is_new_file, error_message)
    """
    try:
        # Check if file should exist in warn mode
        if warn and not partial_file.exists():
            return None, False, "DOES_NOT_EXIST"

        # Update existing file
        if partial_file.exists():
            f = open(partial_file, "r+")
            return f, False, ""
        # Create new file
        else:
            f = open(partial_file, "w")
            return f, True, ""

    except IsADirectoryError:
        return None, False, f"Destination is a directory: {partial_file}"
    except PermissionError as e:
        return None, False, f"Permission denied: {e}"
    except FileNotFoundError as e:
        return None, False, f"File not found: {e}"
    except OSError as e:
        return None, False, f"OS error: {e}"


def write_chopped_block(
        block: ParsedData,
        log: ChopperLog,
        warn: bool = False,
        update: bool = False,
        last: bool = False,
) -> tuple[bool, bool]:
    """Create or update the file specified in the chopper:file attribute.

    Returns:
        Tuple of (success, source_was_updated)
        - success: Whether operation succeeded
        - source_was_updated: Whether the chopper source file was modified
    """
    content = block.content

    # Handle blocks with no destination path
    if not block.path:
        print_action(Action.UNCHANGED, "No destination defined", last=False)
        log.chopped.append(
            Chopped(Action.UNCHANGED, Path(""), msg="No destination defined")
        )
        return True, False

    # Validate and resolve output path
    is_valid, partial_file, error_msg = validate_and_resolve_output_path(block)
    if not is_valid:
        show_error(Action.WRITE, block.source_file,
                   f"Security violation: {error_msg}")
        log.chopped.append(
            Chopped(Action.MISSMATCH, Path(block.path), error_msg))
        return False, False

    assert partial_file is not None  # mypy hint: validated above

    # Ensure parent directory exists
    if not ensure_parent_directory_exists(partial_file):
        return False, False

    # Open file for writing
    file_handle, is_new_file, error_msg = open_file_for_write(partial_file,
                                                              warn)

    if error_msg == "DOES_NOT_EXIST":
        print_action(Action.DOES_NOT_EXIST, partial_file, last=last)
        return False, False

    if file_handle is None:
        show_error(Action.WRITE, block.source_file, error_msg)
        return False, False

    # Write content to file
    try:
        with file_handle:
            return write_to_file(
                block,
                content,
                file_handle,
                last,
                partial_file,
                warn,
                update,
                is_new_file,
            )
    except Exception as e:
        show_error(Action.WRITE, block.source_file, f"Unexpected error: {e}")
        return False, False


def read_file_content(f: TextIO) -> tuple[str | None, str]:
    """Read content from file handle.

    Args:
        f: File handle to read from

    Returns:
        Tuple of (content, error_message)
    """
    try:
        return f.read(), ""
    except io.UnsupportedOperation:
        return "", ""
    except PermissionError as e:
        return None, f"Permission denied reading file: {e}"


def prompt_for_update() -> str:
    """Prompt user to update chopper file with destination changes.

    Returns:
        User choice: 'y', 'n', or 'c'
    """
    return click.prompt(
        "Update chopper file?",
        type=click.Choice(["y", "n", "c"], case_sensitive=False),
    )


def handle_file_difference(
        block: ParsedData,
        content: str,
        current_contents: str,
        partial: Path,
        warn: bool,
        update: bool,
) -> tuple[bool, bool, bool]:
    """Handle case where file contents differ from chopped content.

    Args:
        block: ParsedData containing source information
        content: New content from chopper file
        current_contents: Current file contents
        partial: Path to destination file
        warn: Whether warn mode is enabled
        update: Whether update mode is enabled

    Returns:
        Tuple of (should_write, success, source_was_updated)
        - should_write: Whether to write content to destination
        - success: Whether operation succeeded
        - source_was_updated: Whether the chopper source file was modified
    """
    if not warn:
        return True, True, False

    # Warn mode: show error and diff
    show_error(Action.WRITE, str(partial), "File contents differ")
    a = partial.absolute()
    b = Path(block.source_file).absolute()
    a, b = remove_common_path(a, b, prefix="…")
    show_diff(content, current_contents, str(a), str(b))

    # Handle update mode
    if update:
        choice = prompt_for_update()

        if choice == "y":
            # Update the chopper file with destination content
            if update_chopper_section(Path(block.source_file), block,
                                      current_contents):
                return False, True, True  # Don't write, success, source updated
            else:
                return False, False, False  # Update failed
        elif choice == "c":
            # Cancel entire operation
            click.echo("Operation cancelled")
            sys.exit(0)
        # choice == 'n': continue with warn behavior

    return False, False, False  # Don't write, not success, no update


def write_content_to_file(
        f: TextIO, content: str, partial: Path, last: bool, is_new: bool,
) -> None:
    """Write content to file handle and print appropriate action.

    Args:
        f: File handle to write to
        content: Content to write
        partial: Path to file for logging
        last: Whether this is the last file being processed
        is_new: Whether this is a new file
    """
    if is_new:
        print_action(Action.NEW, partial, last=last)
    else:
        print_action(Action.WRITE, partial, last=last)
    f.seek(0)
    f.write(content)
    f.truncate()


def write_to_file(
        block: ParsedData,
        content: str,
        f: TextIO,
        last: bool,
        partial: Path,
        warn: bool,
        update: bool,
        newfile: bool,
) -> tuple[bool, bool]:
    """Write the content to the file if it differs from the current contents.

    Show a diff if the file contents differ and the warn flag is set.

    Returns:
        Tuple of (success, source_was_updated)
    """
    # Read current file contents
    current_contents, error_msg = read_file_content(f)
    if current_contents is None:
        show_error(Action.WRITE, str(partial), error_msg)
        return False, False

    # Check if content differs
    if current_contents != content:
        should_write, success, source_updated = handle_file_difference(
            block, content, current_contents, partial, warn, update
        )
        if should_write:
            write_content_to_file(f, content, partial, last, newfile)
        return success, source_updated
    else:
        print_action(Action.UNCHANGED, partial, last=last)
        return True, False


def remove_common_path(a: Path, b: Path, prefix: str = "") -> tuple[Path, Path]:
    """Remove the common path from the two paths."""
    common = Path(os.path.commonpath([str(a), str(b)]))
    a_parts = a.parts[len(common.parts):]
    b_parts = b.parts[len(common.parts):]
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
                + click.style(line, fg="bright_white", bold=True,
                              underline=True),
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
