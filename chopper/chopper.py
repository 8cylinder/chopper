#!/usr/bin/env python3

from datetime import datetime
import os
import sys
import errno
import io
import argparse
from textwrap import dedent
from pprint import pprint as pp
from html.parser import HTMLParser
from pathlib import Path
from enum import Enum
import difflib
from typing import List, Any, Dict, Union

NOW = datetime.now().isoformat(timespec='seconds', sep=',')
DRYRUN = False
CHOPPER_NAME = '.chopper.html'


class C:
    MAGENTA = '\033[95m'

    RED = '\033[31m'
    BRED = '\033[91m'
    REDB = '\033[41m'

    BLUE = '\033[34m'
    BBLUE = '\033[94m'
    BLUEB = '\033[44m'

    BCYAN = '\033[96m'
    CYAN = '\033[36m'
    CYANB = '\033[46m'

    GREEN = '\033[32m'
    BGREEN = '\033[92m'
    GREENB = '\033[42m'

    BLACK = '\033[30m'
    BBLACK = '\033[90m'
    BLACKB = '\033[40m'

    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


class Action(Enum):
    CHOP = 'Chop'
    WRITE = 'Write'
    NEW = 'New'
    DIR = 'Mkdir'
    UNCHANGED = 'File unchanged'


def info(
    action: Action, filename: Union[str, Path], dry_run: bool = False, last: bool = False
) -> None:
    dry_run = ' (DRY RUN)' if dry_run else ''
    choppa: str = f'{C.MAGENTA}{C.BOLD}CHOPPER:{C.RESET}'
    task: str = f'{C.BGREEN}{action.value}{dry_run}{C.RESET}'
    filename: str = f'{C.BBLUE}{filename}{C.RESET}'
    tree: str = ''
    if action != action.CHOP:
        tree = '└─ ' if last else '├─ '
    date: str = ''
    if action == action.CHOP:
        date = f'{C.BBLACK}{NOW}{C.RESET}'
    print(f'{choppa} {tree}{task} {filename}  {date}')


def error(action: Action, filename: str, msg: str, dry_run: bool = False) -> None:
    dry_run = ' (DRY RUN)' if dry_run else ''
    choppa: str = f'{C.REDB}{C.BOLD}CHOPPER:{C.RESET}'
    action: str = f'{C.REDB}{C.BOLD}{action.value}{dry_run}{C.RESET}'
    filename: str = f'{C.BBLUE}{filename}{C.RESET}'
    print(choppa, action, msg, filename, file=sys.stderr)


class ChopperParser(HTMLParser):
    tags: list[str] = ['style', 'script', 'chop']
    tree: list[Any] = []
    path: str = None
    parsed_data: list[dict[str, Any]] = []
    start: tuple = None

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.tree.append(tag)
            for attr in attrs:
                if attr[0] == 'chopper:file':
                    self.path = attr[1]
                    pos = list(self.getpos())
                    pos[0] = pos[0] - 1
                    extra = [len(i) for i in self.get_starttag_text().split("\n")]
                    for line in extra:
                        pos = (pos[0] + 1, line)
                    self.start = pos

    def handle_endtag(self, tag):
        if tag in self.tags:
            self.tree.pop()
            if not self.tree:
                self.parsed_data.append(
                    {
                        'path': self.path,
                        'tag': tag,
                        'start': self.start,
                        'end': self.getpos(),
                    }
                )
                self.path = ''


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


def chop(source, types, insert_comments, comments, warn=False):
    """Chop up the source file into the blocks defined by the chopper tags."""
    info(Action.CHOP, source)
    with open(source, 'r') as f:
        source_html = f.read()

    parser = ChopperParser()
    parser.parsed_data.clear()
    parser.feed(source_html)
    data = parser.parsed_data

    source_html = source_html.splitlines()
    block_count = len(data) - 1
    success: bool = True
    for i, block in enumerate(data):
        block['base_path'] = types[block['tag']]
        block['path'] = magic_vars(block['path'], source)
        block['content'] = extract_block(block['start'], block['end'], source_html)
        block['source_file'] = source

        c = comments[block['tag']]
        block['comment_open'], block['comment_close'] = c
        if insert_comments:
            # text = [source, block['path']]
            dest = Path(os.path.join(block['base_path'], block['path']))
            comment = f'{c[0]}{source} -> {dest}{c[1]}'
            block['content'] = f'\n{comment}\n\n{block["content"]}'

        last = False if block_count != i else True
        if not new_or_overwrite_file(block, warn, last):
            success = False

    return success


def extract_block(start: List, end: List, source_html: List) -> str:
    """Extract the block of code from the source.

    Extract from the end of the start tag to the start of the end tag."""

    start_line: int = start[0] - 1
    start_char: int = start[1]
    end_line: int = end[0]
    end_char: int = end[1]

    extracted: array = source_html[start_line:end_line]
    if len(extracted) == 1:
        extracted[0] = extracted[0][start_char:end_char]
    else:
        extracted[0] = extracted[0][start_char:]
        extracted[-1] = extracted[-1][:end_char]

    extracted = '\n'.join(extracted)
    extracted = dedent(extracted)
    extracted = extracted.strip()
    extracted = f'{extracted}\n'

    return extracted


def magic_vars(path, source):
    """Replace magic variables in the path with the source file name.

    If the source file is named `hero.chopper.html` and the chopper:file
    attribute is `assets/{NAME}.css`, return the string `assets/hero.css`.
    """
    source = Path(source)
    source_name = source.name.replace(CHOPPER_NAME, '')
    fields = {
        'NAME': source_name,
        'THIS-NAME': source,
    }
    try:
        new_name = path.format(**fields)
    except KeyError:
        error(Action.CHOP, str(source), 'Invalid magic variable in attribute:')
        sys.exit(1)
    return new_name


def new_or_overwrite_file(block, warn=False, last=False):
    """Create or update the file specified in the chopper:file attribute."""
    content = f'{block["content"]}'
    partial_file = Path(os.path.join(block['base_path'], block['path']))

    if partial_file.parent.mkdir(parents=True, exist_ok=True):
        info(Action.DIR, partial_file.parent)

    try:
        if partial_file.exists():
            with open(partial_file, 'r+') as f:
                success: bool = write_to_file(block, content, f, last, partial_file, warn, False)
        else:
            with open(partial_file, 'w') as f:
                success: bool = write_to_file(block, content, f, last, partial_file, False, True)
    except IsADirectoryError:
        error(Action.CHOP, block['source_file'], 'Destination is a dir.')
        sys.exit(1)

    return success


def write_to_file(block, content, f, last, partial, warn, newfile):
    """Write the content to the file if it differs from the current contents.

    Show a diff if the file contents differ and the warn flag is set.
    """
    success: bool = True
    try:
        current_contents = f.read()
    except io.UnsupportedOperation:
        current_contents = None

    if current_contents != content:
        if warn:
            error(Action.WRITE, partial, 'File contents differ')
            show_diff(content, current_contents, block['path'], str(partial))
            success = False
            print()
            # if not DRYRUN:
            #     sys.exit(1)
        else:
            if newfile:
                info(Action.NEW, partial, last=last)
            else:
                info(Action.WRITE, partial, last=last)
            if not DRYRUN:
                f.seek(0)
                f.write(content)
                f.truncate()
    else:
        info(Action.UNCHANGED, partial, last=last)

    return success


def show_diff(a, b, fname_a, fname_b):
    diff = difflib.context_diff(
        a.splitlines(), b.splitlines(), tofile=fname_a, fromfile=fname_b, n=0
    )
    print()

    for i, line in enumerate(diff):
        if i <= 2:
            continue

        line = line.rstrip()

        if line.startswith('!'):
            print(line)
        elif line.startswith('--'):
            print(f'{C.BLACK}{C.REDB}{line}{C.RESET}')
        elif line.startswith('****'):
            hl = '=' * 80
            print()
            print(f'{C.BCYAN}{hl}{C.RESET}')
            print()
        elif line.startswith('*'):
            print(f'{C.BLACK}{C.GREENB}{line}{C.RESET}')
        else:
            print(line)


def main():
    help_msg = dedent(
        '''
      Chop files into their separate types, style, script and html.

      Get to the choppa!
    '''
    )

    parser = argparse.ArgumentParser(
        description=help_msg, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-s', '--script-dir', help='Destination for the script files')
    parser.add_argument('-c', '--style-dir', help='Destination for the style files')
    parser.add_argument('-m', '--html-dir', help='Destination for the html files')
    parser.add_argument('--comments', action='store_true', help='Add comments to generated files')
    parser.add_argument(
        '--warn',
        action='store_true',
        help='Warn when the file contents differs instead of overwriting it.',
    )
    parser.add_argument(
        '--dry-run', action="store_true", help="Do not write any file to the filesystem"
    )
    parser.add_argument(
        'source_dir',
        metavar='SOURCE-DIR',
        help='The directory that contains the chopper files.',
    )

    args = parser.parse_args()

    global DRYRUN
    DRYRUN = args.dry_run

    if os.path.exists(args.source_dir):
        if os.path.isdir(args.source_dir):
            chopper_files = find_chopper_files(args.source_dir)
        else:
            chopper_files = [args.source_dir]
    else:
        error(Action.CHOP, args.source_dir, 'No such file or directory:')
        sys.exit(1)

    types = {
        'script': args.script_dir or '',
        'style': args.style_dir or '',
        'chop': args.html_dir or '',
    }

    comment_types = {
        'script': ['// ', ''],
        'style': ['/* ', ' */'],
        # 'chop': ['<!-- ', ' -->'],
        'chop': ['{{# ', ' #}}'],
    }

    success: bool = True
    for source in chopper_files:
        if not chop(source, types, args.comments, comment_types, warn=args.warn):
            success = False

    if not success:
        error(Action.CHOP, '', 'Some files were different.')
        sys.exit(1)

    print()


if __name__ == '__main__':
    main()
